# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Benches and probes of the copper check (change c0029; capability kicad-oracle, "Via re-net probe").

Every re-net bench holds a 0.6 mm via of net ``GND`` whose disc overlaps a 0.25 mm ``F.Cu`` track of net
``VIN`` by 0.05 mm:

- ``padded``: the track ends on pad 1 of ``R1``, which is on ``VIN``; no other ``GND`` copper. This is the
  reported case (``H-K-VIA-RENET``).
- ``tied``: as ``padded``, and a ``GND`` track joins the via to pad 1 of ``R2``, on ``GND``: both nets own
  a pad. ``kicad-cli`` 10.0.6 reports the short of this bench in about half of its runs, so its DRC
  outcome is pinned on 9.0.9 only.
- ``dangling``: no pad at all, and no other ``GND`` copper.
- ``anchored``: no pad at all, and a ``GND`` track ends at the via's centre.

They are built with ``_rulebench.Builder``, written with ``write_board`` for the running major, with a
``{}`` project and the rules text ``(version 1)`` next to them. Nothing is committed: every bench lives in
a temporary folder.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

import _rulebench as rb

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.core.coords import Point

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
RULES = "(version 1)\n"
OVERLAP = 50_000
RENET_BENCHES = ("padded", "tied", "dangling", "anchored")
VIA_NET, TRACK_NET = "GND", "VIN"
SHORT = "shorting_items"
CLEARANCE = "clearance"
PAD_OFFSET = 800_000
"""Pad 1 of ``Mini_R_0603`` sits 0.8 mm left of the footprint origin."""
VIA_DIAMETER = 600_000
_NET = re.compile(r"\[([^\]]*)\]")


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def running_target() -> int:
    return runner().major()


# --- the re-net benches ---------------------------------------------------------------------------


def _vertical(made: rb.Builder, label: str, net: str, x: int, y0: int, y1: int) -> None:
    made.track(label, net, y0, x0=x, x1=x)
    made.tracks[-1] = dataclasses.replace(made.tracks[-1], start=Point(x, y0), end=Point(x, y1))


