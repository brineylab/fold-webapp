from __future__ import annotations

from pathlib import Path

import streamlit as st

from fold_webapp.config import Settings


def render_sidebar(*, settings: Settings, active_job_count: int) -> None:
    with st.sidebar:
        logo_path = Path(settings.logo_file)
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.title("BrineyLab")

        st.markdown("### AlphaFold 3 Server")
        st.markdown("---")

        st.metric("Cluster Activity", f"{active_job_count} Jobs Running")
        if st.button("🔄 Refresh Status"):
            st.rerun()

        st.markdown("---")
        st.markdown(
            """
    <div class="disclaimer">
    <b>⚠️ Terms of Use</b><br><br>
    This server is for <b>non-commercial use only</b>.<br><br>
    Outputs <b>cannot</b> be used:<br>
    • In docking or screening tools<br>
    • To train ML models for structure prediction<br><br>
    <b>Citation:</b><br>
    <i>Abramson, J et al. Accurate structure prediction of biomolecular interactions with AlphaFold 3. Nature (2024).</i>
    </div>
    """,
            unsafe_allow_html=True,
        )


