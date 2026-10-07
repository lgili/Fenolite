# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored bench for the limits of KiCad's DRC report, per type (``H-K-DRC-LIMITS``, change c0141;
capability kicad-oracle, "DRC report limits are probed").

``limits_project`` writes, by code, a board of 400 mm × 400 mm in format 20241229 with a ``{}`` project and
a rules file. The board holds, for each requested type, N copies of one small construct that gives exactly
one entry of that type and none of another, one construct per cell of a 4 mm grid, so no copy touches
another. ``report_counts`` runs ``kicad-cli pcb drc --format json --severity-all`` on it and counts the
entries per type. ``limit_probes`` gives the ``drc-limit-*`` rows of ``_probes.PROBES``: each compares one
count with what the hypothesis states, and ``counted`` keeps the counts for the test and the fact rows.

It is a second bench beside ``_limitbench.py`` (change c0051), which proves the canary's verdict at the
``clearance`` limit with close track pairs and is not changed. Every byte is authored for Fenolite: 400 mm,
4 mm, 700 and 150 are round values chosen for the bench.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from fenolite.backends.kicad.cli import DRC_REPORT, KicadCli
from fenolite.core.ids import FENOLITE_NS

STEM = "limits"
UNCONNECTED = "unconnected_items"
"""The key that stands for the report's list of unconnected items; every other type is a violation type."""
TYPES: tuple[str, ...] = (
    "clearance",
    UNCONNECTED,
    "track_dangling",
    "via_dangling",
    "copper_edge_clearance",
    "track_width",
    "hole_to_hole",
    "hole_clearance",
    "annular_width",
    "silk_overlap",
    "courtyards_overlap",
    "lib_footprint_issues",
    "shorting_items",
)
ABOVE = 700
"""Copies per type far above every limit."""
BELOW = 150
"""Copies per type under every limit."""
BELOW_TYPES: tuple[str, ...] = ("track_dangling", "silk_overlap", UNCONNECTED)
REPORT_KEYS: tuple[str, ...] = (
    "$schema",
    "coordinate_units",
    "date",
    "ignored_checks",
    "included_severities",
    "kicad_version",
    "schematic_parity",
    "source",
    "unconnected_items",
    "violations",
)
"""The top-level keys of the report (``H-K-DRC-LIMITS``): none of them marks a type as cut."""
STATED: Mapping[str, int] = {type_: 499 if type_ in ("clearance", UNCONNECTED) else 199 for type_ in TYPES}
"""What ``H-K-DRC-LIMITS`` states per type; the probes compare the tool with it, and the test compares the
counts with ``REPORT_LIMITS``."""

SIDE_MM = 400
PITCH_MM = 4
COLUMNS = 98
"""Cells per row: the first at (4, 4) mm, the last column at 392 mm, clear of the board's edge."""
ABSENT_LIBRARY = "Fenolite_Absent"
"""A library nickname that no table holds, for ``lib_footprint_issues``."""

RULES = (
    "(version 1)\n"
    '(rule "bench_track_width" (constraint track_width (min 0.2mm)))\n'
    '(rule "bench_hole_to_hole" (constraint hole_to_hole (min 1mm)))\n'
    '(rule "bench_hole_clearance" (constraint hole_clearance (min 1mm)))\n'
    '(rule "bench_annular_width" (constraint annular_width (min 0.15mm)))\n'
)
_HEAD = (
    "(kicad_pcb\n"
    "\t(version 20241229)\n"
    '\t(generator "fenolite-tests")\n'
    '\t(generator_version "9.0")\n'
    "\t(general (thickness 1.6) (legacy_teardrops no))\n"
    '\t(paper "A2")\n'
    "\t(layers\n"
    '\t\t(0 "F.Cu" signal)\n'
    '\t\t(2 "B.Cu" signal)\n'
    '\t\t(5 "F.SilkS" user "F.Silkscreen")\n'
    '\t\t(7 "B.SilkS" user "B.Silkscreen")\n'
    '\t\t(1 "F.Mask" user)\n'
    '\t\t(3 "B.Mask" user)\n'
    '\t\t(25 "Edge.Cuts" user)\n'
    '\t\t(31 "F.CrtYd" user "F.Courtyard")\n'
    '\t\t(29 "B.CrtYd" user "B.Courtyard")\n'
    '\t\t(35 "F.Fab" user)\n'
    '\t\t(33 "B.Fab" user)\n'
    "\t)\n"
    "\t(setup (pad_to_mask_clearance 0))\n"
)
_FONT = "(effects (font (size 0.3 0.3) (thickness 0.05)))"


