import streamlit as st
import subprocess
import os
import json
import shutil
import pandas as pd
import time
from datetime import datetime
import glob
import py3Dmol
from stmol import showmol

# --- CONFIGURATION ---
BASE_DIR = "/af3_raid0/web_jobs"
AF3_RUN_CMD = "/usr/local/bin/af3run"
LOGO_FILE = "logo.png"

st.set_page_config(page_title="BrineyLab AF3", layout="wide", page_icon="🧬")

# --- CSS ---
st.markdown("""
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
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def get_active_slurm_jobs():
    try:
        output = subprocess.check_output(["squeue", "--noheader", "--format=%j"], text=True)
        return set(output.strip().split())
    except: return set()

def get_job_status(job_dir, active_jobs):
    # PRIORITY 1: Is it in the Queue? (Ignore logs if running)
    out_logs = glob.glob(os.path.join(job_dir, "logs", "*.out"))
    if out_logs:
        for log in out_logs:
            try:
                with open(log, 'r') as f:
                    head = f.read(500) # Read just the header
                    if "Job ID:" in head:
                        job_id = head.split("Job ID:")[1].split("\n")[0].strip()
                        if job_id in active_jobs: return "running"
            except: pass

    # PRIORITY 2: Did it finish?
    if glob.glob(os.path.join(job_dir, "**", "*model.cif"), recursive=True): return "success"
    
    # PRIORITY 3: Did it actually fail?
    err_logs = glob.glob(os.path.join(job_dir, "logs", "*.err"))
    for err_file in err_logs:
        if os.path.getsize(err_file) > 0:
            with open(err_file, 'r') as f:
                content = f.read().lower()
                # Only flag as failed if we see fatal python errors, ignore warnings
                if "traceback" in content or "valueerror" in content or "critical" in content:
                    return "failed"

    return "crashed"

def render_mol(cif_file, width=500, height=400):
    with open(cif_file) as f: cif_data = f.read()
    view = py3Dmol.view(width=width, height=height)
    view.addModel(cif_data, 'cif')
    view.setStyle({'cartoon': {'color': 'spectrum'}})
    view.zoomTo()
    return view

if 'entities' not in st.session_state: st.session_state.entities = []

# --- SIDEBAR ---
with st.sidebar:
    if os.path.exists(LOGO_FILE): st.image(LOGO_FILE, use_container_width=True)
    else: st.title("BrineyLab")
    
    st.markdown("### AlphaFold 3 Server")
    st.markdown("---")
    
    active_jobs = get_active_slurm_jobs()
    st.metric("Cluster Activity", f"{len(active_jobs)} Jobs Running")
    if st.button("🔄 Refresh Status"): st.rerun()
    
    st.markdown("---")
    
    st.markdown("""
    <div class="disclaimer">
    <b>⚠️ Terms of Use</b><br><br>
    This server is for <b>non-commercial use only</b>.<br><br>
    Outputs <b>cannot</b> be used:<br>
    • In docking or screening tools<br>
    • To train ML models for structure prediction<br><br>
    <b>Citation:</b><br>
    <i>Abramson, J et al. Accurate structure prediction of biomolecular interactions with AlphaFold 3. Nature (2024).</i>
    </div>
    """, unsafe_allow_html=True)

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["🧬 New Fold", "📄 JSON Upload", "📚 Batch CSV", "📂 My Jobs"])

# TAB 1: INTERACTIVE
with tab1:
    st.header("Start a New Folding Job")
    st.caption("By submitting, you agree to the Terms of Use listed in the sidebar.")
    col_c, col_i = st.columns([1, 2])
    
    with col_c:
        job_name = st.text_input("Job Name", f"Fold_{datetime.now().strftime('%Y%m%d')}")
        model_seeds = st.number_input("Seed", 1, 100, 1)
        st.markdown("### Molecules")
        if st.button("➕ Protein Chain", use_container_width=True): 
            st.session_state.entities.append({"type":"Protein","id":chr(65+len(st.session_state.entities)),"name":f"Protein Chain {chr(65+len(st.session_state.entities))}","seq":"","copies":1})
        if st.button("➕ DNA Sequence", use_container_width=True): 
            st.session_state.entities.append({"type":"DNA","id":chr(65+len(st.session_state.entities)),"name":f"DNA Chain {chr(65+len(st.session_state.entities))}","seq":"","copies":1})
        if st.button("➕ RNA Sequence", use_container_width=True): 
            st.session_state.entities.append({"type":"RNA","id":chr(65+len(st.session_state.entities)),"name":f"RNA Chain {chr(65+len(st.session_state.entities))}","seq":"","copies":1})
        if st.button("🗑️ Clear All", type="secondary", use_container_width=True): 
            st.session_state.entities = []; st.rerun()

    with col_i:
        if not st.session_state.entities: st.info("👈 Add molecules using the buttons on the left.")
        for idx, ent in enumerate(st.session_state.entities):
            if 'name' not in ent: ent['name'] = f"{ent['type']} Chain {ent['id']}"
            with st.container():
                st.markdown(f"""<div class="entity-box"><b>{ent['type']} Chain {ent['id']}</b></div>""", unsafe_allow_html=True)
                ent['name'] = st.text_input(f"Label", value=ent['name'], key=f"n_{idx}", label_visibility="collapsed")
                c1, c2 = st.columns([4,1])
                ent['seq'] = c1.text_area("Sequence", ent['seq'], key=f"s_{idx}", height=70, label_visibility="collapsed", placeholder="Sequence string...")
                ent['copies'] = c2.number_input("Copies", 1, 50, ent['copies'], key=f"c_{idx}")
        
        if st.session_state.entities:
            st.markdown("---")
            if st.button("🚀 Launch AlphaFold 3", type="primary", use_container_width=True):
                clean_name = "".join(x for x in job_name if x.isalnum() or x in "_-")
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                job_dir = os.path.join(BASE_DIR, f"{ts}_{clean_name}")
                os.makedirs(job_dir, exist_ok=True)
                seqs = []
                for ent in st.session_state.entities:
                    ids = [chr(ord(ent['id'])+i) for i in range(ent['copies'])]
                    key = ent['type'].lower() if ent['type'] != "Protein" else "protein"
                    seqs.append({key: {"id": ids, "sequence": ent['seq'].strip()}})
                with open(os.path.join(job_dir, "input.json"), "w") as f:
                    json.dump({"name": clean_name, "dialect": "alphafold3", "version": 1, "modelSeeds": [model_seeds], "sequences": seqs}, f, indent=2)
                subprocess.Popen([AF3_RUN_CMD, os.path.join(job_dir, "input.json"), job_dir])
                st.toast(f"Job {clean_name} submitted successfully!")
                st.session_state.entities = []
                time.sleep(1)
                st.rerun()

# TAB 2: JSON
with tab2:
    st.header("Upload JSON")
    st.caption("Ensure your usage complies with the non-commercial license.")
    up_json = st.file_uploader("Upload an input.json file", type="json")
    if up_json and st.button("🚀 Launch JSON Job", type="primary"):
        data = json.load(up_json)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.splitext(up_json.name)[0]
        jd = os.path.join(BASE_DIR, f"{ts}_{name}")
        os.makedirs(jd, exist_ok=True)
        with open(os.path.join(jd, "input.json"), "w") as f: json.dump(data, f, indent=2)
        subprocess.Popen([AF3_RUN_CMD, os.path.join(jd, "input.json"), jd])
        st.success("Submitted!")

# TAB 3: BATCH
with tab3:
    st.header("Batch CSV")
    st.caption("Batch processing for high-throughput non-commercial research.")
    up_csv = st.file_uploader("Upload CSV (columns: name, sequence)", type="csv")
    if up_csv:
        df = pd.read_csv(up_csv)
        st.dataframe(df.head())
        if st.button(f"🚀 Launch Batch ({len(df)} proteins)", type="primary"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = os.path.splitext(up_csv.name)[0]
            jd = os.path.join(BASE_DIR, f"{ts}_BATCH_{name}")
            os.makedirs(jd, exist_ok=True)
            json_list = []
            for i, row in df.iterrows():
                json_list.append({
                    "name": str(row['name']), 
                    "modelSeeds": [1],
                    "sequences": [{"protein": {"id": ["A"], "sequence": str(row['sequence']).strip()}}]
                })
            with open(os.path.join(jd, "input.json"), "w") as f: json.dump(json_list, f, indent=2)
            subprocess.Popen([AF3_RUN_CMD, os.path.join(jd, "input.json"), jd])
            st.success("Batch Submitted!")

# TAB 4: MY JOBS
with tab4:
    c1, c2 = st.columns([3, 1])
    with c1: st.header("Job Status")
    with c2: 
        if st.button("🔄 Refresh List"): st.rerun()
    if os.path.exists(BASE_DIR):
        jobs = sorted(os.listdir(BASE_DIR), reverse=True)
        active_slurm = get_active_slurm_jobs()
        for job in jobs:
            jp = os.path.join(BASE_DIR, job)
            if not os.path.isdir(jp): continue
            status = get_job_status(jp, active_slurm)
            
            icon = "✅" if status=="success" else "⏳" if status=="running" else "❌" if status=="failed" else "💀"
            
            with st.expander(f"{icon} {job}", expanded=(status=='running')):
                col_status, col_actions, col_viz = st.columns([1, 1, 2])
                with col_status:
                    st.write(f"**Status:** {status.upper()}")
                    if status == "success":
                        zp = f"/tmp/{job}"
                        shutil.make_archive(zp, 'zip', jp)
                        with open(f"{zp}.zip", "rb") as f: st.download_button("⬇️ ZIP", f, f"{job}.zip", use_container_width=True)
                with col_actions:
                    if status != "running":
                        if st.button("🔄 Resubmit", key=f"re_{job}", use_container_width=True):
                            try:
                                old_in = os.path.join(jp, "input.json")
                                if os.path.exists(old_in):
                                    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                                    nm = "_".join(job.split("_")[2:])
                                    njd = os.path.join(BASE_DIR, f"{ts}_{nm}_Re")
                                    os.makedirs(njd, exist_ok=True)
                                    shutil.copy(old_in, os.path.join(njd, "input.json"))
                                    subprocess.Popen([AF3_RUN_CMD, os.path.join(njd, "input.json"), njd])
                                    st.toast("Resubmitted!"); time.sleep(1); st.rerun()
                            except: st.error("Error")
                        if st.button("🗑️ Delete", key=f"del_{job}", type="secondary", use_container_width=True):
                            shutil.rmtree(jp); st.rerun()
                    else: st.info("Active in Slurm")
                with col_viz:
                    if status == "success":
                         cifs = glob.glob(os.path.join(jp, "**", "*model.cif"), recursive=True)
                         if cifs:
                             view = render_mol(cifs[0], width=500, height=350)
                             showmol(view, height=350, width=500)
                    elif status in ["failed", "crashed"]:
                        st.caption("Error Logs")
                        errs = glob.glob(os.path.join(jp, "logs", "*.err"))
                        if errs:
                            with open(errs[0]) as f: st.code(f.read())
