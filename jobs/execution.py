from __future__ import annotations

import os
import shlex
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from console.models import RunnerConfig
from jobs.fs import ensure_dir, write_text
from jobs.models import Job, JobAttempt
from runners import get_runner


DOCKER_RUN_SENTINEL = "docker run --rm --gpus all"
LOCAL_STARTUP_GRACE_SECONDS = 5


@dataclass(frozen=True)
class AttemptRuntimePaths:
    root: Path
    runner_script: Path
    launcher_script: Path
    pid_file: Path
    container_file: Path
    exit_code_file: Path
    finished_at_file: Path
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True)
class ContainerState:
    status: str
    exit_code: int | None


def configured_gpu_slots() -> list[int]:
    raw_slots = getattr(settings, "GPU_SLOTS", [])
    if isinstance(raw_slots, str):
        slots = []
        for chunk in raw_slots.split(","):
            chunk = chunk.strip()
            if chunk:
                slots.append(int(chunk))
        return slots
    return [int(slot) for slot in raw_slots]


def local_attempt_paths(job: Job, attempt: JobAttempt) -> AttemptRuntimePaths:
    root = job.workdir / "attempts" / str(attempt.attempt_number)
    return AttemptRuntimePaths(
        root=root,
        runner_script=root / "runner.sh",
        launcher_script=root / "launch.sh",
        pid_file=root / "launcher.pid",
        container_file=root / "container.id",
        exit_code_file=root / "exit_code.txt",
        finished_at_file=root / "finished_at.txt",
        stdout_path=root / "stdout.log",
        stderr_path=root / "stderr.log",
    )


def job_uses_local_executor(job: Job) -> bool:
    attempt = job.attempts.order_by("-attempt_number").first()
    if attempt is None:
        return True

    if (
        attempt.container_id
        or attempt.gpu_index is not None
        or attempt.stdout_path
        or attempt.stderr_path
        or attempt.scheduler_job_id.startswith("local:")
    ):
        return True

    return local_attempt_paths(job, attempt).root.exists()


def run_local_worker_iteration() -> None:
    executor = LocalDockerExecutor()
    executor.reconcile()
    executor.launch_next()