def renet_bench(name: str, target: int = 10) -> rb.Bench:
    """A re-net bench: items ``renet_a`` (the via) and ``renet_b`` (the track of the other net)."""
    if name not in RENET_BENCHES:
        raise ValueError(f"unknown re-net bench {name!r}")
    made = rb.Builder()
    if name in ("dangling", "anchored"):
        made.via_track("renet", VIA_NET, TRACK_NET, gap=-OVERLAP)
        if name == "anchored":
            via = made.vias[-1]
            _vertical(made, "anchor", VIA_NET, via.position.x, via.position.y - 3 * rb.MM, via.position.y)
        return made.build()
    y = made.row()
    made.row()
    centre = (rb.LEFT + rb.RIGHT) // 2
    made.part("r1", "R1", Point(centre, y), target=target, nets={"1": TRACK_NET, "2": "N1"})
    pad_x = centre - PAD_OFFSET
    made.track("renet_b", TRACK_NET, y, x0=rb.LEFT, x1=pad_x)
    at = Point(rb.LEFT + rb.MM, y + VIA_DIAMETER // 2 + rb.WIDTH // 2 - OVERLAP)
    made.via("renet_a", VIA_NET, at)
    if name == "tied":
        low = y + 5 * rb.MM
        made.part("r2", "R2", Point(centre, low), target=target, nets={"1": VIA_NET, "2": "N2"})
        _vertical(made, "tie_down", VIA_NET, at.x, at.y, low)
        made.track("tie_across", VIA_NET, low, x0=at.x, x1=pad_x)
    return made.build()


@contextmanager
def written(bench: rb.Bench, rules: str, target: int, project: str = rb.PROJECT) -> Iterator[Path]:
    """The bench written for ``target`` in a temporary folder, with its project and rules files: the
    board's path."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(bench.design, target=target).text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(project, encoding="utf-8")
        (folder / "bench.kicad_dru").write_text(rules, encoding="utf-8")
        yield board


def side_files(board: Path) -> dict[str, Path]:
    return {name: board.with_name(name) for name in ("bench.kicad_pro", "bench.kicad_dru")}


@cache
def _bench(name: str) -> rb.Bench:
    return renet_bench(name, running_target())


@cache
def renet_report(name: str) -> DrcReport | None:
    with written(_bench(name), RULES, running_target()) as board:
        return runner().drc(board, files=side_files(board)).report


@cache
def renet_export_nets(name: str) -> tuple[str, ...]:
    """The net field of every via record of the bench's IPC-D-356 export."""
    with written(_bench(name), RULES, running_target()) as board:
        text = runner().export_ipcd356(board, files=side_files(board))
    return tuple(record.net for record in read_ipcd356(text).records if record.ref == "VIA")


def renet_export(name: str) -> str:
    """``present`` when the bench's only via record is listed under the track's net."""
    nets = renet_export_nets(name)
    if len(nets) != 1:
        return "inconclusive"
    return rb.outcome(nets[0] == TRACK_NET)


def _naming_via(name: str) -> tuple[DrcViolation, ...]:
    report = renet_report(name)
    if report is None:
        return ()
    via = set(_bench(name).uuids("renet_a"))
    groups = (*report.violations, *report.unconnected_items)
    return tuple(v for v in groups if via & {item.uuid for item in v.items})


def renet_types(name: str) -> tuple[str, ...]:
    """The sorted DRC types (violations and unconnected items) that name the via's uuid."""
    return tuple(sorted({v.type for v in _naming_via(name)}))


def renet_drc(name: str) -> str:
    """``present`` when a ``shorting_items`` violation names the via's uuid."""
    if renet_report(name) is None:
        return "inconclusive"
    return rb.outcome(SHORT in renet_types(name))


def described_nets(name: str) -> dict[str, frozenset[str]]:
    """Item label → the net names in square brackets of the DRC report's descriptions of that item
    (``Via [VIN] on F.Cu - B.Cu``): the net each item has once the tool loaded the board."""
    report = renet_report(name)
    if report is None:
        return {}
    bench = _bench(name)
    labels = {uuid: label for label, uuids in bench.items.items() for uuid in uuids if ":" not in label}
    found: dict[str, set[str]] = {}
    for violation in (*report.violations, *report.unconnected_items):
        for item in violation.items:
            match = _NET.search(item.description)
            if item.uuid in labels and match is not None:
                found.setdefault(labels[item.uuid], set()).add(match.group(1))
    return {label: frozenset(nets) for label, nets in found.items()}


def renet_merged(name: str) -> str:
    """``present`` when the DRC report describes the via and the track of the other net with one net name:
    the tool merged the touching copper into one net. ``inconclusive`` when it describes neither."""
    nets = described_nets(name)
    via, track = nets.get("renet_a"), nets.get("renet_b")
    if via is None or track is None or len(via) != 1 or len(track) != 1:
        return "inconclusive"
    return rb.outcome(via == track)


@cache
def renet_resave_nets(name: str) -> tuple[str | None, str | None]:
    """The net names of the via and of the track after ``pcb upgrade`` (10.0 only)."""
    bench = _bench(name)
    with written(bench, RULES, running_target()) as board:
        saved = runner().upgrade_board(board, files=side_files(board)).decode("utf-8")
    design = read_board(saved, file="bench.kicad_pcb")
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    by_uuid = {
        item.native_ids.get("kicad"): item.net_id for item in (*design.board.vias, *design.board.tracks)
    }
    (via_uuid,), (track_uuid,) = bench.uuids("renet_a"), bench.uuids("renet_b")
    via, track = by_uuid[via_uuid], by_uuid[track_uuid]
    return (names.get(via) if via else None, names.get(track) if track else None)


def renet_resave(name: str) -> str:
    """``present`` when the re-saved board holds the via on the net of the track."""
    via, track = renet_resave_nets(name)
    return rb.outcome(via is not None and via == track)


def copper_probes() -> Probes:
    both = (9, 10)
    return {
        "copper-renet-export": (lambda: renet_export("padded"), both),
        "copper-renet-drc": (lambda: renet_drc("padded"), both),
        "copper-renet-resave": (lambda: renet_resave("padded"), (10,)),
        "copper-renet-tied-export": (lambda: renet_export("tied"), both),
        "copper-renet-tied-drc": (lambda: renet_drc("tied"), (9,)),
        "copper-renet-dangling-drc": (lambda: renet_drc("dangling"), both),
        "copper-renet-dangling-merged": (lambda: renet_merged("dangling"), both),
        "copper-renet-anchored-drc": (lambda: renet_drc("anchored"), both),
        "copper-renet-anchored-merged": (lambda: renet_merged("anchored"), both),
        "copper-renet-dangling-resave": (lambda: renet_resave("dangling"), (10,)),
    }


__all__ = [
    "CLEARANCE",
    "OVERLAP",
    "RENET_BENCHES",
    "RULES",
    "SHORT",
    "TRACK_NET",
    "VIA_NET",
    "copper_probes",
    "described_nets",
    "renet_bench",
    "renet_drc",
    "renet_export",
    "renet_export_nets",
    "renet_merged",
    "renet_report",
    "renet_resave",
    "renet_resave_nets",
    "renet_types",
    "running_target",
    "side_files",
    "written",
]
