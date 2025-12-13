from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from fold_webapp.db import AuthMethod, PriorityGroup, User, UserRole, get_session
from fold_webapp.services import require_role
from fold_webapp.services.password import hash_password


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def render_admin() -> None:
    admin = require_role(UserRole.admin)
    if admin is None:
        return

    st.header("Admin console")

    tab_users, tab_invite, tab_local = st.tabs(["Users", "Invite user", "Create local admin"])
    with tab_users:
        _render_user_management(current_admin=admin)
    with tab_invite:
        _render_invite_form()
    with tab_local:
        _render_create_local_admin()


def _render_user_management(*, current_admin: User) -> None:
    session = get_session()
    try:
        users = session.query(User).order_by(User.created_at.desc()).all()
    finally:
        session.close()

    st.subheader(f"Users ({len(users)})")

    pending = [u for u in users if not u.is_active]
    active = [u for u in users if u.is_active]

    if pending:
        st.caption("Pending invitations")
        for u in pending:
            status = "approved" if u.is_approved else "pending approval"
            with st.expander(f"{u.display_name} ({u.github_username or 'no github username'}) - {status}"):
                st.write(f"Auth: {u.auth_method.value}")
                st.write(f"Role: {u.role.value}")
                st.write(f"Priority: {u.priority_group.value}")
                st.write(f"Email: {u.email or ''}")

                c1, c2 = st.columns(2)
                with c1:
                    if not u.is_approved and st.button("Approve", key=f"approve_{u.id}"):
                        _approve_user(user_id=u.id)
                        st.rerun()
                with c2:
                    if st.button("Revoke invitation", key=f"revoke_{u.id}"):
                        _delete_user(user_id=u.id)
                        st.rerun()

    if active:
        st.caption("Active users")
        for u in active:
            with st.expander(f"{u.display_name} ({u.role.value})"):
                st.write(f"Auth: {u.auth_method.value}")
                st.write(f"GitHub: {u.github_username or ''}")
                st.write(f"Email: {u.email or ''}")
                st.write(f"Last login: {u.last_login or ''}")

                role = st.selectbox(
                    "Role",
                    options=[r.value for r in UserRole],
                    index=[r.value for r in UserRole].index(u.role.value),
                    key=f"role_{u.id}",
                )
                priority = st.selectbox(
                    "Priority group",
                    options=[p.value for p in PriorityGroup],
                    index=[p.value for p in PriorityGroup].index(u.priority_group.value),
                    key=f"priority_{u.id}",
                )

                if st.button("Save", key=f"save_{u.id}"):
                    _update_user_role_priority(
                        user_id=u.id, role=UserRole(role), priority_group=PriorityGroup(priority)
                    )
                    st.success("Updated.")

                if u.id != current_admin.id:
                    if st.button("Deactivate", key=f"deactivate_{u.id}"):
                        _set_user_approved(user_id=u.id, approved=False)
                        st.rerun()


def _render_invite_form() -> None:
    st.subheader("Invite user (GitHub)")
    st.caption("Invite-only: users must be pre-created here before GitHub sign-in will succeed.")

    with st.form("invite_user"):
        github_username = st.text_input("GitHub username", help="Example: octocat").strip()
        display_name = st.text_input("Display name").strip()
        email = st.text_input("Email (optional)").strip().lower()
        role = st.selectbox("Role", options=[r.value for r in UserRole], index=0)
        priority = st.selectbox("Priority group", options=[p.value for p in PriorityGroup], index=0)
        auto_approve = st.checkbox("Approve immediately", value=True)
        submitted = st.form_submit_button("Create invitation", use_container_width=True)

    if not submitted:
        return

    if not github_username or not display_name:
        st.error("GitHub username and display name are required.")
        return

    session = get_session()
    try:
        exists = (
            session.query(User)
            .filter(User.github_username.ilike(github_username.lower()))
            .one_or_none()
        )
        if exists is not None:
            st.error("A user with that GitHub username already exists.")
            return

        user = User(
            auth_method=AuthMethod.github,
            provider_id=None,
            username=None,
            password_hash=None,
            github_username=github_username.lower(),
            email=email or None,
            display_name=display_name,
            avatar_url=None,
            role=UserRole(role),
            priority_group=PriorityGroup(priority),
            is_approved=bool(auto_approve),
            is_active=False,
            approved_at=_utcnow() if auto_approve else None,
            activated_at=None,
            last_login=None,
        )
        session.add(user)
        session.commit()
    finally:
        session.close()

    st.success("Invitation created.")


def _render_create_local_admin() -> None:
    st.subheader("Create local admin (offline)")
    st.caption("Local admins can sign in without GitHub when the network is unavailable.")

    with st.form("create_local_admin"):
        username = st.text_input("Username", help="Alphanumeric").strip()
        display_name = st.text_input("Display name").strip()
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create local admin", use_container_width=True)

    if not submitted:
        return

    if not username.isalnum():
        st.error("Username must be alphanumeric.")
        return
    if not display_name:
        st.error("Display name is required.")
        return
    if not password or len(password) < 8:
        st.error("Password must be at least 8 characters.")
        return
    if password != confirm:
        st.error("Passwords do not match.")
        return

    session = get_session()
    try:
        if session.query(User).filter(User.username == username).one_or_none() is not None:
            st.error("That username is already taken.")
            return

        user = User(
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
        session.add(user)
        session.commit()
    finally:
        session.close()

    st.success("Local admin created.")


def _approve_user(*, user_id: int) -> None:
    _set_user_approved(user_id=user_id, approved=True)


def _set_user_approved(*, user_id: int, approved: bool) -> None:
    session = get_session()
    try:
        u = session.query(User).filter(User.id == int(user_id)).one_or_none()
        if u is None:
            return
        u.is_approved = bool(approved)
        u.approved_at = _utcnow() if approved else None
        session.commit()
    finally:
        session.close()


def _delete_user(*, user_id: int) -> None:
    session = get_session()
    try:
        u = session.query(User).filter(User.id == int(user_id)).one_or_none()
        if u is None:
            return
        session.delete(u)
        session.commit()
    finally:
        session.close()


def _update_user_role_priority(*, user_id: int, role: UserRole, priority_group: PriorityGroup) -> None:
    session = get_session()
    try:
        u = session.query(User).filter(User.id == int(user_id)).one_or_none()
        if u is None:
            return
        u.role = role
        u.priority_group = priority_group
        session.commit()
    finally:
        session.close()


