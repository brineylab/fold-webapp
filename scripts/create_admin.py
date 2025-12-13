#!/usr/bin/env python3
from __future__ import annotations

import getpass
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from fold_webapp.db import AuthMethod, PriorityGroup, User, UserRole, get_engine, get_session  # noqa: E402
from fold_webapp.db.models import Base  # noqa: E402
from fold_webapp.services.password import hash_password  # noqa: E402


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def main() -> int:
    os.chdir(repo_root)

    # Minimal bootstrap for a fresh install: create tables if migrations weren't run yet.
    engine = get_engine()
    Base.metadata.create_all(engine)

    session = get_session()
    try:
        existing = session.query(User).filter(User.role == UserRole.admin).first()
        if existing is not None:
            print(f"An admin already exists: {existing.display_name} ({existing.username or existing.github_username})")
            resp = input("Create another local admin? [y/N]: ").strip().lower()
            if resp != "y":
                return 0

        print("Create local admin account")
        username = input("Username (alphanumeric): ").strip()
        if not username.isalnum():
            print("Error: username must be alphanumeric.")
            return 1

        display_name = input("Display name: ").strip()
        if not display_name:
            print("Error: display name required.")
            return 1

        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match.")
            return 1
        if len(password) < 8:
            print("Error: password must be at least 8 characters.")
            return 1

        if session.query(User).filter(User.username == username).one_or_none() is not None:
            print("Error: username already exists.")
            return 1

        admin = User(
            auth_method=AuthMethod.local,
            provider_id=None,
            username=username,
            password_hash=hash_password(password),
            github_username=None,
            email=None,
            display_name=display_name,
            avatar_url=None,
            role=UserRole.admin,
            priority_group=PriorityGroup.urgent,
            is_approved=True,
            is_active=True,
            approved_at=_utcnow(),
            activated_at=_utcnow(),
            last_login=None,
        )
        session.add(admin)
        session.commit()

        print(f"Created local admin: {username}")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())


