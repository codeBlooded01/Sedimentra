"""
Admin-only API routes for user management.

All endpoints require role="admin" — enforced via require_admin dependency
which calls get_current_user → checks is_active AND is_approved AND role.
Direct Postman/API calls without a valid admin token will be rejected with 401/403.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.db.models.user import User
from app.api.deps import require_admin
from app.schemas.auth import UserListResponse, MessageResponse, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Return all users sorted by creation date (newest first)."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return {"users": users, "total": len(users)}


@router.post("/users/{user_id}/approve", response_model=MessageResponse)
async def approve_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """Approve a pending user so they can log in."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_approved = True
    user.is_active = True
    await db.commit()
    return {"message": f"User {user.email} has been approved and can now log in."}


@router.post("/users/{user_id}/reject", response_model=MessageResponse)
async def reject_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Reject/revoke a user's access.
    Sets is_approved=False and is_active=False so any existing tokens
    are blocked by the get_current_user dependency on the next request.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject/deactivate an admin account."
        )

    user.is_approved = False
    user.is_active = False
    await db.commit()
    return {"message": f"User {user.email} has been rejected and deactivated."}


@router.post("/users/{user_id}/impersonate", response_model=TokenResponse)
async def impersonate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """
    Generate an access token for an approved user to test their account
    safely using the Administrator test-session UI.
    """
    tokens = await auth_service.impersonate_user(db, user_id)
    return {**tokens, "token_type": "bearer"}
