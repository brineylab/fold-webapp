from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from fold_webapp.services import JobManager, JobStatus, SlurmClient
from fold_webapp.ui.components import show_structure


def _show_error_logs(job_dir: Path) -> None:
    st.caption("Error Logs")
    errs = list((job_dir / "logs").glob("*.err")) if (job_dir / "logs").exists() else []
    if not errs:
        return
    try:
        st.code(errs[0].read_text(errors="ignore"))
    except Exception:
        st.code("Unable to read error log.")


def render_my_jobs(*, job_manager: JobManager, slurm: SlurmClient) -> None:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.header("Job Status")
    with c2:
        if st.button("🔄 Refresh List"):
            st.rerun()

    base = Path(job_manager.settings.base_dir)
    if not base.exists():
        st.info("No jobs directory found yet.")
        return

    jobs = job_manager.list_jobs()
    active_keys = slurm.get_snapshot().keys

    for job in jobs:
        if not job_manager.can_access_job(dir_name=job):
            continue
        job_dir = job_manager.get_job_dir(job)
        status = job_manager.get_status(job_dir, active_job_keys=active_keys)
        icon = (
            "✅"
            if status == JobStatus.success
            else "⏳"
            if status == JobStatus.running
            else "❌"
            if status == JobStatus.failed
            else "💀"
        )

        with st.expander(f"{icon} {job}", expanded=(status == JobStatus.running)):
            col_status, col_actions, col_viz = st.columns([1, 1, 2])

            with col_status:
                st.write(f"**Status:** {status.value.upper()}")
                if status == JobStatus.success:
                    try:
                        zip_path = job_manager.make_zip(job_dir)
                        with open(zip_path, "rb") as f:
                            st.download_button("⬇️ ZIP", f, f"{job}.zip", use_container_width=True)
                    except PermissionError:
                        st.error("Not authorized to download this job.")

            with col_actions:
                if status != JobStatus.running:
                    if st.button("🔄 Resubmit", key=f"re_{job}", use_container_width=True):
                        try:
                            job_manager.resubmit(job_dir)
                            st.toast("Resubmitted!")
                            time.sleep(1)
                            st.rerun()
                        except Exception:
                            st.error("Error")

                    if st.button(
                        "🗑️ Delete",
                        key=f"del_{job}",
                        type="secondary",
                        use_container_width=True,
                    ):
                        try:
                            job_manager.delete(job_dir)
                            st.rerun()
                        except PermissionError:
                            st.error("Not authorized to delete this job.")
                else:
                    st.info("Active in Slurm")

            with col_viz:
                if status == JobStatus.success:
                    cif = job_manager.model.find_primary_structure_file(job_dir=job_dir)
                    if cif is not None:
                        show_structure(cif, width=500, height=350)
                elif status in (JobStatus.failed, JobStatus.crashed):
                    _show_error_logs(job_dir)


