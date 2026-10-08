# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The impedance bench (capability kicad-oracle, "Impedance targets pass the oracle"; hypotheses
H-K-PRO-TUNING-DRC and H-K-DRU-IMPEDANCE; change c0105).

A four-copper board written by ``write_board`` with the stack-up of the design of c0105 (0.2 mm prepreg,
1.065 mm core and 0.2 mm prepreg of permittivity 4.3, 35 µm copper), the classes ``SE50`` (a track on
``F.Cu`` and one on ``B.Cu``) and ``USB90`` (a pair on ``F.Cu``), class clearances of 0.2 mm, and the canary
scoped to its own net. The project is synthesised for the running major; the profiles are written by
``tuning.lower_profile`` and ``apply_profile_keys``, the rules by ``lower_rules``. Every verdict comes from
the JSON report of ``pcb drc``, and a run whose canary does not fire is ``inconclusive``.

The probes are not in ``_probes.PROBES`` yet: no ``kicad-cli`` ran where c0105 was implemented, and a probe
without a recorded outcome would fail ``test_probe_results``. ``tuning_probes`` and ``width_probes`` give
them for the commit that records them. The numbers are authored round values of a generic 1.6 mm board.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _rulebench as rb
import _rulecases as rc

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import _json, pro
from fenolite.backends.kicad._json import JsonObject
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.tuning import apply_profile_keys
from fenolite.core.ids import derived_id
from fenolite.model.board import StackLayer, Stackup
from fenolite.model.design import Design
from fenolite.model.rules import ImpedanceTarget, Rule, RuleSet, Selector, TraceGeometry

MM = rb.MM
CLEARANCE = 200_000
SE_WIDTH = 350_000
PAIR_WIDTH = 200_000
PAIR_GAP = 150_000
SEVERITY_KEY = "tuning_profile_track_geometries"
WIDTH_TYPES = frozenset({"track_width"})
GAP_TYPES = frozenset({"diff_pair_gap_out_of_range"})
MISSING_TYPES = frozenset({"missing_tuning_profile"})


def _id(prefix: str, n: int) -> str:
    return f"{prefix}_00000000-0000-4000-8000-{n:012d}"


def stackup() -> Stackup:
    """The stack-up of the bench, top to bottom, with the board's copper names."""
    entries = (
        ("F.Cu", "copper", 35_000, ""),
        ("dielectric 1", "dielectric", 200_000, "4.3"),
        ("In1.Cu", "copper", 35_000, ""),
        ("dielectric 2", "dielectric", 1_065_000, "4.3"),
        ("In2.Cu", "copper", 35_000, ""),
        ("dielectric 3", "dielectric", 200_000, "4.3"),
        ("B.Cu", "copper", 35_000, ""),
    )
    layers = tuple(
        StackLayer(id=_id("sly", n), name=name, kind=kind, thickness=thickness, epsilon_r=eps)  # type: ignore[arg-type]
        for n, (name, kind, thickness, eps) in enumerate(entries, start=1)
    )
    return Stackup(id=_id("stk", 1), layers=layers, impedance_controlled=True)


@dataclass(frozen=True)
class Tracks:
    """The widths of the bench's tracks and the pair gap, in nm; ``inner`` adds a track of ``SE50`` on
    ``In1.Cu`` (a layer without a row)."""

    se_front: int = SE_WIDTH
    se_back: int = SE_WIDTH
    pair_width: int = PAIR_WIDTH
    pair_gap: int = PAIR_GAP
    inner: int | None = None


@cache
def bench(tracks: Tracks) -> rb.Bench:
    made = rb.builder()
    made.netclass("SE50", CLEARANCE, "CLK", "CLK2", "CLK3")
    made.netclass("USB90", CLEARANCE, "USB_P", "USB_N")
    made.track("se_f", "CLK", made.row(), layer="F.Cu", width=tracks.se_front)
    made.track("se_b", "CLK2", made.row(), layer="B.Cu", width=tracks.se_back)
    if tracks.inner is not None:
        made.track("se_in", "CLK3", made.row(), layer="In1.Cu", width=tracks.inner)
    y = made.row()
    made.track("usb_a", "USB_P", y, layer="F.Cu", width=tracks.pair_width)
    made.track(
        "usb_b", "USB_N", y + tracks.pair_width + tracks.pair_gap, layer="F.Cu", width=tracks.pair_width
    )
    built = made.build()
    board = built.design.board
    assert board is not None
    design = dataclasses.replace(
        built.design, board=dataclasses.replace(board, layers=created_layers(4), stackup=stackup())
    )
    return rb.Bench(design, built.items)


