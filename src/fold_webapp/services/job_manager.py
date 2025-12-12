from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from fold_webapp.config import Settings
from fold_webapp.models.base import PredictionModel


class JobStatus(str, Enum):
    running = "running"
    success = "success"
    failed = "failed"
    crashed = "crashed"


@dataclass(frozen=True)
class JobManager:
    settings: Settings
    model: PredictionModel

    def list_jobs(self) -> list[str]:
        base = Path(self.settings.base_dir)
        if not base.exists():
            return []
        return sorted([p.name for p in base.iterdir() if p.is_dir()], reverse=True)

    def get_job_dir(self, job_name: str) -> Path:
        return Path(self.settings.base_dir) / job_name

    def sanitize_job_name(self, job_name: str) -> str:
        return "".join(ch for ch in job_name if ch.isalnum() or ch in "_-")

    def create_job_dir(self, job_name: str) -> Path:
        clean = self.sanitize_job_name(job_name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = Path(self.settings.base_dir) / f"{ts}_{clean}"
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir

    def write_input_json(self, job_dir: Path, payload: dict) -> Path:
        input_path = job_dir / "input.json"
        input_path.write_text(json.dumps(payload, indent=2))
        return input_path

    def submit_job_dir(self, job_dir: Path) -> None:
        input_path = job_dir / "input.json"
        cmd = self.model.get_run_command(input_path=input_path, output_dir=job_dir)
        subprocess.Popen(cmd)

    def submit_new_job(self, *, job_name: str, model_seed: int, entities: list) -> Path:
        job_dir = self.create_job_dir(job_name)
        payload = self.model.prepare_input(
            job_name=self.sanitize_job_name(job_name), model_seed=model_seed, entities=entities
        )
        self.write_input_json(job_dir, payload)
        self.submit_job_dir(job_dir)
        return job_dir

    def submit_uploaded_json(self, *, uploaded_name: str, data: dict) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = os.path.splitext(uploaded_name)[0]
        job_dir = Path(self.settings.base_dir) / f"{ts}_{name}"
        job_dir.mkdir(parents=True, exist_ok=True)
        self.write_input_json(job_dir, data)
        self.submit_job_dir(job_dir)
        return job_dir

    def submit_batch_json_list(self, *, batch_name: str, json_list: list[dict]) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        job_dir = Path(self.settings.base_dir) / f"{ts}_BATCH_{batch_name}"
        job_dir.mkdir(parents=True, exist_ok=True)
        self.write_input_json(job_dir, json_list)
        self.submit_job_dir(job_dir)
        return job_dir

    def get_status(self, job_dir: Path, active_job_keys: set[str]) -> JobStatus:
        # PRIORITY 1: queued/running (ignore logs if active)
        out_logs = list((job_dir / "logs").glob("*.out")) if (job_dir / "logs").exists() else []
        for log in out_logs:
            try:
                head = log.read_text(errors="ignore")[:500]
            except Exception:
                continue
            if "Job ID:" in head:
                job_id = head.split("Job ID:")[1].split("\n")[0].strip()
                if job_id in active_job_keys:
                    return JobStatus.running

        # PRIORITY 2: finished successfully
        if self.model.find_primary_structure_file(job_dir=job_dir) is not None:
            return JobStatus.success

        # PRIORITY 3: actual failure (ignore warnings)
        err_logs = list((job_dir / "logs").glob("*.err")) if (job_dir / "logs").exists() else []
        for err_file in err_logs:
            try:
                if err_file.stat().st_size <= 0:
                    continue
                content = err_file.read_text(errors="ignore").lower()
            except Exception:
                continue
            if "traceback" in content or "valueerror" in content or "critical" in content:
                return JobStatus.failed

        return JobStatus.crashed

    def make_zip(self, job_dir: Path) -> Path:
        # Streamlit download_button wants a file; match old behavior using /tmp
        zip_base = Path("/tmp") / job_dir.name
        archive = shutil.make_archive(str(zip_base), "zip", str(job_dir))
        return Path(archive)

    def resubmit(self, job_dir: Path) -> Path | None:
        old_in = job_dir / "input.json"
        if not old_in.exists():
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts = job_dir.name.split("_")
        # old naming is "{ts}_{clean_name}" so keep best-effort original user name
        nm = "_".join(parts[2:]) if len(parts) > 2 else job_dir.name
        new_dir = Path(self.settings.base_dir) / f"{ts}_{nm}_Re"
        new_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(old_in, new_dir / "input.json")
        self.submit_job_dir(new_dir)
        return new_dir

    def delete(self, job_dir: Path) -> None:
        shutil.rmtree(job_dir, ignore_errors=True)


