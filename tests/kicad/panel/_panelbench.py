# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The panel boards of change c0173 against the running ``kicad-cli`` (hypotheses ``H-K-PANEL-LOAD``,
``H-K-PANEL-DRILL``, ``H-K-PANEL-NETS`` and ``H-K-PANEL-GERBER``).

The boards are the three panel fixtures of ``tests/data/panels/`` over the committed board of the running
major (``board_t9.kicad_pcb`` or ``board_t10.kicad_pcb``), written by ``panel.build.kicad_panel``;
``vscore.py``, which the checks refuse, is written past them with ``panel.kicad.panel_board_text`` (KiCad
judges the board, not the fabricator). Each is checked with an empty project, as the source board is:

- ``panel-load``: every panel loads, ``pcb drc`` gives no ``invalid_outline``, no unconnected item, and no
  violation type counts more than the number of copies times the source board's own count: ``absent`` (no
  finding beyond the copies' own; ``tabs.py`` and ``mixed.py`` give exactly that many, ``vscore.py`` fewer
  edge findings, its copies touching where the source has an edge);
- ``panel-drill``: the non-plated drill file of ``tabs.py`` holds exactly the mouse-bite and tooling holes
  at their places (within 1 µm, the file's precision), and the plated one the copies' own holes:
  ``equal``;
- ``panel-nets``: no ``unconnected_items`` and no ``shorting_items`` on ``tabs.py`` and ``mixed.py``:
  ``absent``;
- ``panel-gerber``: the plot of the score layer of ``mixed.py`` holds one draw per score line: ``equal``;
  ``gerber_function()`` gives its ``.FileFunction``, recorded in ``docs/formats/kicad/panel.md``.
"""

from __future__ import annotations

import re
import runpy
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

from _lenscases import runner
from _outlinebench import target
from _panels import PANELS, committed_board

from fenolite.backends.base import DrcReport
from fenolite.dsl import Panel, to_model
from fenolite.model.panel import Panel as ModelPanel
from fenolite.panel.build import kicad_panel, read_source
from fenolite.panel.kicad import ORIGIN, footprint_files, panel_board_text
from fenolite.panel.layout import PanelLayout, layout

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
PROJECT = "{}\n"
MICRON = 1_000


def model_of(name: str) -> ModelPanel:
    panel = runpy.run_path(str(PANELS / f"{name}.py"))["panel"]
    assert isinstance(panel, Panel)
    return to_model(panel)


@cache
def panel_files(name: str) -> tuple[tuple[str, bytes], ...]:
    """The board, its generated footprints and an empty project of the panel ``name`` for the running
    major."""
    model = model_of(name)
    source = committed_board(target())
    if name == "vscore":
        board, data = read_source(source)
        laid = layout(model, board)
        text, _ = panel_board_text(model, laid, data.decode("utf-8"), target=target())
        files = {f"{name}.kicad_pcb": text.encode("utf-8"), **footprint_files(model, laid, target=target())}
    else:
        output = kicad_panel(model, source, target=target())
        assert not output.refused, output.issues
        files = {k: v for k, v in output.files.items() if not k.endswith((".kicad_pro", ".kicad_dru"))}
    files[f"{name}.kicad_pro"] = PROJECT.encode("utf-8")
    return tuple(sorted(files.items()))


@cache
def panel_layout(name: str) -> PanelLayout:
    board, _ = read_source(committed_board(target()))
    return layout(model_of(name), board)


def _drc(files: Mapping[str, bytes], board: str) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for key, data in files.items():
            path = root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        extra = {key: root / key for key in files if key != board}
        return runner().drc(root / board, files=extra).report


@cache
def source_report() -> DrcReport | None:
    return _drc(
        {"board.kicad_pcb": committed_board(target()).read_bytes(), "board.kicad_pro": PROJECT.encode()},
        "board.kicad_pcb",
    )


@cache
def panel_report(name: str) -> DrcReport | None:
    return _drc(dict(panel_files(name)), f"{name}.kicad_pcb")


def counts(report: DrcReport) -> Counter[str]:
    return Counter(v.type for v in report.violations)


@cache
def load() -> str:
    """``absent`` when every panel loads with no ``invalid_outline`` and no finding beyond the copies'."""
    source = source_report()
    if source is None:
        return "inconclusive"
    for name in ("tabs", "mixed", "vscore"):
        report = panel_report(name)
        if report is None:
            return "inconclusive"
        copies = len(panel_layout(name).copies)
        wanted = Counter({kind: copies * n for kind, n in counts(source).items()})
        found = counts(report)
        beyond = any(n > wanted.get(kind, 0) for kind, n in found.items())
        if "invalid_outline" in found or beyond or report.unconnected_items:
            return "present"
    return "absent"


@cache
def drill_hits(name: str) -> dict[str, list[tuple[float, float]]] | None:
    """The drill files of panel ``name`` with the options of ``exports.plan``: file name → hit points."""
    files = dict(panel_files(name))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for key, data in files.items():
            (root / key).parent.mkdir(parents=True, exist_ok=True)
            (root / key).write_bytes(data)
        args = ["pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm"]
        args += ["--excellon-separate-th", "--drill-origin", "absolute", "-o", "drill/", f"{name}.kicad_pcb"]
        run = runner().run(args, files={k: root / k for k in files}, folders=["drill"])
    if not run.ok:
        return None
    found: dict[str, list[tuple[float, float]]] = {}
    for key, data in run.outputs.items():
        if key.startswith("drill/") and key.endswith(".drl"):
            hits = []
            for line in data.decode("utf-8", "replace").splitlines():
                match = re.match(r"^X(-?\d+(?:\.\d+)?)Y(-?\d+(?:\.\d+)?)$", line.strip())
                if match:
                    hits.append((float(match.group(1)), float(match.group(2))))
            found[key.removeprefix("drill/")] = hits
    return found


def _near(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) * 1_000_000 <= MICRON and abs(abs(a[1]) - abs(b[1])) * 1_000_000 <= MICRON


@cache
def drill() -> str:
    """``equal`` when the NPTH file holds exactly the mouse-bite and tooling holes of ``tabs.py`` and the
    PTH file the copies' own holes (eight times the source's)."""
    hits = drill_hits("tabs")
    laid = panel_layout("tabs")
    if hits is None:
        return "inconclusive"
    npth = [h for key, found in hits.items() if "NPTH" in key for h in found]
    pth = [h for key, found in hits.items() if "NPTH" not in key for h in found]
    wanted = [
        ((p.x + ORIGIN.x) / 1_000_000, (p.y + ORIGIN.y) / 1_000_000)
        for p in (*(h for t in laid.tabs for h in t.holes), *(h.at for h in laid.tooling_holes))
    ]
    if len(npth) != len(wanted) or not all(any(_near(w, h) for h in npth) for w in wanted):
        return "different"
    board, _ = read_source(committed_board(target()))
    assert board.board is not None
    own = sum(1 for fp in board.board.footprints for pad in fp.pads if pad.drill) + len(board.board.vias)
    return "equal" if len(pth) == len(laid.copies) * own else "different"


@cache
def nets() -> str:
    """``absent`` when neither ``tabs.py`` nor ``mixed.py`` gives an unconnected or a shorting item."""
    for name in ("tabs", "mixed"):
        report = panel_report(name)
        if report is None:
            return "inconclusive"
        if report.unconnected_items or "shorting_items" in counts(report):
            return "present"
    return "absent"


@cache
def gerber_plot() -> tuple[str, int] | None:
    """The ``.FileFunction`` of the score layer's plot of ``mixed.py`` and its number of draws."""
    files = dict(panel_files("mixed"))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for key, data in files.items():
            (root / key).parent.mkdir(parents=True, exist_ok=True)
            (root / key).write_bytes(data)
        args = [
            "pcb",
            "export",
            "gerbers",
            "-o",
            "gerbers/",
            "--no-protel-ext",
            "--layers",
            "User.1,Edge.Cuts",
        ]
        run = runner().run(
            [*args, "mixed.kicad_pcb"], files={k: root / k for k in files}, folders=["gerbers"]
        )
    if not run.ok:
        return None
    for key, data in run.outputs.items():
        if key.startswith("gerbers/") and not key.endswith(("Edge_Cuts.gbr", ".gbrjob")):
            text = data.decode("utf-8", "replace")
            match = re.search(r"%TF\.FileFunction,([^*]*)\*%", text)
            draws = len(re.findall(r"D01\*", text))
            return (match.group(1) if match else ""), draws
    return None


def gerber_function() -> str:
    found = gerber_plot()
    return "" if found is None else found[0]


@cache
def gerber() -> str:
    """``equal`` when the score layer plots one draw per score line of ``mixed.py``."""
    found = gerber_plot()
    if found is None:
        return "inconclusive"
    return "equal" if found[1] == len(panel_layout("mixed").score_lines) else "different"


def panel_probes() -> Probes:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    return {
        "panel-load": (load, both),
        "panel-drill": (drill, both),
        "panel-nets": (nets, both),
        "panel-gerber": (gerber, both),
    }


__all__ = ["gerber_function", "panel_files", "panel_probes"]
