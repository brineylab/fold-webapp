from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import streamlit as st

from fold_webapp.config import get_settings
from fold_webapp.db import AuthMethod, User, UserRole, get_session
from fold_webapp.services.password import verify_password


class AuthError(RuntimeError):
    """Authentication error with a user-friendly message."""


class NotInvitedError(AuthError):
    """Raised when a user authenticates via OAuth but has no pre-approved invitation."""


class NotApprovedError(AuthError):
    """Raised when a user exists but is not approved/active."""


_GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
_GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_USER_URL = "https://api.github.com/user"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AuthService:
    """Authentication helper supporting GitHub OAuth and local admin accounts."""

    def get_authorization_url(self) -> str:
        """Return a GitHub OAuth authorization URL and store state in session for CSRF."""
        settings = get_settings()

        state = secrets.token_urlsafe(32)
        st.session_state["oauth_state"] = state

        params = {
            "client_id": settings.oauth_client_id,
            "redirect_uri": settings.oauth_redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return f"{_GITHUB_AUTHORIZE_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, *, code: str, state: str) -> str:
        """Exchange GitHub OAuth code for an access token."""
        settings = get_settings()

        expected_state = st.session_state.get("oauth_state")
        if not expected_state or not secrets.compare_digest(str(expected_state), str(state)):
            raise AuthError("Invalid login state. Please try again.")

        resp = httpx.post(
            _GITHUB_TOKEN_URL,
            data={
                "client_id": settings.oauth_client_id,
                "client_secret": settings.oauth_client_secret,
                "code": code,
                "redirect_uri": settings.oauth_redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise AuthError("GitHub authentication failed. Please try again.")

        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise AuthError("GitHub authentication failed. Please try again.")
        return str(token)

    def get_github_user_info(self, *, access_token: str) -> dict[str, Any]:
        """Fetch GitHub user profile for the authenticated token."""
        resp = httpx.get(
            _GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise AuthError("Unable to fetch GitHub profile.")
        return resp.json()

    def authenticate_github_user(self, *, github_info: dict[str, Any]) -> User:
        """
        Invite-only GitHub authentication.

        Matching priority:
        1) provider_id (returning users)
        2) github_username (pending invite)
        """
        github_id = str(github_info.get("id", "")).strip()
        login = str(github_info.get("login", "")).strip().lower()
        if not github_id or not login:
            raise AuthError("Unable to read GitHub identity.")

        provider_id = f"github:{github_id}"

        session = get_session()
        try:
            # Returning users
            user = session.query(User).filter(User.provider_id == provider_id).one_or_none()
            if user is not None:
                if not user.is_approved:
                    raise NotApprovedError("Your access is disabled. Contact an administrator.")
                user.last_login = _utcnow()
                session.commit()
                session.refresh(user)
                return user

            # Pending invitation by GitHub username
            invited = (
                session.query(User)
                .filter(
                    User.auth_method == AuthMethod.github,
                    User.provider_id.is_(None),
                    User.github_username.is_not(None),
                    User.github_username.ilike(login),
                )
                .one_or_none()
            )
            if invited is None:
                raise NotInvitedError(
                    f"No invitation found for GitHub user '{login}'. "
                    "Contact an administrator to request access."
                )
            if not invited.is_approved:
                raise NotApprovedError(
                    "Your invitation exists but is not approved yet. Contact an administrator."
                )

            invited.provider_id = provider_id
            invited.is_active = True
            invited.activated_at = _utcnow()
            invited.last_login = _utcnow()
            invited.display_name = str(github_info.get("name") or github_info.get("login") or invited.display_name)
            invited.avatar_url = str(github_info.get("avatar_url") or invited.avatar_url or "") or None

            # Email may be null depending on GitHub privacy; keep any admin-provided email.
            gh_email = github_info.get("email")
            if gh_email:
                invited.email = str(gh_email).strip().lower()

            session.commit()
            session.refresh(invited)
            return invited
        finally:
            session.close()

    def authenticate_local(self, *, username: str, password: str) -> User:
        """Authenticate a local account (intended for offline admin access)."""
        username = username.strip()
        if not username or not password:
            raise AuthError("Invalid username or password.")

        session = get_session()
        try:
            user = (
                session.query(User)
                .filter(User.auth_method == AuthMethod.local, User.username == username)
                .one_or_none()
            )
            if user is None or not user.password_hash:
                # Constant-time-ish work to reduce user enumeration signal.
                verify_password(password, "00" * 16 + "$" + "00" * 32)
                raise AuthError("Invalid username or password.")

            if not verify_password(password, user.password_hash):
                raise AuthError("Invalid username or password.")

            if not user.is_approved:
                raise NotApprovedError("Your access is disabled. Contact an administrator.")

            user.last_login = _utcnow()
            session.commit()
            session.refresh(user)
            return user
        finally:
            session.close()


def login_user(*, user: User) -> None:
    """Persist login in Streamlit session state."""
    st.session_state["user_id"] = int(user.id)


def logout_user() -> None:
    """Clear login-related session state."""
    for k in ("user_id", "oauth_state"):
        if k in st.session_state:
            del st.session_state[k]


def require_auth() -> User | None:
    """Return the current user, or None if unauthenticated."""
    user_id = st.session_state.get("user_id")
    if user_id is None:
        return None

    session = get_session()
    try:
        return session.query(User).filter(User.id == int(user_id)).one_or_none()
    finally:
        session.close()


def require_role(role: UserRole) -> User | None:
    """Return the current user if they have required role (admins always pass)."""
    user = require_auth()
    if user is None:
        return None
    if user.role == UserRole.admin:
        return user
    if user.role != role:
        st.error("You don't have permission to access this page.")
        return None
    return user


