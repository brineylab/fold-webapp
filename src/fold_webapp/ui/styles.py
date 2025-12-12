from __future__ import annotations

import streamlit as st


def configure_page() -> None:
    st.set_page_config(page_title="BrineyLab AF3", layout="wide", page_icon="🧬")


def apply_global_styles() -> None:
    st.markdown(
        """
<style>
    .block-container {padding-top: 2rem;}
    div[data-testid="stForm"] {
        border: 1px solid #dadce0;
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3);
        border-radius: 8px;
        padding: 2rem;
        background-color: white;
    }
    .entity-box {
        border: 1px solid #dadce0;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        background-color: #f8f9fa;
    }
    .disclaimer {
        font-size: 0.85rem;
        color: #5f6368;
        background-color: #f1f3f4;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #d93025;
        margin-top: 20px;
    }
</style>
""",
        unsafe_allow_html=True,
    )


