"""Create users and jobs tables.

Revision ID: 0001_create_users_jobs
Revises: None
Create Date: 2025-12-13
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_create_users_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "auth_method",
            sa.Enum("github", "local", name="auth_method", native_enum=False),
            nullable=False,
        ),
        sa.Column("provider_id", sa.String(length=128), nullable=True, unique=True),
        sa.Column("username", sa.String(length=64), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(length=256), nullable=True),
        sa.Column("github_username", sa.String(length=64), nullable=True, unique=True),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column(
            "role",
            sa.Enum("user", "admin", name="user_role", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "priority_group",
            sa.Enum("normal", "high", "urgent", name="priority_group", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_approved", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("dir_name", sa.String(length=256), nullable=False, unique=True),
        sa.Column("job_name", sa.String(length=128), nullable=False),
        sa.Column("slurm_job_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_owner_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("users")