@dataclass
class _Board:
    """The nets and the items of the board being written."""

    nets: list[str] = field(default_factory=lambda: [])
    items: list[str] = field(default_factory=lambda: [])
    parts: int = 0

    def net(self, name: str) -> int:
        self.nets.append(name)
        return len(self.nets)

    def uid(self, label: str) -> str:
        return str(uuid.uuid5(FENOLITE_NS, f"limits-bench:{label}"))

    def footprint(self, label: str, x: float, y: float, body: Sequence[str], library: str = "") -> None:
        self.parts += 1
        name = f"{library}:Bench" if library else "Bench"
        rows = [
            f'\t(footprint "{name}" (layer "F.Cu") (uuid "{self.uid(label)}") (at {x:g} {y:g})',
            f'\t\t(property "Reference" "X{self.parts}" (at 0 0) (layer "F.Fab") hide'
            f' (uuid "{self.uid(label + ":ref")}") {_FONT})',
            f'\t\t(property "Value" "bench" (at 0 0) (layer "F.Fab") hide'
            f' (uuid "{self.uid(label + ":value")}") {_FONT})',
            *(f"\t\t{row}" for row in body),
            "\t)",
        ]
        self.items.append("\n".join(rows) + "\n")


def _pad(board: _Board, label: str, number: str, x: float, net: tuple[int, str] | None = None) -> str:
    """A 0.5 mm square pad on ``F.Cu`` alone (no mask opening, so no mask bridge is reported)."""
    wire = f' (net {net[0]} "{net[1]}")' if net is not None else ""
    return (
        f'(pad "{number}" smd rect (at {x:g} 0) (size 0.5 0.5) (layers "F.Cu"){wire}'
        f' (uuid "{board.uid(f"{label}:pad{number}")}"))'
    )


def _hole(board: _Board, label: str, part: str, x: float) -> str:
    """An unplated hole of 0.5 mm."""
    return (
        f'(pad "" np_thru_hole circle (at {x:g} 0) (size 0.5 0.5) (drill 0.5) (layers "*.Cu" "*.Mask")'
        f' (uuid "{board.uid(f"{label}:hole{part}")}"))'
    )


def _named(board: _Board, label: str, *parts: str) -> list[tuple[int, str]]:
    return [
        (board.net(name), name) for name in (f"LIMITS_{label}_{part}".replace(":", "_") for part in parts)
    ]


def _clearance(board: _Board, label: str, x: int, y: int) -> None:
    """Two pads of two nets with a gap of 0.1 mm, under the default clearance of 0.2 mm."""
    a, b = _named(board, label, "A", "B")
    board.footprint(label, x, y, [_pad(board, label, "1", 0, a), _pad(board, label, "2", 0.6, b)])


def _unconnected(board: _Board, label: str, x: int, y: int) -> None:
    """Two pads of one net, 1.5 mm apart, with no copper between them."""
    (net,) = _named(board, label, "N")
    board.footprint(label, x, y, [_pad(board, label, "1", 0, net), _pad(board, label, "2", 1.5, net)])


def _track_dangling(board: _Board, label: str, x: int, y: int) -> None:
    """A track of no net that touches nothing."""
    board.items.append(
        f'\t(segment (start {x} {y}) (end {x + 1} {y}) (width 0.25) (layer "F.Cu") (net 0)'
        f' (uuid "{board.uid(label)}"))\n'
    )


def _via_dangling(board: _Board, label: str, x: int, y: int) -> None:
    """A via of a net of its own that touches nothing."""
    (net,) = _named(board, label, "N")
    board.items.append(
        f'\t(via (at {x} {y}) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net {net[0]})'
        f' (uuid "{board.uid(label)}"))\n'
    )


def _copper_edge(board: _Board, label: str, x: int, y: int) -> None:
    """A pad that reaches into a square cut-out of the board."""
    board.items.append(
        f"\t(gr_rect (start {x - 0.5:g} {y - 0.25:g}) (end {x:g} {y + 0.25:g})"
        ' (stroke (width 0.05) (type default)) (fill no) (layer "Edge.Cuts")'
        f' (uuid "{board.uid(label + ":cut")}"))\n'
    )
    board.footprint(label, x, y, [_pad(board, label, "1", 0.3)])


def _track_width(board: _Board, label: str, x: int, y: int) -> None:
    """Two pads of one net joined by a track of 0.1 mm, under the rule's 0.2 mm."""
    (net,) = _named(board, label, "N")
    board.footprint(label, x, y, [_pad(board, label, "1", 0, net), _pad(board, label, "2", 1.5, net)])
    board.items.append(
        f'\t(segment (start {x} {y}) (end {x + 1.5:g} {y}) (width 0.1) (layer "F.Cu") (net {net[0]})'
        f' (uuid "{board.uid(label + ":track")}"))\n'
    )


