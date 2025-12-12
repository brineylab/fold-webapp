"""Compatibility entrypoint.

Historically this repo ran via:

  streamlit run af3_web_app.py

The implementation now lives in `fold_webapp/main.py`, but we keep this file
to preserve existing deploy/run scripts.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if _SRC.exists():
    sys.path.insert(0, str(_SRC))

from fold_webapp.main import main


main()
