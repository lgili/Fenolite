# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net-tie bench (change c0114; capability kicad-oracle, "Net-tie facts are probed" and "Net-tie parity
canaries"; ``H-K-NETTIE-DRC``).

One board, written by ``write_board`` for a target, with one footprint per case on nets of its own. Every
footprint is an authored definition (``fenolite.dsl.Footprint`` through ``tests/_ties.py``), its groups
declared with ``Footprint.net_tie``; four cases also come in a copy without groups (``<case>-plain``). The
``spelling`` case is the ``touching`` footprint with its child edited to ``"1,2"`` in the written text. A
control pair, two 0.25 mm tracks of their own nets 0.1 mm apart, proves that the DRC judged the board: a
report without its ``clearance`` violation fails the test.

KiCad runs with a ``{}`` project, so its own ``Default`` class (0.2 mm) is in force. The Fenolite half
reads the same board text and takes the same 0.2 mm from the packaged project template of the target,
because a ``{}`` project gives ``check_copper`` no clearance in force. That half is hermetic
(``tests/kicad/copper/test_parity_bench.py``).

Every length is a round invented value; the form of the first footprint (two round pads joined by a filled
polygon on a copper layer) is the one KiCad's own net-tie library uses (S-0018, S-0042).
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Collection
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _ties import LIBRARY, MM, OVERLAP, ROUND, SQUARE, WIDTH, TieBoard, row, tie_footprint

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad import _json
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.copperrules import design_rules_from_texts
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.pro import template
from fenolite.backends.kicad.sexpr import Node, parse, walk
from fenolite.checks.copper import CopperFinding, CopperReport, check_copper
from fenolite.core.coords import Point
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
NAME = "ties"
BOARD, PROJECT = f"{NAME}.kicad_pcb", f"{NAME}.kicad_pro"
EMPTY_PROJECT = "{}\n"
SHORT, CLEAR, MASK, OPEN = "shorting_items", "clearance", "solder_mask_bridge", "unconnected_items"
COUNTED = frozenset({SHORT, CLEAR, MASK, OPEN})
"""The DRC types a case is judged by; every other type of the report is left out."""
TOUCH = SQUARE - OVERLAP
"""The pitch of two square pads that overlap by 0.2 mm."""
NEAR = SQUARE + MM // 10
"""The pitch of two square pads 0.1 mm apart: closer than the 0.2 mm in force."""
APART = SQUARE + 3 * MM // 20
"""The pitch of two square pads 0.15 mm apart."""
ROUND_PITCH = MM
"""The pitch of the two round pads: 0.5 mm apart edge to edge."""
COLUMN = 20 * MM
FIRST_ROW = 15 * MM
ROW = 6 * MM
PLAIN = "-plain"
ZERO_GAP = "actual 0.0000 mm"
"""How the description of a ``clearance`` violation states that the two items touch."""


@dataclass(frozen=True)
class Case:
    """One footprint of the bench: its pad centres, its groups, and the DRC types expected between two of
    its items, with the groups and (``plain``) in the copy without them (``None``: no such copy)."""

    name: str
    xs: tuple[int, ...]
    groups: tuple[tuple[str, ...], ...]
    expected: frozenset[str]
    plain: frozenset[str] | None = None
    official: bool = False
    track: bool = False
    spelling: bool = False