def _hole_to_hole(board: _Board, label: str, x: int, y: int) -> None:
    """Two unplated holes with 0.3 mm between them, under the rule's 1 mm."""
    board.footprint(label, x, y, [_hole(board, label, "a", 0), _hole(board, label, "b", 0.8)])


def _hole_clearance(board: _Board, label: str, x: int, y: int) -> None:
    """A pad 0.5 mm from an unplated hole, under the rule's 1 mm."""
    board.footprint(label, x, y, [_hole(board, label, "a", 0), _pad(board, label, "1", 1.0)])


def _annular_width(board: _Board, label: str, x: int, y: int) -> None:
    """A plated hole with a ring of 0.05 mm, under the rule's 0.15 mm."""
    pad = (
        f'(pad "1" thru_hole circle (at 0 0) (size 0.6 0.6) (drill 0.5) (layers "*.Cu")'
        f' (uuid "{board.uid(label + ":pad")}"))'
    )
    board.footprint(label, x, y, [pad])


def _silk_overlap(board: _Board, label: str, x: int, y: int) -> None:
    """A silkscreen text crossed by a silkscreen line."""
    board.items.append(
        f'\t(gr_text "S" (at {x} {y}) (layer "F.SilkS") (uuid "{board.uid(label + ":text")}")'
        " (effects (font (size 1 1) (thickness 0.15))))\n"
    )
    board.items.append(
        f"\t(gr_line (start {x - 1} {y}) (end {x + 1} {y}) (stroke (width 0.15) (type default))"
        f' (layer "F.SilkS") (uuid "{board.uid(label + ":line")}"))\n'
    )


def _courtyards_overlap(board: _Board, label: str, x: int, y: int) -> None:
    """Two footprints whose courtyards of 1 mm overlap by half."""
    for part, dx in (("a", 0.0), ("b", 0.5)):
        yard = (
            "(fp_rect (start -0.5 -0.5) (end 0.5 0.5) (stroke (width 0.05) (type default)) (fill no)"
            f' (layer "F.CrtYd") (uuid "{board.uid(f"{label}:{part}:yard")}"))'
        )
        board.footprint(f"{label}:{part}", x + dx, y, [yard])


def _lib_footprint_issues(board: _Board, label: str, x: int, y: int) -> None:
    """A footprint of a library that no table holds."""
    board.footprint(label, x, y, [], library=ABSENT_LIBRARY)


def _shorting_items(board: _Board, label: str, x: int, y: int) -> None:
    """Two overlapping pads of two nets."""
    a, b = _named(board, label, "A", "B")
    board.footprint(label, x, y, [_pad(board, label, "1", 0, a), _pad(board, label, "2", 0.3, b)])


CONSTRUCTS: Mapping[str, Callable[[_Board, str, int, int], None]] = {
    "clearance": _clearance,
    UNCONNECTED: _unconnected,
    "track_dangling": _track_dangling,
    "via_dangling": _via_dangling,
    "copper_edge_clearance": _copper_edge,
    "track_width": _track_width,
    "hole_to_hole": _hole_to_hole,
    "hole_clearance": _hole_clearance,
    "annular_width": _annular_width,
    "silk_overlap": _silk_overlap,
    "courtyards_overlap": _courtyards_overlap,
    "lib_footprint_issues": _lib_footprint_issues,
    "shorting_items": _shorting_items,
}


