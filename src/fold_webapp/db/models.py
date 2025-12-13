from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, Enum):
    user = "user"
    admin = "admin"


class PriorityGroup(str, Enum):
    normal = "normal"
    high = "high"
    urgent = "urgent"


class AuthMethod(str, Enum):
    github = "github"
    local = "local"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Authentication fields
    auth_method: Mapped[AuthMethod] = mapped_column(
        SAEnum(AuthMethod, native_enum=False, name="auth_method"),
        default=AuthMethod.github,
        nullable=False,
    )
    # OAuth users: "github:{id}" once activated; local users: None
    provider_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)

    # Local accounts (offline admin fallback)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Invite-only matching (pre-approved by admin)
    github_username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Display/profile
    display_name: Mapped[str] = mapped_column(String(128))
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Authorization
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, native_enum=False, name="user_role"),
        default=UserRole.user,
        nullable=False,
    )
    priority_group: Mapped[PriorityGroup] = mapped_column(
        SAEnum(PriorityGroup, native_enum=False, name="priority_group"),
        default=PriorityGroup.normal,
        nullable=False,
    )

    # Lifecycle flags
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    jobs: Mapped[list["Job"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan",
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Matches filesystem directory name, e.g. "20241212_140530_myjob"
    dir_name: Mapped[str] = mapped_column(String(256), unique=True)
    job_name: Mapped[str] = mapped_column(String(128))
    slurm_job_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="jobs")


