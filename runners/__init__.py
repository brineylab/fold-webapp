from __future__ import annotations

from abc import ABC, abstractmethod


class Runner(ABC):
    key: str
    name: str

    @abstractmethod
    def build_script(self, job, config=None) -> str:
        """Generate sbatch script content for a Job.

        Args:
            job: The Job instance.
            config: Optional RunnerConfig with SLURM resource settings
                and container overrides.
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


