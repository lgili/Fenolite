# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed set of copper issue codes and the module's evidence (capability manual-copper: "Copper issue
codes", "Copper evidence", "Copper module"; change c0028)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from _copper import at, built_blink, end, step, stitch, track, via
from _placed import mm

from fenolite.backends.kicad import copper
from fenolite.backends.kicad.copper import COPPER_ISSUE_CODES, copper_uuid, resolve_copper
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level
from fenolite.core.ids import derived_id

TABLE = {
    "kicad.copper.bad-intent": "error",
    "kicad.copper.pad-not-found": "error",
    "kicad.copper.layer-mismatch": "error",
    "kicad.copper.bad-layer": "error",
    "kicad.copper.net-conflict": "error",
    "kicad.copper.unknown-net": "error",
    "kicad.copper.no-net": "error",
    "kicad.copper.size-missing": "error",
    "kicad.copper.bad-size": "error",
    "kicad.copper.stale": "warning",
    "kicad.copper.end-unplaced": "warning",
    "kicad.copper.stitch-empty": "warning",
    "kicad.copper.regenerated": "info",
    "kicad.copper.duplicate": "info",
    "kicad.copper.stitch-skipped": "info",
}


def _codes(design: object, *intents: object, unplaced: tuple[str, ...] = ()) -> list[Issue]:
    found: list[Issue] = []
    resolve_copper(design, intents, unplaced=unplaced, issues=found)  # type: ignore[arg-type]
    return found


def test_closed_set() -> None:
    """Every code a resolution produces is a key of the table with its severity, every key is produced, and
    the module writes no other ``kicad.copper.*`` literal."""
    assert dict(COPPER_ISSUE_CODES) == TABLE
    blink = built_blink()
    found = _codes(
        blink,
        track("bad", end("R1", 1)),
        track("nopad", end("R9", 1), at(1, 1)),
        track("layer", end("R1", 1), at(30, 9), layer="B.Cu"),
        track("badlayer", end("R1", 1), at(30, 9), layer="In1.Cu"),
        track("conflict", end("R1", 1), end("U1", 9)),
        track("unknown", end("R1", 1), at(30, 9), net="NOPE"),
        track("nonet", at(1, 1), at(2, 1)),
        track("missing", end("R1", 2), at(36, 9), width=None),
        track("size", end("R1", 2), at(36, 9), width=0),
        track("staged", end("R1", 2), step(36, 9), end("D1", 2)),
        stitch("empty", along=(at(31.2, 9), at(32.8, 9)), pitch=mm(5)),
        unplaced=("D1",),
    )
    resolved = resolve_copper(blink, [track("a", end("R1", 2), at(36, 9)), via("b", at(20, 20))])
    assert resolved.board is not None
    edited = dataclasses.replace(resolved.board.tracks[0], width=1)
    native = "00000000-0000-4000-8000-000000000001"
    copy = dataclasses.replace(
        resolved.board.tracks[0], id=derived_id("trk", "kicad", native), native_ids={"kicad": native}
    )
    design = dataclasses.replace(resolved, board=dataclasses.replace(resolved.board, tracks=(edited, copy)))
    found += _codes(design, track("a", end("R1", 2), at(36, 9)))
    assert {(i.code, i.severity) for i in found} == set(TABLE.items())
    assert copper_uuid("b", "via") in " ".join(i.message for i in found if i.code == "kicad.copper.stale")
    tree = ast.parse(Path(copper.__file__).read_text(encoding="utf-8"))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith("kicad.copper.")
    }
    assert literals == set(TABLE)


def test_messages_hold_no_absolute_path() -> None:
    found = _codes(built_blink(), track("conflict", end("R1", 1), end("D1", 2)))
    assert all(str(Path.home()) not in i.message and i.where == "conflict" for i in found)


def test_evidence_constant() -> None:
    assert copper.EVIDENCE.level is Level.INFERRED
    assert copper.EVIDENCE.hypotheses == ("H-G-FRAME-UUID", "H-G-FRAME-ROUTE")


def test_module_does_not_import_the_dsl() -> None:
    tree = ast.parse(Path(copper.__file__).read_text(encoding="utf-8"))
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not [m for m in modules if m.startswith("fenolite.dsl")]
    assert set(copper.__all__) >= {
        "COPPER_MARKER", "copper_uuid", "is_copper_uuid", "PadEndLike", "ViaStepLike", "TrackIntentLike",
        "ViaIntentLike", "StitchIntentLike", "CopperIntentLike", "resolve_copper", "merge_copper",
        "CopperMerge", "COPPER_ISSUE_CODES", "EVIDENCE",
    }  # fmt: skip