class LocalDockerExecutor:
    def __init__(self, *, gpu_slots: list[int] | None = None):
        self.gpu_slots = list(gpu_slots if gpu_slots is not None else configured_gpu_slots())

    def reconcile(self) -> None:
        qs = Job.objects.filter(status=Job.Status.RUNNING).order_by("queued_at")
        for job in qs.iterator():
            self._reconcile_job(job)

    def launch_next(self) -> None:
        free_slots = self._free_gpu_slots()
        if not free_slots:
            return

        queued_jobs = list(
            Job.objects.filter(status=Job.Status.PENDING)
            .annotate(
                priority_rank=Case(
                    When(priority_tier_snapshot="priority", then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("priority_rank", "queued_at", "created_at", "id")[: len(free_slots)]
        )

        for gpu_index, job in zip(free_slots, queued_jobs):
            attempt = self._current_attempt(job)
            self._launch_attempt(job, attempt, gpu_index)

    def cancel(self, job: Job) -> None:
        attempt = self._current_attempt(job)
        paths = local_attempt_paths(job, attempt)
        container_id = attempt.container_id or _read_text(paths.container_file)
        if container_id:
            subprocess.run(
                ["docker", "stop", "--time", "10", container_id],
                capture_output=True,
                text=True,
            )
            return

        pid = _read_pid(paths.pid_file)
        if pid is None:
            return

        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            return

    def _free_gpu_slots(self) -> list[int]:
        used_slots = set(
            JobAttempt.objects.filter(
                job__status=Job.Status.RUNNING,
                gpu_index__isnull=False,
            ).values_list("gpu_index", flat=True)
        )
        return [slot for slot in self.gpu_slots if slot not in used_slots]

    def _launch_attempt(self, job: Job, attempt: JobAttempt, gpu_index: int) -> None:
        from jobs.services import sync_job_status

        paths = local_attempt_paths(job, attempt)
        ensure_dir(paths.root)
        ensure_dir(job.workdir / "output")

        attempt.scheduler_job_id = ""
        attempt.container_id = ""
        attempt.gpu_index = gpu_index
        attempt.stdout_path = str(paths.stdout_path)
        attempt.stderr_path = str(paths.stderr_path)
        attempt.failure_summary = ""
        attempt.save(
            update_fields=[
                "scheduler_job_id",
                "container_id",
                "gpu_index",
                "stdout_path",
                "stderr_path",
                "failure_summary",
                "updated_at",
            ]
        )

        try:
            runner = get_runner(job.runner)
            config = RunnerConfig.get_config(job.runner)
            runner_script = self._build_runner_script(job, attempt, runner.build_script(job, config=config), gpu_index)
            write_text(paths.runner_script, runner_script)
            _make_executable(paths.runner_script)

            launcher_script = self._build_launcher_script(job, attempt)
            write_text(paths.launcher_script, launcher_script)
            _make_executable(paths.launcher_script)

            process = subprocess.Popen(
                [str(paths.launcher_script)],
                cwd=str(job.workdir),
                env=os.environ.copy(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            write_text(paths.pid_file, str(process.pid))
        except Exception as exc:
            sync_job_status(
                job,
                Job.Status.FAILED,
                when=timezone.now(),
                error_message=f"Local executor launch failed: {exc}",
            )
            return

        attempt.scheduler_job_id = f"local:{process.pid}"
        attempt.save(update_fields=["scheduler_job_id", "updated_at"])
        sync_job_status(job, Job.Status.RUNNING, when=timezone.now())

    def _build_runner_script(
        self,
        job: Job,
        attempt: JobAttempt,
        script_content: str,
        gpu_index: int,
    ) -> str:
        paths = local_attempt_paths(job, attempt)
        rewritten = script_content
        rewritten = rewritten.replace(
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "-e NVIDIA_VISIBLE_DEVICES=all",
        )
        rewritten = rewritten.replace(
            "-e CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}",
            "-e CUDA_VISIBLE_DEVICES=0",
        )

        docker_prefix = (
            "docker run --rm "
            f"--cidfile {shlex.quote(str(paths.container_file))} "
            f"--label fold.job_id={job.id} "
            f"--label fold.attempt_number={attempt.attempt_number} "
            f"--name fold-job-{job.id}-a{attempt.attempt_number} "
            f"--gpus device={gpu_index}"
        )
        return rewritten.replace(DOCKER_RUN_SENTINEL, docker_prefix)

    def _build_launcher_script(self, job: Job, attempt: JobAttempt) -> str:
        paths = local_attempt_paths(job, attempt)
        attempt_root = shlex.quote(str(paths.root))
        runner_script = shlex.quote(str(paths.runner_script))
        stdout_path = shlex.quote(str(paths.stdout_path))
        stderr_path = shlex.quote(str(paths.stderr_path))
        pid_file = shlex.quote(str(paths.pid_file))
        exit_code_file = shlex.quote(str(paths.exit_code_file))
        finished_at_file = shlex.quote(str(paths.finished_at_file))
        output_dir = shlex.quote(str(job.workdir / "output"))

        return f"""#!/bin/bash
set -uo pipefail
umask 000

mkdir -p {attempt_root} {output_dir}
printf '%s\\n' "$$" > {pid_file}

{runner_script} > {stdout_path} 2> {stderr_path}
rc=$?

printf '%s\\n' "$rc" > {exit_code_file}
date -u +"%Y-%m-%dT%H:%M:%SZ" > {finished_at_file}

chmod -R a+rwX {attempt_root} {output_dir} 2>/dev/null || true
exit "$rc"
"""

    def _reconcile_job(self, job: Job) -> None:
        from jobs.services import sync_job_status

        attempt = self._current_attempt(job)
        paths = local_attempt_paths(job, attempt)
        updated_fields: list[str] = []

        container_id = _read_text(paths.container_file)
        if container_id and attempt.container_id != container_id:
            attempt.container_id = container_id
            updated_fields.append("container_id")

        if attempt.stdout_path != str(paths.stdout_path):
            attempt.stdout_path = str(paths.stdout_path)
            updated_fields.append("stdout_path")
        if attempt.stderr_path != str(paths.stderr_path):
            attempt.stderr_path = str(paths.stderr_path)
            updated_fields.append("stderr_path")

        if updated_fields:
            attempt.save(update_fields=updated_fields + ["updated_at"])

        exit_code = _read_exit_code(paths.exit_code_file)
        if exit_code is not None:
            finished_at = _read_finished_at(paths.finished_at_file) or timezone.now()
            terminal_status = Job.Status.COMPLETED if exit_code == 0 else Job.Status.FAILED
            error_message = ""
            if exit_code != 0:
                error_message = _build_failure_summary(exit_code, paths.stderr_path)
            sync_job_status(
                job,
                terminal_status,
                when=finished_at,
                error_message=error_message,
                exit_code=exit_code,
            )
            return

        now = timezone.now()
        if attempt.started_at and (now - attempt.started_at).total_seconds() < LOCAL_STARTUP_GRACE_SECONDS:
            return

        pid = _read_pid(paths.pid_file)
        if pid is not None and _process_is_running(pid):
            return

        state = None
        container_id = attempt.container_id or container_id
        if container_id:
            state = _inspect_container(container_id)
            if state and state.status == "running":
                return
            if state and state.status == "exited":
                exit_code = 1 if state.exit_code is None else state.exit_code
                write_text(paths.exit_code_file, str(exit_code))
                sync_job_status(
                    job,
                    Job.Status.COMPLETED if exit_code == 0 else Job.Status.FAILED,
                    when=now,
                    error_message="" if exit_code == 0 else _build_failure_summary(exit_code, paths.stderr_path),
                    exit_code=exit_code,
                )
                return

        sync_job_status(
            job,
            Job.Status.FAILED,
            when=now,
            error_message=(
                "Local executor lost track of the launcher before it recorded "
                "a terminal state."
            ),
        )

    def _current_attempt(self, job: Job) -> JobAttempt:
        attempt = job.attempts.order_by("-attempt_number").first()
        if attempt is not None:
            return attempt

        attempt = JobAttempt.objects.create(
            job=job,
            attempt_number=max(1, job.attempt_count or 1),
            status=job.status or Job.Status.PENDING,
        )
        if job.attempt_count != attempt.attempt_number:
            job.attempt_count = attempt.attempt_number
            job.save(update_fields=["attempt_count"])
        return attempt


def _build_failure_summary(exit_code: int, stderr_path: Path) -> str:
    stderr_tail = ""
    if stderr_path.exists():
        lines = stderr_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines:
            stderr_tail = lines[-1].strip()

    message = f"Local executor exited with code {exit_code}"
    if stderr_tail:
        return f"{message}: {stderr_tail[:300]}"
    return message


def _inspect_container(container_id: str) -> ContainerState | None:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}|{{.State.ExitCode}}", container_id],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    raw_status, _, raw_exit_code = result.stdout.strip().partition("|")
    exit_code = None
    if raw_exit_code.strip():
        try:
            exit_code = int(raw_exit_code.strip())
        except ValueError:
            exit_code = None
    return ContainerState(status=raw_status.strip(), exit_code=exit_code)


def _process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _read_pid(path: Path) -> int | None:
    raw_value = _read_text(path)
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _read_exit_code(path: Path) -> int | None:
    raw_value = _read_text(path)
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _read_finished_at(path: Path):
    raw_value = _read_text(path)
    if not raw_value:
        return None
    return parse_datetime(raw_value)


def _make_executable(path: Path) -> None:
    try:
        path.chmod(0o775)
    except OSError:
        pass