_SHORTED = frozenset({SHORT, MASK})
_ONE = (("1", "2"),)
CASES: tuple[Case, ...] = (
    Case("official", row(2, ROUND_PITCH), _ONE, frozenset(), _SHORTED, official=True),
    Case("touching", row(2, TOUCH), _ONE, frozenset(), _SHORTED),
    Case("close", row(2, NEAR), _ONE, frozenset(), frozenset({CLEAR})),
    Case(
        "track-near",
        row(2, ROUND_PITCH),
        _ONE,
        frozenset({CLEAR, OPEN}),
        frozenset({CLEAR, OPEN, SHORT, MASK}),
        official=True,
        track=True,
    ),
    Case("two-groups", row(4, TOUCH), (("1", "2"), ("3", "4")), frozenset({MASK})),
    Case("ungrouped-touching", row(3, TOUCH), _ONE, frozenset({MASK})),
    Case("ungrouped-close", (-TOUCH // 2, TOUCH // 2, TOUCH // 2 + APART), _ONE, frozenset()),
    Case(
        "groups-close",
        (-TOUCH // 2, TOUCH // 2, TOUCH // 2 + APART, TOUCH // 2 + APART + TOUCH),
        (("1", "2"), ("3", "4")),
        frozenset(),
    ),
    Case("spelling", row(2, TOUCH), _ONE, frozenset(), spelling=True),
    Case("three", row(3, TOUCH), (("1", "2", "3"),), frozenset()),
)
BY_NAME = {case.name: case for case in CASES}
LABELS: tuple[str, ...] = tuple(
    label
    for case in CASES
    for label in ((case.name, case.name + PLAIN) if case.plain is not None else (case.name,))
)
"""Every footprint of the bench: each case, and each copy without groups."""
COMPARED = ("touching", "close", "spelling", "three", "touching" + PLAIN, "close" + PLAIN)
"""The parity rows that must agree: grouped pads, and the same pads without a group."""
RECORDED: dict[str, tuple[str, str, str]] = {
    "two-groups": ("copper.short", "2", "3"),
    "ungrouped-touching": ("copper.short", "2", "3"),
    "ungrouped-close": ("copper.clearance", "2", "3"),
    "groups-close": ("copper.clearance", "2", "3"),
}
"""The documented difference: the one finding ``check_copper`` gives, naming the two pads that share no
group, where KiCad's DRC reports no short and no clearance between two pads of a net-tie footprint."""
VERDICT = {"copper.short": "short", "copper.clearance": "clearance"}


def case_of(label: str) -> tuple[Case, bool]:
    """The case of a footprint label and whether the footprint has its groups."""
    plain = label.endswith(PLAIN)
    return BY_NAME[label.removesuffix(PLAIN)], not plain


def expected(label: str) -> frozenset[str]:
    case, grouped = case_of(label)
    found = case.expected if grouped else case.plain
    assert found is not None
    return found


def _definition(case: Case, grouped: bool) -> object:
    name = case.name.replace("-", "_") + ("" if grouped else "_plain")
    groups = case.groups if grouped else ()
    if case.official:
        return tie_footprint(name, case.xs, groups=groups, size=ROUND, shape="circle", bridge=True)
    return tie_footprint(name, case.xs, groups=groups)


@dataclass(frozen=True)
class TieBench:
    """The bench of one target: the built design, the written board text, the reference of each
    footprint, and the KiCad uuids of every item of each footprint and of the control tracks."""

    target: int
    design: Design
    text: str
    refs: dict[str, str]
    pads: dict[str, dict[str, tuple[str, ...]]]
    items: dict[str, frozenset[str]]
    control: tuple[tuple[str, ...], tuple[str, ...]]


def _inner_uuids(root: Node, footprint_uuid: str) -> set[str]:
    """Every uuid inside the board footprint whose own uuid is ``footprint_uuid``."""
    for child in root.nodes("footprint"):
        own = child.find("uuid")
        if own is not None and own.atoms() and own.atoms()[0].value == footprint_uuid:
            found: set[str] = set()
            for _, node in walk(child):
                held = node.find("uuid")
                if held is not None and held.atoms():
                    found.add(held.atoms()[0].value)
            return found
    raise KeyError(footprint_uuid)


@cache
def tie_bench(target: int) -> TieBench:
    board = TieBoard()
    board.track("control_a", "CONTROL_A", Point(10 * MM, 5 * MM), Point(20 * MM, 5 * MM))
    offset = WIDTH + MM // 10
    board.track("control_b", "CONTROL_B", Point(10 * MM, 5 * MM + offset), Point(20 * MM, 5 * MM + offset))
    refs: dict[str, str] = {}
    tracks: dict[str, str] = {}
    for index, label in enumerate(LABELS):
        case, grouped = case_of(label)
        ref = f"NT{index + 1}"
        refs[label] = ref
        at = Point(COLUMN, FIRST_ROW + index * ROW)
        board.place(ref, _definition(case, grouped), at)  # type: ignore[arg-type]
        if case.track:
            start = Point(at.x + case.xs[1] + ROUND // 2 + MM // 10 + WIDTH // 2, at.y)
            board.track(f"{label}:track", f"{ref}_1", start, Point(start.x + 3 * MM, at.y))
            tracks[label] = f"{label}:track"
    design = board.build(height=FIRST_ROW + len(LABELS) * ROW + 10 * MM)
    text = write_board(design, target=target).text
    spelled = refs["spelling"]
    marker = f'(footprint "{LIBRARY}:spelling"'
    start = text.index(marker)
    token = '(net_tie_pad_groups "1, 2")'
    at_token = text.index(token, start)
    assert text.count(marker) == 1 and at_token - start < 2_000, spelled
    text = text[:at_token] + '(net_tie_pad_groups "1,2")' + text[at_token + len(token) :]
    root = parse(text)
    items: dict[str, frozenset[str]] = {}
    pads: dict[str, dict[str, tuple[str, ...]]] = {}
    for label, ref in refs.items():
        found = _inner_uuids(root, board.uuids[ref][0])
        if label in tracks:
            found |= set(board.uuids[tracks[label]])
        items[label] = frozenset(found)
        case, _ = case_of(label)
        pads[label] = {str(n): board.uuids[f"{ref}:{n}"] for n in range(1, len(case.xs) + 1)}
    control = (board.uuids["control_a"], board.uuids["control_b"])
    return TieBench(target, design, text, refs, pads, items, control)


# --- the Fenolite half (hermetic) -----------------------------------------------------------------


@cache
def fenolite_report(target: int) -> tuple[CopperReport, dict[str, str]]:
    """``check_copper`` on the bench read back from its written text, under the ``Default`` class of the
    packaged project template (0.2 mm), and the map from entity id to KiCad uuid."""
    bench = tie_bench(target)
    design = read_board(bench.text, file=BOARD)
    rules = design_rules_from_texts(
        design, project_text=_json.dumps(template(target)), rules_text=None, major=target, file_stem=NAME
    )
    assert not rules.unread and not rules.opaque_clearance_rules
    report = check_copper(
        rules.design,
        pads=KicadBackend().board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
    )
    assert not report.summary["unsupported"], report.summary["unsupported"]
    board = rules.design.board
    assert board is not None
    entities = [*board.tracks, *(pad for footprint in board.footprints for pad in footprint.pads)]
    return report, {e.id: e.native_ids["kicad"] for e in entities if "kicad" in e.native_ids}


def pad_findings(target: int, label: str) -> list[tuple[str, str, str]]:
    """``(code, pad number, pad number)`` of every finding of ``check_copper`` between two pads of the
    footprint ``label``, the numbers in order."""
    bench = tie_bench(target)
    report, uuid_of = fenolite_report(target)
    number_of = {uuid: number for number, uuids in bench.pads[label].items() for uuid in uuids}
    found: list[tuple[str, str, str]] = []
    for finding in report.findings:
        numbers = [number_of.get(uuid_of.get(item.entity_id, "")) for item in finding.items]
        if numbers[0] is not None and numbers[1] is not None:
            first, second = sorted((numbers[0], numbers[1]))
            found.append((finding.code, first, second))
    return sorted(found)


def other_findings(target: int) -> list[CopperFinding]:
    """The findings that are not between two pads of one footprint of the bench."""
    bench = tie_bench(target)
    report, uuid_of = fenolite_report(target)
    owner = {uuid: label for label, pads in bench.pads.items() for uuids in pads.values() for uuid in uuids}
    return [
        finding
        for finding in report.findings
        if len({owner.get(uuid_of.get(item.entity_id, ""), item.entity_id) for item in finding.items}) != 1
    ]


def fenolite_verdict(target: int, label: str) -> str:
    """``short``, ``clearance`` or ``clean`` for the pads of the footprint ``label``."""
    codes = {code for code, _, _ in pad_findings(target, label)}
    return "short" if "copper.short" in codes else "clearance" if "copper.clearance" in codes else "clean"


# --- KiCad's half ---------------------------------------------------------------------------------


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def running_target() -> int:
    return runner().major()


@cache
def kicad_report() -> DrcReport | None:
    """``pcb drc`` on the bench written for the running major, with a ``{}`` project next to it."""
    bench = tie_bench(running_target())
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / BOARD).write_text(bench.text, encoding="utf-8")
        (folder / PROJECT).write_text(EMPTY_PROJECT, encoding="utf-8")
        return runner().drc(folder / BOARD, files={PROJECT: folder / PROJECT}).report


def judged_report() -> DrcReport:
    """The report, after failing the test when the control pair's ``clearance`` violation is absent."""
    report = kicad_report()
    bench = tie_bench(running_target())
    first, second = (set(uuids) for uuids in bench.control)
    fired = report is not None and any(
        violation.type == CLEAR
        and {i.uuid for i in violation.items} & first
        and {i.uuid for i in violation.items} & second
        for violation in report.violations
    )
    if not fired:
        pytest.fail(
            "the DRC did not judge the bench: the control pair's clearance violation is absent", pytrace=False
        )
    assert report is not None
    return report


def _types(report: DrcReport, uuids: Collection[str]) -> frozenset[str]:
    wanted = set(uuids)
    entries = (*report.violations, *report.unconnected_items)
    return frozenset(_kind(v) for v in entries if {item.uuid for item in v.items} & wanted) & COUNTED


def _kind(violation: DrcViolation) -> str:
    """The type a violation is counted as: its own, except that a ``clearance`` entry whose actual distance
    is 0 counts as ``shorting_items``. KiCad reports copper of one net that touches a netless copper
    graphic under either type (seen on 10.0.6: one pad of the bridged footprint each way in one run), so
    the two are one fact here: the copper touches."""
    touching = violation.type == CLEAR and ZERO_GAP in violation.description
    return SHORT if touching else violation.type


def kicad_types(label: str) -> frozenset[str]:
    """The counted DRC types of the entries that name an item of the footprint ``label`` (its pads, its
    graphics, its fields, and the track of the ``track-near`` case)."""
    return _types(judged_report(), tie_bench(running_target()).items[label])


def kicad_pad_verdict(label: str) -> str:
    """``short``, ``clearance`` or ``clean`` from the ``shorting_items`` and ``clearance`` violations that
    name two pads of the footprint ``label``."""
    report = judged_report()
    pads = {uuid for uuids in tie_bench(running_target()).pads[label].values() for uuid in uuids}
    found = {v.type for v in report.violations if len({item.uuid for item in v.items} & pads) >= 2}
    return "short" if SHORT in found else "clearance" if CLEAR in found else "clean"


def fact(label: str) -> str:
    return "equal" if kicad_types(label) == expected(label) else "different"


def parity_group() -> str:
    target = running_target()
    return (
        "equal" if all(kicad_pad_verdict(c) == fenolite_verdict(target, c) for c in COMPARED) else "different"
    )


def parity_ungrouped() -> str:
    target = running_target()
    return (
        "equal" if all(kicad_pad_verdict(c) == fenolite_verdict(target, c) for c in RECORDED) else "different"
    )


def tie_probes() -> Probes:
    both = (9, 10)
    probes: Probes = {f"nettie-{label}": (lambda label=label: fact(label), both) for label in LABELS}
    probes["copper-nettie-group"] = (parity_group, both)
    probes["copper-nettie-ungrouped"] = (parity_ungrouped, both)
    return probes


__all__ = [
    "BY_NAME",
    "CASES",
    "COMPARED",
    "COUNTED",
    "LABELS",
    "RECORDED",
    "Case",
    "TieBench",
    "case_of",
    "expected",
    "fact",
    "fenolite_report",
    "fenolite_verdict",
    "judged_report",
    "kicad_pad_verdict",
    "kicad_report",
    "kicad_types",
    "other_findings",
    "pad_findings",
    "tie_bench",
    "tie_probes",
]
