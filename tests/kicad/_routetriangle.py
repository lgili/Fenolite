# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The level-5 triangle on the routed sample (capability design-equivalence, "Level 5 over the triangle";
change c0089; ``H-G-EQ-L5-TRIANGLE``).

Three reads of one routed board:

- ``kicad``: the routed sample's KiCad board (``tests/_altium_copper.py``, authored for Fenolite), read by
  the KiCad backend;
- ``altium``: the PCB document that ``fenolite build --target altium --copper-from`` writes from that board,
  read by the Altium backend;
- ``imported``: the board that ``kicad-cli pcb import --format altium`` converts that document to, read by
  the KiCad backend.

Each pair is compared at levels 1 to 5 in the relative frame, with the tolerances of the importer's
profile of the running ``kicad-cli`` version line. ``pcb import`` exists from 10.0 only (S-0166).
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from _altium import blink_tree
from _altium_copper import routed_board_text, routed_script
from _resources import kicad_cli
from _triangle import TIMEOUT, profile_for

import fenolite.cli.main as cli_main
from fenolite.backends import registry
from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import cli_for
from fenolite.backends.kicad.pcb import read_board
from fenolite.checks.equivalence import EquivalenceReport, Tolerances, compare_designs
from fenolite.model.design import Design

PAIRS = (("kicad", "altium"), ("altium", "imported"), ("kicad", "imported"))
"""The three sides of the triangle, as pairs of corners."""


@dataclass(frozen=True)
class Corners:
    """The three reads of the routed sample and the version of the tool that converted the document."""

    kicad: Design
    altium: Design
    imported: Design
    version: str

    def of(self, name: str) -> Design:
        found: Design = getattr(self, name)
        return found


def _build(script: Path, board: Path, out: Path, config: Path) -> None:
    """``fenolite build --target altium --copper-from`` in this process, with KiCad's configuration folder
    set to an empty one of the test."""
    argv = ["build", str(script), "--out", str(out), "--target", "altium", "--copper-from", str(board)]
    saved = os.environ.get("KICAD_CONFIG_HOME")
    os.environ["KICAD_CONFIG_HOME"] = str(config)
    old_out, old_err = sys.stdout, sys.stderr
    stdout, stderr = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = stdout, stderr
    try:
        code = cli_main.main([*argv, "--confirm", "--json"])
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        if saved is None:
            del os.environ["KICAD_CONFIG_HOME"]
        else:
            os.environ["KICAD_CONFIG_HOME"] = saved
    assert code == 0, stderr.getvalue() + stdout.getvalue()
    assert json.loads(stdout.getvalue())["result"]["copper"]["source"] == "board"


@cache
def corners() -> Corners:
    """The three reads; the sample is built and converted once per session, in a temporary folder."""
    path = kicad_cli()
    assert path is not None
    with tempfile.TemporaryDirectory(prefix="fenolite-l5-triangle-") as folder:
        root = Path(folder)
        project = blink_tree(root / "tree")
        script, board = project / "design.py", project / "routed.kicad_pcb"
        script.write_text(routed_script(), encoding="utf-8")
        board.write_text(routed_board_text(), encoding="utf-8", newline="\n")
        _build(script, board, root / "out", root / "config")
        document = root / "out" / "routed.PcbDoc"
        backend = registry.for_path(document)
        assert backend is not None
        found = altium_import.import_design(cli_for(Path(path), timeout=TIMEOUT), document)
        return Corners(
            read_board(board), backend.read(document).design, found.read.design, found.tool_version
        )


def tolerances(version: str, *, ppm: int | None = None) -> Tolerances:
    """The tolerances of the importer's profile of ``version``; ``ppm`` replaces its relative one."""
    profile = profile_for(version)
    return Tolerances(
        profile.tolerance_nm, profile.tolerance_udeg, profile.tolerance_ppm if ppm is None else ppm
    )


def compare(one: Design, other: Design, version: str, *, ppm: int | None = None) -> EquivalenceReport:
    """Levels 1 to 5 of two corners in the relative frame. No rule applies: the profile's rules name pads
    of the public documents, and the sample needs none."""
    return compare_designs(one, other, level=5, tolerances=tolerances(version, ppm=ppm), frame="relative")


def outcome() -> str:
    """The probe ``equiv-l5-triangle``: ``equal`` when the three pairs hold no difference at levels 1 to
    5 and level 5 compared at least one net of each, ``different`` otherwise."""
    found = corners()
    for first, second in PAIRS:
        report = compare(found.of(first), found.of(second), found.version)
        if not report.equivalent or report.levels[-1].compared == 0:
            return "different"
    return "equal"


__all__ = ["PAIRS", "Corners", "compare", "corners", "outcome", "tolerances"]
