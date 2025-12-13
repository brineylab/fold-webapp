#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    os.chdir(repo_root)
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    cfg = Config(str(repo_root / "alembic.ini"))
    # Make sure alembic env can import from src/
    cfg.set_main_option("prepend_sys_path", str(src_dir))

    command.upgrade(cfg, "head")
    print("Database initialized (alembic upgrade head).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


