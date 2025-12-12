from __future__ import annotations

from pathlib import Path

import py3Dmol
from stmol import showmol


def render_mol(cif_file: Path, *, width: int = 500, height: int = 400):
    cif_data = cif_file.read_text(errors="ignore")
    view = py3Dmol.view(width=width, height=height)
    view.addModel(cif_data, "cif")
    view.setStyle({"cartoon": {"color": "spectrum"}})
    view.zoomTo()
    return view


def show_structure(cif_file: Path, *, width: int = 500, height: int = 350) -> None:
    view = render_mol(cif_file, width=width, height=height)
    showmol(view, height=height, width=width)


