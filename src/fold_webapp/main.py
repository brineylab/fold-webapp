from __future__ import annotations

import streamlit as st

from fold_webapp.config import get_settings
from fold_webapp.models import AlphaFold3Model
from fold_webapp.services import JobManager, SlurmClient
from fold_webapp.services import require_auth
from fold_webapp.ui.sidebar import render_sidebar
from fold_webapp.ui.styles import apply_global_styles, configure_page
from fold_webapp.ui.pages import (
    render_admin,
    handle_oauth_callback,
    render_batch_csv,
    render_json_upload,
    render_login,
    render_my_jobs,
    render_new_fold,
)


def main() -> None:
    settings = get_settings()
    configure_page()
    apply_global_styles()

    if "code" in st.query_params:
        handle_oauth_callback()
        st.rerun()

    user = require_auth()
    if user is None:
        render_login()
        return

    model = AlphaFold3Model()
    job_manager = JobManager(settings=settings, model=model, user=user)
    slurm = SlurmClient()

    snapshot = slurm.get_snapshot()
    render_sidebar(settings=settings, active_job_count=snapshot.job_count, user=user)

    admin_mode = bool(st.session_state.get("show_admin", False))
    if admin_mode:
        st.session_state["show_admin"] = False
        render_admin()
        return

    tab1, tab2, tab3, tab4 = st.tabs(["🧬 New Fold", "📄 JSON Upload", "📚 Batch CSV", "📂 My Jobs"])
    with tab1:
        render_new_fold(job_manager=job_manager)
    with tab2:
        render_json_upload(job_manager=job_manager)
    with tab3:
        render_batch_csv(job_manager=job_manager)
    with tab4:
        render_my_jobs(job_manager=job_manager, slurm=slurm)


if __name__ == "__main__":
    main()


