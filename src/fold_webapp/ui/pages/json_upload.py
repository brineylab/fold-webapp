from __future__ import annotations

import json

import streamlit as st

from fold_webapp.services import JobManager


def render_json_upload(*, job_manager: JobManager) -> None:
    st.header("Upload JSON")
    st.caption("Ensure your usage complies with the non-commercial license.")

    up_json = st.file_uploader("Upload an input.json file", type="json")
    if up_json and st.button("🚀 Launch JSON Job", type="primary"):
        data = json.load(up_json)
        job_manager.submit_uploaded_json(uploaded_name=up_json.name, data=data)
        st.success("Submitted!")


