from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from app.db.models.user import User
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    create_verification_token, decode_token,
    get_unverified_token_data,
    create_password_reset_token, decode_password_reset_token
)
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def validate_email_domain(email: str) -> None:
    allowed = settings.allowed_domains_list
    if not allowed:
        return
    domain = email.split("@")[1].lower()
    if domain not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email domain not allowed. Permitted: {', '.join(allowed)}"
        )


async def signup(db: AsyncSession, email: str, password: str, full_name: str | None = None) -> User:
    validate_email_domain(email)

    result = await db.execute(select(User).where(User.email == email.lower()))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    verification_token = create_verification_token(email)
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name.strip().title() if full_name else full_name,
        verification_token=verification_token,
        is_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
        is_approved=False,  # always requires explicit admin approval
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("New user registered (pending approval): %s", email)
    # TODO: send verification email with token
    return user


async def create_admin(db: AsyncSession, email: str, password: str, full_name: str | None = None) -> User:
    """
    Create the first-ever admin account.
    Uses a SELECT-then-INSERT inside the same transaction to prevent race conditions.
    Raises 409 if any admin already exists.
    """
    validate_email_domain(email)

    # Check for existing admin — done at the DB level to be race-condition safe
    count_result = await db.execute(
        select(func.count()).select_from(User).where(User.role == "admin")
    )
    if (count_result.scalar() or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An admin account already exists. Contact your system administrator."
        )

    # Also block if email is already taken
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    admin = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        full_name=full_name.strip().title() if full_name else full_name,
        role="admin",
        is_primary_admin=True,
        is_active=True,
        is_verified=True,
        is_approved=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    logger.info("Admin account created: %s", email)
    return admin


async def impersonate_user(db: AsyncSession, user_id: int) -> dict:
    """
    Generate an access token and refresh token for an approved user
    without requiring their password. (Used by Admin for testing).
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot impersonate a deactivated user")
    if not user.is_approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot impersonate an unapproved user")

    logger.info("Admin impersonating user: %s (id=%d)", user.email, user.id)
    return {
        "access_token": create_access_token(str(user.id), {"role": user.role}),
        "refresh_token": create_refresh_token(str(user.id)),
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def login(db: AsyncSession, email: str, password: str) -> dict:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning("Login attempt for unknown email: %s", email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked. Try again after {user.locked_until.isoformat()}"
        )

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            logger.warning("Account locked after failed attempts: %s", email)
        await db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Gate 1: account must be active
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    # Gate 2: email must be verified (if REQUIRE_EMAIL_VERIFICATION is on)
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    # Gate 3: must be approved by admin — checked per-request, not cached
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending admin approval. You will be notified once your account is activated."
        )

    # Reset brute-force state on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    logger.info("Successful login: %s", email)
    return {
        "access_token": create_access_token(str(user.id), {"role": user.role}),
        "refresh_token": create_refresh_token(str(user.id)),
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def verify_email(db: AsyncSession, token: str) -> User:
    payload = decode_token(token)
    if not payload or payload.get("type") != "verify":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.email == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_verified = True
    user.verification_token = None
    await db.commit()
    logger.info("Email verified: %s", user.email)
    return user


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return {
        "access_token": create_access_token(str(user.id), {"role": user.role}),
        "refresh_token": create_refresh_token(str(user.id)),
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def promote_to_admin(db: AsyncSession, user_id: int, current_user: User) -> dict:
    if not current_user.is_primary_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the primary admin can promote users")

    count_result = await db.execute(select(func.count()).select_from(User).where(User.role == "admin"))
    total_admins = count_result.scalar() or 0
    if total_admins >= 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum number of admins (3) reached")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already an admin")
    if not user.is_approved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User must be approved first")

    user.role = "admin"
    await db.commit()
    logger.info("User %s promoted to admin by %s", user.email, current_user.email)
    return {"message": "User promoted to admin successfully"}


async def process_forgot_password(db: AsyncSession, email: str, background_tasks=None) -> dict:
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    # Always return a blind response to prevent enumeration
    base_message = {"message": "If an account exists for this email, a reset link has been sent."}
    if not user:
        return base_message

    from app.services.mail_service import send_password_reset_email

    token = create_password_reset_token(user.email, user.hashed_password)
    frontend_url = settings.FRONTEND_URL.rstrip("/")
    reset_link = f"{frontend_url}/reset-password?token={token}"

    logger.info("Password reset token created for %s", user.email)

    if background_tasks is not None:
        background_tasks.add_task(send_password_reset_email, user.email, reset_link)
    else:
        # Fallback: synchronous send if no background_tasks provided
        send_password_reset_email(user.email, reset_link)

    return base_message


async def process_reset_password(db: AsyncSession, token: str, new_password: str) -> dict:
    unauth_payload = get_unverified_token_data(token)
    if not unauth_payload or unauth_payload.get("type") != "reset" or not unauth_payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    email = unauth_payload.get("sub")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    payload = decode_password_reset_token(token, user.hashed_password)
    if not payload or payload.get("type") != "reset" or payload.get("sub") != user.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()

    logger.info("Password reset successfully for %s", user.email)
    return {"message": "Password updated successfully. You can now log in."}
