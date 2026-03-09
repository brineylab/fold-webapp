from __future__ import annotations

from abc import ABC, abstractmethod
import shlex


class Runner(ABC):
    key: str
    name: str

    @abstractmethod
    def build_script(self, job, config=None) -> str:
        """Generate the shell script content for a Job.

        Args:
            job: The Job instance.
            config: Optional RunnerConfig with a container image override.
        """
        raise NotImplementedError

    def validate(self, sequences: str, params: dict) -> list[str]:
        """Return list of validation errors, empty if valid."""
        return []


_RUNNERS: dict[str, Runner] = {}


def register(cls):
    instance = cls()
    if not getattr(instance, "key", None):
        raise ValueError(f"Runner {cls.__name__} missing key")
    _RUNNERS[instance.key] = instance
    return cls


def get_runner(key: str) -> Runner:
    try:
        return _RUNNERS[key]
    except KeyError as e:
        raise ValueError(f"Unknown runner: {key}") from e


def all_runners() -> list[Runner]:
    return list(_RUNNERS.values())


def optional_cuda_visible_devices_env_setup() -> str:
    return """cuda_visible_devices_flag=""
if [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then
  cuda_visible_devices_flag="-e CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}"
fi"""


def docker_resource_flags(
    *,
    shm_size: str | None = None,
    ipc_mode: str | None = None,
) -> list[str]:
    flags: list[str] = []
    if shm_size:
        value = str(shm_size).strip()
        if value:
            flags.append(f"--shm-size {shlex.quote(value)}")
    if ipc_mode:
        value = str(ipc_mode).strip()
        if value:
            flags.append(f"--ipc {shlex.quote(value)}")
    return flags