def _class_id(design: Design, name: str) -> str:
    return next(c.id for c in design.circuit.netclasses if c.name == name)


def target(
    design: Design, name: str, cls: str, rows: tuple[TraceGeometry, ...], *, kind: str = "single"
) -> ImpedanceTarget:
    return ImpedanceTarget(
        id=derived_id("imp", "oracle", name),
        name=name,
        kind=kind,  # type: ignore[arg-type]
        netclass_ids=(_class_id(design, cls),),
        ohms="50" if kind == "single" else "90",
        layers=rows,
    )


SE_ROWS = (TraceGeometry("F.Cu", ("In1.Cu",), SE_WIDTH), TraceGeometry("B.Cu", ("In2.Cu",), SE_WIDTH))
PAIR_ROWS = (TraceGeometry("F.Cu", ("In1.Cu",), PAIR_WIDTH, PAIR_GAP),)


def project(design: Design, targets: tuple[ImpedanceTarget, ...], *, severity: str | None = None,
            class_keys: dict[str, str] | None = None) -> str:  # fmt: skip
    """The project of the running major with ``targets`` as profiles, the severity of
    ``tuning_profile_track_geometries`` when given, and class keys overridden by ``class_keys``."""
    major = rc.major()
    rules = design.rules or RuleSet(id=_id("rst", 1))
    with_targets = dataclasses.replace(design, rules=dataclasses.replace(rules, impedance=targets))
    text = pro.synthesize_project(with_targets, target=major, board_name="bench")
    text = apply_profile_keys(text, with_targets, target=major)
    data = _json.loads(text)
    if severity is not None:
        severities = _json.get(data, pro.SEVERITY_POINTER)
        assert isinstance(severities, dict)
        severities[SEVERITY_KEY] = severity
    for entry in data["net_settings"]["classes"]:
        item: JsonObject = entry
        if class_keys and item["name"] in class_keys:
            item["tuning_profile"] = class_keys[item["name"]]
    return _json.dumps(data)


def rule(name: str, kind: str, selector: Selector, *, layers: tuple[str, ...] = (), **limits: int) -> Rule:
    return Rule(
        id=derived_id("rul", "oracle", f"z:{name}"),
        name=name,
        kind=kind,  # type: ignore[arg-type]
        selector_a=selector,
        layers=layers,
        priority=1,
        **limits,  # type: ignore[arg-type]
    )


def derived_rules(*, pair: bool = False) -> tuple[Rule, ...]:
    """The rules ``to_model`` derives from the targets ``SE50`` and, with ``pair``, ``USB90``."""
    found = [
        rule(
            f"track_width_SE50_{r.layer}",
            "track_width",
            Selector("netclass", "SE50"),
            layers=(r.layer,),
            min=r.width,
            opt=r.width,
            max=r.width,
        )  # fmt: skip
        for r in SE_ROWS
    ]
    if pair:
        row = PAIR_ROWS[0]
        cls = Selector("netclass", "USB90")
        found.append(rule("track_width_USB90_F.Cu", "track_width", cls, layers=("F.Cu",),
                          min=row.width, opt=row.width, max=row.width))  # fmt: skip
        assert row.gap is not None
        found.append(rule("diff_pair_gap_USB90_F.Cu", "diff_pair_gap", cls, layers=("F.Cu",),
                          min=row.gap, opt=row.gap, max=row.gap))  # fmt: skip
    return tuple(found)


def rules_text(*rules: Rule, before: tuple[Rule, ...] = ()) -> str:
    """The scoped canary, then ``rules`` lowered for the running major; ``before`` is written ahead of the
    canary."""
    major = rc.major()
    head = (
        lower_rules(RuleSet(id=_id("rst", 2), rules=before), target=major).text if before else "(version 1)\n"
    )
    tail = lower_rules(RuleSet(id=_id("rst", 3), rules=rules), target=major).text
    return head + rb.scoped_canary_rule() + tail.partition("(version 1)\n")[2]


