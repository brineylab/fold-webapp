from __future__ import annotations

from pathlib import Path


DIR_MODE = 0o777
FILE_MODE = 0o666


def ensure_dir(path: Path) -> Path:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        if current == current.parent:
            break
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    for created in reversed(missing):
        _chmod(created, DIR_MODE)
    _chmod(path, DIR_MODE)
    return path


def write_text(path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    ensure_dir(path.parent)
    path.write_text(content, encoding=encoding)
    _chmod(path, FILE_MODE)
    return path


def write_bytes(path: Path, content: bytes) -> Path:
    ensure_dir(path.parent)
    path.write_bytes(content)
    _chmod(path, FILE_MODE)
    return path


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass
