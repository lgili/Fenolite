# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Projects with seeded faults for ``check`` (change c0020 Decision 13), written into ``tmp_path``.

Each fault is made from c0013's authored built project through the model: the board is read with
``read_board``, changed, and written again with ``write_board`` for the running major, so the writer's
gating and uuids apply; nothing is a text edit and nothing is committed. The positive control is c0018's
own overlap bench (``_rulecases.order_bench`` and ``order_rules``), canary included (Decision 20).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from pathlib import Path

import _rulebench as rb
import _rulecases
from _projects import STEM, authored_project
from _triad import pad_position

from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, FootprintInstance, Track
from fenolite.model.design import Design

LONG_NAMES = ("/A/LONG_SIGNAL_NAME", "/B/LONG_SIGNAL_NAME")
"""Two net names that share their last 14 characters, so IPC-D-356 gives them one label."""


def _board_path(root: Path) -> Path:
    return root / f"{STEM}.kicad_pcb"


def _edit(root: Path, major: int, change: Callable[[Design], Design]) -> Path:
    """Read the project's board, apply ``change(design) -> design`` and write it back for ``major``."""
    path = _board_path(root)
    design = read_board(path.read_text(encoding="utf-8"), file=path.name)
    changed = change(design)
    path.write_text(write_board(changed, target=major).text, encoding="utf-8")
    return root


def _board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def footprint(design: Design, ref: str) -> FootprintInstance:
    by_id = {c.id: c.ref for c in design.circuit.components}
    return next(fp for fp in _board(design).footprints if by_id.get(fp.component_id) == ref)


def net_id(design: Design, name: str) -> str:
    return next(n.id for n in design.circuit.nets if n.name == name)


def pad_uuid(design: Design, ref: str, number: str) -> str:
    """The KiCad uuid of pad ``number`` of ``ref`` in a board read from a file."""
    pad = next(p for p in footprint(design, ref).pads if p.number == number)
    return pad.native_ids["kicad"]


def reassigned(tmp_path: Path, *, major: int) -> Path:
    """Pad 2 of ``R1`` moved from ``LED_A`` to ``GND`` on the board only; ``.fenolite/`` unchanged."""
    root = authored_project(tmp_path / "reassigned", major=major, built=True)

    def change(design: Design) -> Design:
        r1 = footprint(design, "R1")
        gnd = net_id(design, "GND")
        pads = tuple(dataclasses.replace(p, net_id=gnd) if p.number == "2" else p for p in r1.pads)
        board = _board(design)
        fps = tuple(dataclasses.replace(fp, pads=pads) if fp is r1 else fp for fp in board.footprints)
        return dataclasses.replace(design, board=dataclasses.replace(board, footprints=fps))

    return _edit(root, major, change)


def bridging(tmp_path: Path, *, major: int) -> Path:
    """One ``F.Cu`` track of net ``VIN`` from pad 1 to pad 2 of ``R1``: a short with ``LED_A``."""
    root = authored_project(tmp_path / "bridging", major=major, built=True)

    def change(design: Design) -> Design:
        r1 = footprint(design, "R1")
        track = Track(
            id=derived_id("trk", "c0020", "bridging"),
            start=pad_position(r1, "1"),
            end=pad_position(r1, "2"),
            width=250_000,
            layer="F.Cu",
            net_id=net_id(design, "VIN"),
        )
        board = _board(design)
        return dataclasses.replace(design, board=dataclasses.replace(board, tracks=(*board.tracks, track)))

    return _edit(root, major, change)


def missing_track(tmp_path: Path, *, major: int) -> Path:
    """The authored built project without its ``R1``–``D1`` track (net ``LED_A``)."""
    root = authored_project(tmp_path / "missing", major=major, built=True)

    def change(design: Design) -> Design:
        led_a = net_id(design, "LED_A")
        board = _board(design)
        tracks = tuple(t for t in board.tracks if t.net_id != led_a)
        assert len(tracks) == len(board.tracks) - 1, "the authored project has one LED_A track"
        return dataclasses.replace(design, board=dataclasses.replace(board, tracks=tracks))

    return _edit(root, major, change)


def long_names(tmp_path: Path, *, major: int) -> Path:
    """The authored built project with ``VIN`` and ``LED_A`` renamed to the two ``LONG_NAMES``."""
    root = authored_project(tmp_path / "long-names", major=major, built=True)
    renames = dict(zip(("VIN", "LED_A"), LONG_NAMES, strict=True))

    def change(design: Design) -> Design:
        nets = tuple(dataclasses.replace(n, name=renames.get(n.name, n.name)) for n in design.circuit.nets)
        return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=nets))

    return _edit(root, major, change)


def overlap_bench(tmp_path: Path, *, major: int, reverse: bool = False) -> Path:
    """c0018's overlap bench and its rules text, canary included, with a ``{}`` project."""
    direction = "reverse" if reverse else "forward"
    root = tmp_path / f"overlap-{direction}"
    root.mkdir(parents=True)
    bench = _rulecases.order_bench()
    _board_path(root).write_text(write_board(bench.design, target=major).text, encoding="utf-8")
    (root / f"{STEM}.kicad_pro").write_text(rb.PROJECT, encoding="utf-8")
    (root / f"{STEM}.kicad_dru").write_text(_rulecases.order_rules(direction), encoding="utf-8")
    return root


def with_severity(project: Path, key: str, value: str) -> None:
    """Set ``/board/design_settings/rule_severities/<key>`` to ``value`` in the project file."""
    path = project / f"{STEM}.kicad_pro"
    data = json.loads(path.read_text(encoding="utf-8"))
    settings = data.setdefault("board", {}).setdefault("design_settings", {})
    severities = settings.setdefault("rule_severities", {})
    severities[key] = value
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "LONG_NAMES",
    "bridging",
    "footprint",
    "long_names",
    "missing_track",
    "net_id",
    "overlap_bench",
    "pad_uuid",
    "reassigned",
    "with_severity",
]
