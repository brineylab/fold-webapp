from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from fold_webapp.services import JobManager


def render_batch_csv(*, job_manager: JobManager) -> None:
    st.header("Batch CSV")
    st.caption("Batch processing for high-throughput non-commercial research.")

    up_csv = st.file_uploader("Upload CSV (columns: name, sequence)", type="csv")
    if not up_csv:
        return

    df = pd.read_csv(up_csv)
    st.dataframe(df.head())

    if st.button(f"🚀 Launch Batch ({len(df)} proteins)", type="primary"):
        batch_name = os.path.splitext(up_csv.name)[0]
        json_list: list[dict] = []
        for _, row in df.iterrows():
            json_list.append(
                {
                    "name": str(row["name"]),
                    "modelSeeds": [1],
                    "sequences": [
                        {"protein": {"id": ["A"], "sequence": str(row["sequence"]).strip()}}
                    ],
                }
            )
        job_manager.submit_batch_json_list(batch_name=batch_name, json_list=json_list)
        st.success("Batch Submitted!")