@dataclass(frozen=True)
class Run:
    report: DrcReport | None
    bench: rb.Bench

    @property
    def canary(self) -> bool:
        return self.report is not None and rb.canary_fired(self.report, self.bench)

    def of(self, label: str, types: frozenset[str]) -> bool:
        assert self.report is not None
        return any(v.type in types for v in rb.violations_of(self.report, self.bench.uuids(label)))

    def any_of(self, types: frozenset[str]) -> bool:
        assert self.report is not None
        return any(v.type in types for v in self.report.violations)

    def between(self, a: str, b: str, types: frozenset[str]) -> bool:
        assert self.report is not None
        found = rb.violations_between(self.report, self.bench.uuids(a), self.bench.uuids(b))
        return any(v.type in types for v in found)


def run(bench_: rb.Bench, project_text: str, rules: str) -> Run:
    """``pcb drc`` on the bench written for the running major with its project and rules."""
    major = rc.major()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(write_board(bench_.design, target=major).text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(project_text, encoding="utf-8")
        (folder / "bench.kicad_dru").write_text(rules, encoding="utf-8")
        files = {"bench.kicad_pro": folder / "bench.kicad_pro", "bench.kicad_dru": folder / "bench.kicad_dru"}
        result = rc.runner().drc(board, files=files)
    return Run(result.report, bench_)


# -- the profile cases (10.0 only) ------------------------------------------------------------------


@cache
def profile_run(case: str, severity: str | None = "error") -> Run:
    """One profile case of H-K-PRO-TUNING-DRC."""
    if case in ("width", "norow", "missing", "single-under-diff", "rule-governs"):
        made = bench(Tracks(se_back=300_000))
    elif case == "exact":
        made = bench(Tracks(se_front=SE_WIDTH + 1_000, se_back=SE_WIDTH - 100))
    elif case == "gap":
        made = bench(Tracks(pair_gap=PAIR_GAP + 50_000))
    else:  # gap-clearance, gap-clearance-rule: the pair at its gap, below the class clearance
        made = bench(Tracks())
    design = made.design
    se = target(design, "SE50", "SE50", SE_ROWS)
    usb = target(design, "USB90", "USB90", PAIR_ROWS, kind="differential")
    targets: tuple[ImpedanceTarget, ...] = (se, usb)
    keys: dict[str, str] | None = None
    rules: tuple[Rule, ...] = ()
    before: tuple[Rule, ...] = ()
    if case == "norow":
        targets = (dataclasses.replace(se, layers=SE_ROWS[:1]), usb)
    elif case == "missing":
        keys = {"SE50": "NOPE"}
    elif case == "single-under-diff":
        targets = (dataclasses.replace(se, kind="differential", layers=(
            TraceGeometry("F.Cu", ("In1.Cu",), SE_WIDTH, PAIR_GAP),
            TraceGeometry("B.Cu", ("In2.Cu",), SE_WIDTH, PAIR_GAP),
        )), usb)  # fmt: skip
    elif case == "rule-governs":
        rules = (rule("se50 width", "track_width", Selector("netclass", "SE50"), min=300_000),)
    elif case == "gap-clearance-rule":
        before = (rule("board clearance", "clearance", Selector("all"), min=CLEARANCE),)
    project_text = project(design, targets, severity=severity, class_keys=keys)
    return run(made, project_text, rules_text(*rules, before=before))


def _outcome(*runs: Run, found: Callable[[], bool]) -> str:
    if not all(r.canary for r in runs):
        return "inconclusive"
    return rb.outcome(found())


def width_profile_probe() -> str:
    """``present`` when a 50 µm narrower track is reported as ``track_width`` at ``error`` and at
    ``warning`` of ``tuning_profile_track_geometries``, and not at ``ignore``."""
    error, warning, ignore = (profile_run("width", s) for s in ("error", "warning", "ignore"))
    return _outcome(
        error,
        warning,
        ignore,
        found=lambda: (
            error.of("se_b", WIDTH_TYPES)
            and warning.of("se_b", WIDTH_TYPES)
            and not ignore.of("se_b", WIDTH_TYPES)
        ),
    )


def exact_probe() -> str:
    result = profile_run("exact")
    return _outcome(result, found=lambda: result.of("se_f", WIDTH_TYPES) and result.of("se_b", WIDTH_TYPES))


def norow_probe() -> str:
    result = profile_run("norow")
    return _outcome(result, found=lambda: result.of("se_b", WIDTH_TYPES))


def missing_probe() -> str:
    result = profile_run("missing")
    return _outcome(result, found=lambda: result.any_of(MISSING_TYPES))


def gap_probe() -> str:
    result = profile_run("gap")
    return _outcome(result, found=lambda: result.of("usb_a", GAP_TYPES) or result.of("usb_b", GAP_TYPES))


def single_under_diff_probe() -> str:
    result = profile_run("single-under-diff")
    return _outcome(result, found=lambda: result.of("se_b", WIDTH_TYPES))


def rule_governs_probe() -> str:
    """``present`` when the profile's width check still reports the B.Cu track beside a class rule whose
    minimum it meets; the design measured ``absent``: the custom rule replaces the check."""
    result = profile_run("rule-governs")
    return _outcome(result, found=lambda: result.of("se_b", WIDTH_TYPES))


def gap_clearance_probe(case: str) -> str:
    """``present`` when the pair at its gap, below the class clearance, gets a clearance finding between
    its two tracks (``ignore`` severity of the profile check)."""
    result = profile_run(case, "ignore")
    return _outcome(result, found=lambda: result.between("usb_a", "usb_b", frozenset({"clearance"})))


PROFILE_OUTCOMES: dict[str, str] = {
    "pro-tuning-width": "present",
    "pro-tuning-exact": "present",
    "pro-tuning-norow": "absent",
    "pro-tuning-missing": "present",
    "pro-tuning-gap": "present",
    "pro-tuning-single-under-diff": "absent",
    "pro-tuning-rule-governs": "absent",
    "pro-tuning-gap-clearance": "absent",
}
"""The outcomes the design of c0105 measured on 10.0.6 (2026-10-05); ``pro-tuning-gap-clearance-rule`` is
recorded either way."""


def tuning_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)``; ``_probes.PROBES`` takes all but the gap clearance under a rule."""
    ten = (10,)
    return {
        "pro-tuning-width": (width_profile_probe, ten),
        "pro-tuning-exact": (exact_probe, ten),
        "pro-tuning-norow": (norow_probe, ten),
        "pro-tuning-missing": (missing_probe, ten),
        "pro-tuning-gap": (gap_probe, ten),
        "pro-tuning-single-under-diff": (single_under_diff_probe, ten),
        "pro-tuning-rule-governs": (rule_governs_probe, ten),
        "pro-tuning-gap-clearance": (lambda: gap_clearance_probe("gap-clearance"), ten),
        "pro-tuning-gap-clearance-rule": (lambda: gap_clearance_probe("gap-clearance-rule"), ten),
    }


# -- the per-layer rules (both majors) --------------------------------------------------------------


@cache
def width_run() -> Run:
    """No profile; the derived rules of ``SE50``; ``F.Cu`` 1 µm above the row, ``B.Cu`` 50 µm below, and a
    track of the class on ``In1.Cu``, which has no row."""
    made = bench(Tracks(se_front=SE_WIDTH + 1_000, se_back=SE_WIDTH - 50_000, inner=300_000))
    project_text = project(made.design, ())
    return run(made, project_text, rules_text(*derived_rules()))


def width_rules_probe() -> str:
    result = width_run()
    return _outcome(
        result,
        found=lambda: (
            result.of("se_f", WIDTH_TYPES)
            and result.of("se_b", WIDTH_TYPES)
            and not result.of("se_in", WIDTH_TYPES)
        ),
    )


def width_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)``, in ``_probes.PROBES``."""
    return {"dru-impedance-width": (width_rules_probe, (9, 10))}


