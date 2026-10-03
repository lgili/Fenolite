# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Projects assembled in ``tmp_path`` for ``check`` tests, and folder snapshots (change c0013 Decision 19).

``authored_project`` writes c0017's triad with ``write_triad`` for one major, the matching Mini library
under ``libs/`` with a ``${KIPRJMOD}`` ``fp-lib-table`` written by ``libs.write_lib_table``, and decoys
that ``check`` must neither copy nor touch. ``native_project`` is ``two_layer.kicad_pcb`` with a ``{}``
project, and ``demo_project`` a cached demo board with a ``{}`` project and a ``(version 1)`` rules file.
Every file is authored for Fenolite or fetched from a public source declared in the corpus manifest.
"""

from __future__ import annotations

import dataclasses
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Literal

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.ids import derived_id
from fenolite.model.canonical import dump_dir
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS / "kicad" / "board"))  # c0017's triad helper lives with the board oracle

import _triad  # noqa: E402
from _corpus import CorpusItem, require  # noqa: E402

DATA = TESTS / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
RULES = DATA / "kicad" / "rules"
STEM = "board"
Rules = Literal["one-rule", "broken"] | None
ONE_RULE = Rule(
    id=derived_id("rul", "test", "one-rule"),
    name="vin_clearance",
    kind="clearance",
    selector_a=Selector("net", "VIN"),
    min=200_000,
)
NATIVE_RULE = (
    "(version 1)\n"
    '(rule "gnd_clearance"\n'
    "\t(constraint clearance (min 0.2mm))\n"
    "\t(condition \"A.NetName == 'GND'\"))\n"
)
"""An authored one-rule file for the native project, on a net of ``two_layer.kicad_pcb``."""
PRL = (
    '{\n  "board": {\n    "active_layer": 0\n  },\n'
    '  "meta": {\n    "filename": "board.kicad_prl",\n    "version": 3\n  }\n}\n'
)
"""An authored minimal local-settings file for hermetic tests (KiCad writes the real one)."""
SYM_TABLE = "(sym_lib_table\n)\n"


def _broken() -> bytes:
    return (RULES / "broken.kicad_dru").read_bytes()


def _vin_net(design: Design) -> str:
    return next(n.id for n in design.circuit.nets if n.name == "VIN")


def _design(major: int, *, built: bool, rules: Rules) -> Design:
    design = _triad.triad(major)
    # The triad's VIN track runs over R1 pad 2 (LED_A). KiCad then reports the clearance between the two
    # tracks in some runs only (observed on 10.0.6), so two DRC runs of one project could differ. The
    # authored project leaves that track out, and its DRC is repeatable.
    assert design.board is not None
    tracks = tuple(t for t in design.board.tracks if t.net_id != _vin_net(design))
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=tracks))
    if rules == "one-rule":
        design = dataclasses.replace(
            design, rules=RuleSet(id=derived_id("rst", "test", "one-rule"), rules=(ONE_RULE,))
        )
    if built:
        circuit = design.circuit
        components = tuple(
            dataclasses.replace(c, lib_symbol_ref=f"Mini:{c.ref.rstrip('0123456789')}")
            for c in circuit.components
        )
        design = dataclasses.replace(design, circuit=dataclasses.replace(circuit, components=components))
    return design


def authored_project(
    tmp_path: Path,
    *,
    major: int,
    built: bool = False,
    rules: Rules = "one-rule",
    project: bool = True,
    decoys: bool = True,
    cli: KicadCli | None = None,
) -> Path:
    """The folder of an authored project for ``major``: ``board.kicad_pcb`` and, as asked, its project
    and rules files, ``libs/<Mini>.pretty`` with a ``${KIPRJMOD}`` table, decoys and ``.fenolite/``."""
    root = tmp_path / f"authored-{major}"
    root.mkdir(parents=True)
    design = _design(major, built=built, rules=rules)
    texts = write_triad(design, name=STEM, target=major)
    for name, text in texts.items():
        if name.endswith(".kicad_pro") and not project:
            continue
        if name.endswith(".kicad_dru") and rules is None:
            continue
        (root / name).write_text(text, encoding="utf-8")
    if rules == "broken":
        (root / f"{STEM}.kicad_dru").write_bytes(_broken())
    library = _triad.library(major)
    shutil.copytree(library, root / "libs" / library.name)
    row = LibRow("Mini", "KiCad", f"${{KIPRJMOD}}/libs/{library.name}")
    (root / "fp-lib-table").write_text(
        write_lib_table(LibTable("footprint", (row,)), target=major), encoding="utf-8"
    )
    if decoys:
        (root / "notes.txt").write_text("not a KiCad file\n", encoding="utf-8")
        (root / "sym-lib-table").write_text(SYM_TABLE, encoding="utf-8")
        (root / f"{STEM}.kicad_prl").write_text(_prl(root, cli), encoding="utf-8")
    if built:
        dump_dir(design, root / ".fenolite")
    return root


def _prl(root: Path, cli: KicadCli | None) -> str:
    """The local settings KiCad writes in a first run (``CliRun.outputs``), or the authored ``PRL``."""
    if cli is not None:
        board = root / f"{STEM}.kicad_pcb"
        files = {p.name: p for p in root.iterdir() if p.name != board.name and p.is_file()}
        files.update({"libs": root / "libs"})
        written = cli.drc(board, files=files).run.outputs.get(f"{STEM}.kicad_prl")
        if written is not None:
            return written.decode("utf-8")
    return PRL


def native_project(tmp_path: Path, *, rules: Rules = "one-rule") -> Path:
    """``two_layer.kicad_pcb`` as ``board.kicad_pcb`` with a ``{}`` project and, as asked, a rules file."""
    root = tmp_path / "native"
    root.mkdir(parents=True)
    shutil.copyfile(TWO_LAYER, root / f"{STEM}.kicad_pcb")
    (root / f"{STEM}.kicad_pro").write_text("{}\n", encoding="utf-8")
    if rules == "one-rule":
        (root / f"{STEM}.kicad_dru").write_text(NATIVE_RULE, encoding="utf-8")
    elif rules == "broken":
        (root / f"{STEM}.kicad_dru").write_bytes(_broken())
    return root


def demo_project(tmp_path: Path, item: CorpusItem) -> Path:
    """A cached demo board in its own folder with a ``{}`` project and a ``(version 1)`` rules file."""
    source = require(item)
    root = tmp_path / item.id
    root.mkdir(parents=True)
    shutil.copyfile(source, root / f"{STEM}.kicad_pcb")
    (root / f"{STEM}.kicad_pro").write_text("{}\n", encoding="utf-8")
    (root / f"{STEM}.kicad_dru").write_text("(version 1)\n", encoding="utf-8")
    return root


def upgraded_project(tmp_path: Path, item: CorpusItem, cli: KicadCli) -> Path:
    """``demo_project`` with the board re-saved once by ``pcb upgrade --force`` (10.0 only): the copy of a
    board below the read floor keeps its origin (corpus-policy, "Upgraded copies keep their origin"). The
    cached file is only read."""
    source = require(item)
    root = tmp_path / item.id
    root.mkdir(parents=True)
    (root / f"{STEM}.kicad_pcb").write_bytes(cli.upgrade_board(source))
    (root / f"{STEM}.kicad_pro").write_text("{}\n", encoding="utf-8")
    (root / f"{STEM}.kicad_dru").write_text("(version 1)\n", encoding="utf-8")
    return root


def tree_snapshot(root: Path) -> dict[str, tuple[str, str, int]]:
    """``root`` and every path under it (by ``lstat``): kind, SHA-256 of a file, ``st_mtime_ns``."""
    found: dict[str, tuple[str, str, int]] = {".": ("dir", "", root.lstat().st_mtime_ns)}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            found[rel] = ("link", str(path.readlink()), info.st_mtime_ns)
        elif path.is_dir():
            found[rel] = ("dir", "", info.st_mtime_ns)
        else:
            found[rel] = ("file", hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mtime_ns)
    return found


__all__ = [
    "ONE_RULE",
    "STEM",
    "authored_project",
    "demo_project",
    "native_project",
    "tree_snapshot",
    "upgraded_project",
]
