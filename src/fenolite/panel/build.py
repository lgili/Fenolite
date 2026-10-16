# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A panel from its script's model and its board file: the layout, the checks, then the files of the asked
form (change c0173). Nothing is written to disk: ``fenolite panel`` plans and writes what this returns.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.core.errors import Issue
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.model.panel import Panel
from fenolite.panel.checks import check_panel
from fenolite.panel.layout import PanelLayout, layout


@dataclass(frozen=True, slots=True)
class PanelOutput:
    """The files of a panel by path relative to the output folder (empty when an error finding refused
    them), its layout, its findings, its form (``kicad``, ``flat`` or ``embedded``) and its score layer."""

    files: dict[str, bytes]
    layout: PanelLayout
    issues: tuple[Issue, ...]
    form: str
    score_layer: str | None = None
    board: Design | None = None
    notes: tuple[Issue, ...] = field(default=())

    @property
    def refused(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


def read_source(path: Path) -> tuple[Design, bytes]:
    """The design of the board file ``path`` (``.kicad_pcb`` or ``.PcbDoc``) and its bytes."""
    data = path.read_bytes()
    if path.suffix.lower() == ".pcbdoc":
        from fenolite.backends.altium.adapter import import_board
        from fenolite.backends.altium.read.pcb import read_pcbdoc

        design = import_board(read_pcbdoc(data), file=path.name, sha256=hashlib.sha256(data).hexdigest())
        return design, data
    from fenolite.backends.kicad.pcb import read_board

    return read_board(data.decode("utf-8"), file=path.name), data


def panel_json(panel: Panel, data: bytes) -> bytes:
    """The model panel with the digest of its board file, as canonical JSON."""
    source = dataclasses.replace(panel.source, sha256=hashlib.sha256(data).hexdigest())
    return canonical.dumps(dataclasses.replace(panel, source=source)).encode("utf-8")


def kicad_panel(panel: Panel, source: Path, *, target: int) -> PanelOutput:
    """The KiCad panel board of ``panel`` over the board file ``source``, for KiCad ``target``."""
    from fenolite.backends.kicad.pro import synthesize_project
    from fenolite.panel.kicad import footprint_files, panel_board_text, project_text

    board, data = read_source(source)
    laid = layout(panel, board)
    issues = check_panel(panel, laid, board)
    if any(i.severity == "error" for i in issues):
        return PanelOutput({}, laid, issues, "kicad", board=board)
    name = panel.name
    text, score_layer = panel_board_text(panel, laid, data.decode("utf-8"), target=target)
    files: dict[str, bytes] = {f"{name}.kicad_pcb": text.encode("utf-8")}
    files.update(footprint_files(panel, laid, target=target))
    sibling = source.with_suffix(".kicad_pro")

    def synthesize() -> str:
        from fenolite.backends.kicad.pcb import read_board

        return synthesize_project(read_board(text), target=target, board_name=name)

    files[f"{name}.kicad_pro"] = project_text(
        sibling.read_text(encoding="utf-8") if sibling.is_file() else None, name, len(laid.copies), synthesize
    ).encode("utf-8")
    rules = source.with_suffix(".kicad_dru")
    if rules.is_file():
        files[f"{name}.kicad_dru"] = rules.read_bytes()
    files[f"{name}.panel.json"] = panel_json(panel, data)
    return PanelOutput(dict(sorted(files.items())), laid, issues, "kicad", score_layer, board)


__all__ = ["PanelOutput", "kicad_panel", "panel_json", "read_source"]