# -- the built design (both majors) -----------------------------------------------------------------


@cache
def built_run(narrow: bool) -> Run:
    """The design of ``tests/_zdesign.py`` with both targets built for the running major, with tracks drawn
    at the targets' widths and gap (``LED_DRV`` on ``F.Cu``, ``LED_A`` on ``B.Cu``, the pair on ``F.Cu``),
    ``LED_A`` 50 µm narrower with ``narrow``, and the scoped canary pair."""
    from _buildhelp import build
    from _zdesign import zdesign

    from fenolite.backends.kicad.pcb import kicad_uuid
    from fenolite.backends.kicad.triad import write_triad
    from fenolite.core.coords import Point
    from fenolite.dsl.convert import BOARD_ORIGIN
    from fenolite.model.board import Track
    from fenolite.model.circuit import Net

    major = rc.major()
    layout = build(zdesign(), target=major).layout
    assert layout is not None and layout.board is not None
    canaries = tuple(Net(id=derived_id("net", "oracle", f"z:{n}"), name=n) for n in rb.CANARY_NETS)
    nets = {net.name: net.id for net in (*layout.circuit.nets, *canaries)}
    rows = (
        ("se_f", "LED_DRV", "F.Cu", SE_WIDTH, 23 * MM, 2 * MM, 10 * MM),
        ("se_b", "LED_A", "B.Cu", SE_WIDTH - (50_000 if narrow else 0), 23 * MM, 2 * MM, 10 * MM),
        ("usb_a", "USB_P", "F.Cu", PAIR_WIDTH, 25 * MM, 2 * MM, 10 * MM),
        ("usb_b", "USB_N", "F.Cu", PAIR_WIDTH, 25 * MM + PAIR_WIDTH + PAIR_GAP, 2 * MM, 10 * MM),
        ("canary_a", rb.CANARY_NETS[0], "F.Cu", 250_000, 27 * MM, 30 * MM, 40 * MM),
        ("canary_b", rb.CANARY_NETS[1], "F.Cu", 250_000, 28 * MM, 30 * MM, 40 * MM),
    )
    tracks: list[Track] = []
    items: dict[str, tuple[str, ...]] = {}
    for label, net, layer, width, y, x0, x1 in rows:
        track = Track(
            id=derived_id("trk", "oracle", f"z:{label}"),
            start=Point(BOARD_ORIGIN.x + x0, BOARD_ORIGIN.y + y),
            end=Point(BOARD_ORIGIN.x + x1, BOARD_ORIGIN.y + y),
            width=width,
            layer=layer,
            net_id=nets[net],
        )
        tracks.append(track)
        items[label] = (kicad_uuid(track),)
    design = dataclasses.replace(
        layout,
        circuit=dataclasses.replace(layout.circuit, nets=(*layout.circuit.nets, *canaries)),
        board=dataclasses.replace(layout.board, tracks=(*layout.board.tracks, *tracks)),
    )
    files = write_triad(design, name="bench", target=major)
    return run_files(rb.Bench(design, items), files["bench.kicad_pcb"], files["bench.kicad_pro"],
                     rb.with_scoped_canary(files["bench.kicad_dru"]))  # fmt: skip


def run_files(bench_: rb.Bench, board_text: str, project_text: str, rules: str) -> Run:
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        board = folder / "bench.kicad_pcb"
        board.write_text(board_text, encoding="utf-8")
        (folder / "bench.kicad_pro").write_text(project_text, encoding="utf-8")
        (folder / "bench.kicad_dru").write_text(rules, encoding="utf-8")
        files = {"bench.kicad_pro": folder / "bench.kicad_pro", "bench.kicad_dru": folder / "bench.kicad_dru"}
        result = rc.runner().drc(board, files=files)
    return Run(result.report, bench_)


def dump(result: Run) -> str:
    """The violation types of a run, for ``-rA`` output and ``docs/evidence/impedance.md``."""
    if result.report is None:
        return "no report"
    return json.dumps(sorted({v.type for v in result.report.violations}))


__all__ = [
    "PROFILE_OUTCOMES",
    "Run",
    "Tracks",
    "bench",
    "built_run",
    "derived_rules",
    "dump",
    "profile_run",
    "project",
    "rules_text",
    "run",
    "run_files",
    "stackup",
    "target",
    "tuning_probes",
    "width_probes",
    "width_run",
]
