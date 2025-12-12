from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

from fold_webapp.schemas import Entity, EntityType
from fold_webapp.services import JobManager


def _ensure_entities_state() -> None:
    if "entities" not in st.session_state:
        st.session_state.entities = []


def _next_entity_id() -> str:
    _ensure_entities_state()
    return chr(65 + len(st.session_state.entities))


def render_new_fold(*, job_manager: JobManager) -> None:
    _ensure_entities_state()

    st.header("Start a New Folding Job")
    st.caption("By submitting, you agree to the Terms of Use listed in the sidebar.")
    col_c, col_i = st.columns([1, 2])

    with col_c:
        job_name = st.text_input("Job Name", f"Fold_{datetime.now().strftime('%Y%m%d')}")
        model_seed = st.number_input("Seed", 1, 100, 1)
        st.markdown("### Molecules")

        if st.button("➕ Protein Chain", use_container_width=True):
            eid = _next_entity_id()
            st.session_state.entities.append(
                {"type": "Protein", "id": eid, "name": f"Protein Chain {eid}", "seq": "", "copies": 1}
            )
        if st.button("➕ DNA Sequence", use_container_width=True):
            eid = _next_entity_id()
            st.session_state.entities.append(
                {"type": "DNA", "id": eid, "name": f"DNA Chain {eid}", "seq": "", "copies": 1}
            )
        if st.button("➕ RNA Sequence", use_container_width=True):
            eid = _next_entity_id()
            st.session_state.entities.append(
                {"type": "RNA", "id": eid, "name": f"RNA Chain {eid}", "seq": "", "copies": 1}
            )
        if st.button("🗑️ Clear All", type="secondary", use_container_width=True):
            st.session_state.entities = []
            st.rerun()

    with col_i:
        if not st.session_state.entities:
            st.info("👈 Add molecules using the buttons on the left.")

        entities: list[Entity] = []
        for idx, ent in enumerate(st.session_state.entities):
            if "name" not in ent:
                ent["name"] = f"{ent['type']} Chain {ent['id']}"

            st.markdown(
                f"""<div class="entity-box"><b>{ent['type']} Chain {ent['id']}</b></div>""",
                unsafe_allow_html=True,
            )
            ent["name"] = st.text_input(
                "Label", value=ent["name"], key=f"n_{idx}", label_visibility="collapsed"
            )
            c1, c2 = st.columns([4, 1])
            ent["seq"] = c1.text_area(
                "Sequence",
                ent.get("seq", ""),
                key=f"s_{idx}",
                height=70,
                label_visibility="collapsed",
                placeholder="Sequence string...",
            )
            ent["copies"] = c2.number_input("Copies", 1, 50, int(ent.get("copies", 1)), key=f"c_{idx}")

            entities.append(
                Entity(
                    type=EntityType(ent["type"]),
                    id=str(ent["id"]),
                    name=str(ent["name"]),
                    seq=str(ent.get("seq", "")),
                    copies=int(ent.get("copies", 1)),
                )
            )

        if st.session_state.entities:
            st.markdown("---")
            if st.button("🚀 Launch AlphaFold 3", type="primary", use_container_width=True):
                job_manager.submit_new_job(job_name=job_name, model_seed=int(model_seed), entities=entities)
                st.toast("Job submitted successfully!")
                st.session_state.entities = []
                time.sleep(1)
                st.rerun()


