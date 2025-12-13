from __future__ import annotations

import streamlit as st


def configure_page() -> None:
    st.set_page_config(page_title="BrineyLab AF3", layout="wide", page_icon="🧬")


def apply_global_styles() -> None:
    # No custom theme toggle UI. Users can switch themes via Streamlit's built-in Settings → Theme.
    # To stay consistent with that, derive our "card" styling from Streamlit's theme CSS variables.
    st.markdown(
        """
<style>
    :root {
        /* Streamlit theme variables we rely on:
           --background-color
           --secondary-background-color
           --text-color
        */
        --fw_border: color-mix(in srgb, var(--text-color) 20%, transparent);
        --fw_surface: var(--secondary-background-color);
        --fw_surface_2: color-mix(
            in srgb,
            var(--secondary-background-color) 85%,
            var(--background-color)
        );
        --fw_muted: color-mix(in srgb, var(--text-color) 70%, transparent);
        --fw_danger: #d93025;
        --fw_shadow: 0 1px 2px 0 rgba(0,0,0,0.15);
    }

    /* Fallback for older browsers that don't support color-mix(). */
    @supports not (color-mix(in srgb, black 50%, white)) {
        :root {
            --fw_border: rgba(128,128,128,0.35);
            --fw_surface_2: var(--secondary-background-color);
            --fw_muted: rgba(128,128,128,0.9);
        }
    }

    .block-container {{padding-top: 2rem;}}

    /* Avoid forced light-mode colors; adapt via CSS variables. */
    div[data-testid="stForm"] {{
        border: 1px solid var(--fw_border);
        box-shadow: var(--fw_shadow);
        border-radius: 8px;
        padding: 2rem;
        background-color: var(--fw_surface);
    }}

    .entity-box {{
        border: 1px solid var(--fw_border);
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        background-color: var(--fw_surface_2);
    }}

    .disclaimer {{
        font-size: 0.85rem;
        color: var(--fw_muted);
        background-color: var(--fw_surface_2);
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid var(--fw_danger);
        margin-top: 20px;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


