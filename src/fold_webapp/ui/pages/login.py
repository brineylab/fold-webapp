from __future__ import annotations

import streamlit as st

from fold_webapp.services import (
    AuthError,
    AuthService,
    NotApprovedError,
    NotInvitedError,
    login_user,
)


def render_login() -> None:
    st.title("Sign in")
    st.caption("Authenticate to submit jobs and access your results.")

    auth = AuthService()

    # Primary: GitHub OAuth
    auth_url = auth.get_authorization_url()
    st.link_button("Sign in with GitHub", auth_url, use_container_width=True)

    # Fallback: local admin
    st.divider()
    with st.expander("Local admin login", expanded=False):
        with st.form("local_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            try:
                user = auth.authenticate_local(username=username, password=password)
                login_user(user=user)
                st.rerun()
            except AuthError as e:
                st.error(str(e))


def handle_oauth_callback() -> bool:
    """Handle GitHub OAuth callback parameters. Returns True if login succeeded."""
    qp = st.query_params
    code = qp.get("code")
    state = qp.get("state")
    if not code or not state:
        return False

    auth = AuthService()
    try:
        token = auth.exchange_code_for_token(code=str(code), state=str(state))
        info = auth.get_github_user_info(access_token=token)
        user = auth.authenticate_github_user(github_info=info)
        login_user(user=user)
        st.query_params.clear()
        return True
    except NotInvitedError as e:
        st.error(str(e))
        return False
    except NotApprovedError as e:
        st.warning(str(e))
        return False
    except AuthError as e:
        st.error(str(e))
        return False