def limits_board(copies: Mapping[str, int]) -> str:
    """The bench board's text with ``copies[type]`` constructs of each type, in the order of ``TYPES``."""
    board = _Board()
    cell = 0
    for type_ in TYPES:
        for index in range(copies.get(type_, 0)):
            x = PITCH_MM * (1 + cell % COLUMNS)
            y = PITCH_MM * (1 + cell // COLUMNS)
            if y > SIDE_MM - PITCH_MM:
                raise ValueError("the bench does not fit on its board")
            CONSTRUCTS[type_](board, f"{type_}:{index}", x, y)
            cell += 1
    unknown = set(copies) - set(TYPES)
    if unknown:
        raise ValueError(f"no construct for {sorted(unknown)}")
    nets = ['\t(net 0 "")\n', *(f'\t(net {n} "{name}")\n' for n, name in enumerate(board.nets, start=1))]
    edge = (
        f"\t(gr_rect (start 0 0) (end {SIDE_MM} {SIDE_MM}) (stroke (width 0.1) (type default)) (fill no)"
        f' (layer "Edge.Cuts") (uuid "{board.uid("edge")}"))\n'
    )
    return _HEAD + "".join(nets) + "".join(board.items) + edge + ")\n"


def limits_project(root: Path, copies: Mapping[str, int]) -> Path:
    """A project folder under ``root`` holding the bench board, a ``{}`` project and the rules file."""
    root.mkdir(parents=True)
    (root / f"{STEM}.kicad_pcb").write_text(limits_board(copies), encoding="utf-8")
    (root / f"{STEM}.kicad_pro").write_text("{}\n", encoding="utf-8")
    (root / f"{STEM}.kicad_dru").write_text(RULES, encoding="utf-8")
    return root


def report_counts(
    cli: KicadCli, root: Path, *, options: Sequence[str] = ()
) -> tuple[dict[str, int], tuple[str, ...]]:
    """``(entries per type, sorted top-level keys)`` of one ``pcb drc --format json --severity-all`` run on
    the project in ``root``, with ``options`` added to the command. The unconnected items count under
    ``unconnected_items``."""
    files = {
        f"{STEM}{suffix}": root / f"{STEM}{suffix}" for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru")
    }
    args = [
        "pcb",
        "drc",
        "--format",
        "json",
        "--severity-all",
        *options,
        "-o",
        DRC_REPORT,
        f"{STEM}.kicad_pcb",
    ]
    run = cli.run(args, files=files)
    data = run.outputs.get(DRC_REPORT)
    assert data is not None, (run.outcome, run.returncode, run.stderr)
    report = json.loads(data.decode("utf-8"))
    counts = dict(Counter(entry["type"] for entry in report["violations"]))
    assert UNCONNECTED not in counts
    counts[UNCONNECTED] = len(report["unconnected_items"])
    return counts, tuple(sorted(report))


# -- the probes


RUNS: Mapping[str, tuple[Mapping[str, int], tuple[str, ...]]] = {
    "above": ({type_: ABOVE for type_ in TYPES}, ()),
    "below": ({type_: BELOW for type_ in BELOW_TYPES}, ()),
    "all-track-errors": ({"track_dangling": ABOVE}, ("--all-track-errors",)),
}
"""The three benches the probes run, each once per session: the copies per type and the added options."""


@cache
def counted(run: str) -> tuple[dict[str, int], tuple[str, ...]]:
    """``report_counts`` of the bench ``run`` of ``RUNS`` on the running ``kicad-cli``."""
    from _probes import runner  # _probes imports this module

    copies, options = RUNS[run]
    with tempfile.TemporaryDirectory(prefix="fenolite-limits-") as tmp:
        return report_counts(runner(), limits_project(Path(tmp) / run, copies), options=options)


def stated(type_: str, count: int, major: int) -> bool:
    """Whether ``count`` entries of ``type_`` at 700 copies is what ``H-K-DRC-LIMITS`` states for ``major``:
    the limit itself, except that 9.0.9 writes 499 or a few more ``clearance`` entries (``H-K-DRC-LIMIT``)."""
    if type_ == "clearance" and major == 9:
        return STATED[type_] <= count < ABOVE
    return count == STATED[type_]


def _major() -> int:
    from _probes import major

    return major()


def above(type_: str) -> str:
    """``equal`` when the count of ``type_`` at 700 copies is the stated limit, else ``different``; no
    entry of a type outside the bench may be in the report."""
    counts, _ = counted("above")
    if set(counts) - set(TYPES):
        return "different"
    return "equal" if stated(type_, counts.get(type_, 0), _major()) else "different"


def below() -> str:
    """``equal`` when each of the three types at 150 copies is written in full and nothing else is."""
    counts, _ = counted("below")
    wanted = {type_: BELOW for type_ in BELOW_TYPES}
    return "equal" if {t: n for t, n in counts.items() if n} == wanted else "different"


def all_track_errors() -> str:
    """``equal`` when ``--all-track-errors`` leaves ``track_dangling`` at the count of the plain run."""
    plain, _ = counted("above")
    lifted, _ = counted("all-track-errors")
    same = lifted.get("track_dangling") == plain.get("track_dangling") == STATED["track_dangling"]
    return "equal" if same else "different"


def keys() -> str:
    """``equal`` when the report of the bench has exactly the ten known top-level keys."""
    return "equal" if counted("above")[1] == REPORT_KEYS else "different"


def limit_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {
        "drc-limit-below": (below, both),
        "drc-limit-all-track-errors": (all_track_errors, both),
        "drc-limit-keys": (keys, both),
    }
    for type_ in TYPES:
        probes[f"drc-limit-{type_}"] = (lambda t=type_: above(t), both)
    return probes


__all__ = [
    "ABOVE",
    "BELOW",
    "BELOW_TYPES",
    "CONSTRUCTS",
    "REPORT_KEYS",
    "RULES",
    "STATED",
    "STEM",
    "TYPES",
    "UNCONNECTED",
    "counted",
    "limit_probes",
    "limits_board",
    "limits_project",
    "report_counts",
    "stated",
]
