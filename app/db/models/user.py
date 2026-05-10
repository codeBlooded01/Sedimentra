"""
User model for the Genomic Intelligence System.
Supports roles: "admin" and "user".
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean,
    DateTime, Text
)

from sqlalchemy.sql import func
from app.db.models.upload import Base 


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)

    # Role: "admin" | "user"
    role = Column(String(20), nullable=False, default="user")
    is_primary_admin = Column(Boolean, nullable=False, default=False)

    # Account state flags
    is_active = Column(Boolean, nullable=False, default=True)
    is_verified = Column(Boolean, nullable=False, default=False)
    is_approved = Column(Boolean, nullable=False, default=False)

    # Email verification token (cleared after use)
    verification_token = Column(Text, nullable=True)

    # Brute-force protection
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Audit
    last_login = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
