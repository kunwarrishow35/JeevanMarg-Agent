"""User model for authentication and role-based access."""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Enum

from app.database import Base


class UserRole(str, enum.Enum):
    """User roles for role-based access control."""
    DISPATCHER = "dispatcher"
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"


class User(Base):
    """User account for authentication."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.DISPATCHER)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
