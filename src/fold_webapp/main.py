from __future__ import annotations

import streamlit as st

from fold_webapp.config import get_settings
from fold_webapp.models import AlphaFold3Model
from fold_webapp.services import JobManager, SlurmClient
from fold_webapp.ui.sidebar import render_sidebar
from fold_webapp.ui.styles import apply_global_styles, configure_page
from fold_webapp.ui.pages import render_batch_csv, render_json_upload, render_my_jobs, render_new_fold


def main() -> None:
    settings = get_settings()
    configure_page()
    apply_global_styles()

    model = AlphaFold3Model()
    job_manager = JobManager(settings=settings, model=model)
    slurm = SlurmClient()

    snapshot = slurm.get_snapshot()
    render_sidebar(settings=settings, active_job_count=snapshot.job_count)

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


