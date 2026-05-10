from fastapi import APIRouter, Depends, Request, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.db.session import get_db
from app.schemas.auth import (
    SignupRequest, AdminSetupRequest, LoginRequest, TokenResponse,
    RefreshRequest, UserResponse, MessageResponse,
    ForgotPasswordRequest, ResetPasswordRequest
)
from app.services import auth_service
from app.api.deps import get_current_user, require_admin
from app.core.redis_util import get_redis
from app.core.security import decode_token
import time
from app.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/admin/setup", response_model=MessageResponse, status_code=201)
@limiter.limit("30/minute")
async def admin_setup(request: Request, body: AdminSetupRequest, db: AsyncSession = Depends(get_db)):
    """
    One-time admin account creation endpoint.
    Returns 409 Conflict if an admin account already exists.
    Protected against race conditions at the DB level in auth_service.create_admin().
    """
    import traceback
    try:
        await auth_service.create_admin(db, body.email, body.password, body.full_name)
        return {"message": "Admin account created successfully. You can now log in."}
    except HTTPException:
        raise
    except Exception:
        err_msg = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"TRACEBACK:\n{err_msg}")


@router.post("/signup", response_model=MessageResponse, status_code=201)
@limiter.limit("5/minute")
async def signup(request: Request, body: SignupRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.signup(db, body.email, body.password, body.full_name)
    return {
        "message": (
            "Account request submitted. An administrator will review and approve "
            "your account before you can log in."
        )
    }


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.login(db, body.email, body.password)
    return {**tokens, "token_type": "bearer"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    tokens = await auth_service.refresh_tokens(db, body.refresh_token)
    return {**tokens, "token_type": "bearer"}


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    await auth_service.verify_email(db, token)
    return {"message": "Email verified successfully. You can now log in."}


@router.get("/me", response_model=UserResponse)
async def me(current_user=Depends(get_current_user)):
    return current_user



@router.post("/logout", response_model=MessageResponse)
async def logout(request: Request, current_user=Depends(get_current_user)):
    """
    Log out the user and blacklist the current JWT token.
    """
    # Extract the token from the Authorization header
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or "jti" not in payload or "exp" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    jti = payload["jti"]
    exp = payload["exp"]
    now = int(time.time())
    ttl = exp - now
    if ttl > 0:
        redis_conn = get_redis()
        redis_conn.setex(f"blacklist:{jti}", ttl, "1")
    return {"message": "Successfully logged out. Please clear your local session data."}


@router.post("/forgot-password", response_model=dict)
@limiter.limit("3/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    return await auth_service.process_forgot_password(db, body.email, background_tasks)


@router.post("/reset-password", response_model=MessageResponse)
@limiter.limit("3/minute")
async def reset_password(request: Request, body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.process_reset_password(db, body.token, body.new_password)


@router.post("/admin/promote/{user_id}", response_model=MessageResponse)
async def promote_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(require_admin)):
    """
    Promote an approved user to the admin role. Only primary admins can do this, up to 3 admins total.
    """
    return await auth_service.promote_to_admin(db, user_id, current_user)
