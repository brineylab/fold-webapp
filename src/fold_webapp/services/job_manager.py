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
from fold_webapp.db import Job, PriorityGroup, User, UserRole, get_session
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
    user: User

    def list_jobs(self) -> list[str]:
        # Admins can see everything via list_all_jobs(); default to per-user.
        session = get_session()
        try:
            rows = session.query(Job).filter(Job.owner_id == int(self.user.id)).all()
            return sorted([j.dir_name for j in rows], reverse=True)
        finally:
            session.close()

    def list_all_jobs(self) -> list[str]:
        if self.user.role != UserRole.admin:
            return self.list_jobs()
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
        dir_name = f"{ts}_{clean}"
        job_dir = Path(self.settings.base_dir) / dir_name
        job_dir.mkdir(parents=True, exist_ok=True)

        session = get_session()
        try:
            session.add(
                Job(
                    owner_id=int(self.user.id),
                    dir_name=dir_name,
                    job_name=str(job_name),
                    slurm_job_id=None,
                )
            )
            session.commit()
        finally:
            session.close()

        return job_dir

    def write_input_json(self, job_dir: Path, payload: dict) -> Path:
        input_path = job_dir / "input.json"
        input_path.write_text(json.dumps(payload, indent=2))
        return input_path

    def submit_job_dir(self, job_dir: Path) -> str | None:
        input_path = job_dir / "input.json"
        job_id = self.model.submit_job(
            input_path=input_path,
            output_dir=job_dir,
            nice=self._slurm_nice_value(),
        )
        if job_id:
            session = get_session()
            try:
                row = session.query(Job).filter(Job.dir_name == job_dir.name).one_or_none()
                if row is not None:
                    row.slurm_job_id = str(job_id)
                    session.commit()
            finally:
                session.close()
        return job_id

    def _slurm_nice_value(self) -> int:
        mapping = {
            PriorityGroup.normal: int(self.settings.slurm_priority_normal),
            PriorityGroup.high: int(self.settings.slurm_priority_high),
            PriorityGroup.urgent: int(self.settings.slurm_priority_urgent),
        }
        return mapping.get(self.user.priority_group, int(self.settings.slurm_priority_normal))

    def can_access_job(self, *, dir_name: str) -> bool:
        if self.user.role == UserRole.admin:
            return True
        session = get_session()
        try:
            row = session.query(Job).filter(Job.dir_name == dir_name).one_or_none()
            return bool(row and row.owner_id == int(self.user.id))
        finally:
            session.close()

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
        dir_name = f"{ts}_{name}"
        job_dir = Path(self.settings.base_dir) / dir_name
        job_dir.mkdir(parents=True, exist_ok=True)
        session = get_session()
        try:
            session.add(
                Job(
                    owner_id=int(self.user.id),
                    dir_name=dir_name,
                    job_name=str(name),
                    slurm_job_id=None,
                )
            )
            session.commit()
        finally:
            session.close()
        self.write_input_json(job_dir, data)
        self.submit_job_dir(job_dir)
        return job_dir

    def submit_batch_json_list(self, *, batch_name: str, json_list: list[dict]) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{ts}_BATCH_{batch_name}"
        job_dir = Path(self.settings.base_dir) / dir_name
        job_dir.mkdir(parents=True, exist_ok=True)
        session = get_session()
        try:
            session.add(
                Job(
                    owner_id=int(self.user.id),
                    dir_name=dir_name,
                    job_name=str(batch_name),
                    slurm_job_id=None,
                )
            )
            session.commit()
        finally:
            session.close()
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
        if not self.can_access_job(dir_name=job_dir.name):
            raise PermissionError("Not authorized to access this job.")
        # Streamlit download_button wants a file; match old behavior using /tmp
        zip_base = Path("/tmp") / job_dir.name
        archive = shutil.make_archive(str(zip_base), "zip", str(job_dir))
        return Path(archive)

    def resubmit(self, job_dir: Path) -> Path | None:
        if not self.can_access_job(dir_name=job_dir.name):
            raise PermissionError("Not authorized to access this job.")
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
        session = get_session()
        try:
            session.add(
                Job(
                    owner_id=int(self.user.id),
                    dir_name=new_dir.name,
                    job_name=str(nm),
                    slurm_job_id=None,
                )
            )
            session.commit()
        finally:
            session.close()

        self.submit_job_dir(new_dir)
        return new_dir

    def delete(self, job_dir: Path) -> None:
        if not self.can_access_job(dir_name=job_dir.name):
            raise PermissionError("Not authorized to access this job.")
        shutil.rmtree(job_dir, ignore_errors=True)
        session = get_session()
        try:
            row = session.query(Job).filter(Job.dir_name == job_dir.name).one_or_none()
            if row is not None:
                session.delete(row)
                session.commit()
        finally:
            session.close()
