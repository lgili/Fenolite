# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The oracle runs of the net class pair values (capability kicad-oracle, "Net class pair values are
probed"; hypothesis H-K-PRO-PAIR; change c0104).

Each run builds a bench of 0.2 mm tracks on ``F.Cu`` through the triad path: the model classes carry
their pair values into the project, the nets get exact-name patterns, and the rules are model rules. The
canary is the scoped one of c0010, a model rule of priority 99, so a board-wide rule of priority 0 is
written before it and every other rule after it. ``min_clearance`` of the project is set by the run: 0
unless the run is about the board minimum.

Classes (clearance / pair gap / pair width / pair via gap, in mm):

- ``DPA``: 0.2 / 0.1 / 0.3 / 0.5, a pair gap below the clearance;
- ``DPB``: 0.2 / 0.25 / 0.2 / 0.25, a pair gap above it;
- ``DPC``: 0.1 / 0.4 / 0.3 / 0.25, a pair gap and width that the row's tracks do not have.

Net names and values are authored for these benches.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

import _pairbench as pb
import _rulebench as rb
import _rulecases as rc

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.units import format_length
from fenolite.model.circuit import NetClass
from fenolite.model.rules import Selector

NAME = "bench"
BOARD, PROJECT = f"{NAME}.kicad_pcb", f"{NAME}.kicad_pro"
WIDTH = 200_000
NEAR = 150_000
"""The gap of most rows: below the class clearance of 0.2 mm and above the pair gap of 0.1 mm."""
CLASSES: Mapping[str, tuple[int, int, int, int]] = MappingProxyType(
    {
        "DPA": (200_000, 100_000, 300_000, 500_000),
        "DPB": (200_000, 250_000, 200_000, 250_000),
        "DPC": (100_000, 400_000, 300_000, 250_000),
    }
)
"""Class → clearance, pair gap, pair width and pair via gap in nm."""
CLEARANCE = frozenset({"clearance"})
PAIR_GAP = frozenset({"diff_pair_gap_out_of_range"})


@dataclass(frozen=True)
class Run:
    bench: rb.Bench
    report: DrcReport | None
    files: Mapping[str, str]

    @property
    def canary(self) -> bool:
        return self.report is not None and rb.canary_fired(self.report, self.bench)

    def types(self, label: str) -> frozenset[str]:
        """The violation types that name an item of each track (or via) of the row ``label``."""
        assert self.report is not None
        a, b = self.bench.uuids(f"{label}_a"), self.bench.uuids(f"{label}_b")
        found = {v.type for v in rb.violations_between(self.report, a, b)}
        return frozenset(found - rc.IGNORED_TYPES)

    def any_types(self, label: str) -> frozenset[str]:
        """The violation types that name any item of the row ``label``, the warnings every free item
        gets left out."""
        assert self.report is not None
        uuids = (*self.bench.uuids(f"{label}_a"), *self.bench.uuids(f"{label}_b"))
        return frozenset({v.type for v in rb.violations_of(self.report, uuids)} - rc.IGNORED_TYPES)


class _Maker:
    def __init__(self) -> None:
        self.made = rb.builder()
        self.count = 0
        for index, (name, (clearance, gap, width, via_gap)) in enumerate(CLASSES.items(), start=1):
            self.made.classes[name] = NetClass(
                id=f"cls_00000000-0000-4000-8000-{index:012d}",
                name=name,
                clearance=clearance,
                diff_pair_gap=gap,
                diff_pair_width=width,
                diff_pair_via_gap=via_gap,
            )
        self.rule("canary", "clearance", Selector("net", rb.CANARY_NETS[0]), min=3 * rb.MM, priority=99)

    def rule(self, name: str, kind: str, a: Selector, *, priority: int = 1, **fields: object) -> None:
        self.count += 1
        made = pb.rule(name, kind, a, priority=priority, **fields)  # type: ignore[arg-type]
        self.made.rule(dataclasses.replace(made, id=f"rul_00000000-0000-4000-8000-{self.count:012d}"))

    def pair(
        self, base: str, netclass: str, gap: int = NEAR, *, names: tuple[str, str] | None = None
    ) -> None:
        positive, negative = names if names is not None else (f"{base}_P", f"{base}_N")
        self.made.pair(base, positive, negative, gap=gap, width=WIDTH)
        self.made.assign(netclass, positive, negative)

    def inside(self, base: str, minimum: int = 100_000) -> None:
        """A clearance rule with the pair on both sides."""
        selector = pb.dp(f"{base}_")
        self.rule(f"inside {base}", "clearance", selector, selector_b=selector, min=minimum)

    def run(self, *, min_clearance: int = 0) -> Run:
        bench = self.made.build()
        with pb.pair_support():
            files = write_triad(bench.design, name=NAME, target=rc.major())
        data = _json.loads(files[PROJECT])
        text = format_length(min_clearance, "mm")[: -len("mm")]
        data["board"]["design_settings"]["rules"]["min_clearance"] = JsonNumber(text)  # type: ignore[index]
        files[PROJECT] = _json.dumps(data)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name, content in files.items():
                (folder / name).write_text(content, encoding="utf-8")
            extra = {name: folder / name for name in files if name != BOARD}
            report = rc.runner().drc(folder / BOARD, files=extra).report
        return Run(bench, report, files)


@cache
def classes() -> Run:
    """The class rows, with no custom rule but the canary and one gap rule on a pair of its own."""
    maker = _Maker()
    maker.pair("CA", "DPA")
    maker.pair("CB", "DPB")
    maker.pair("CC", "DPA", names=("CC_A", "CC_B"))
    maker.pair("CF", "DPC")
    maker.made.via_pair("CV", "CV_P", "CV_N", gap=300_000)
    maker.made.assign("DPA", "CV_P", "CV_N")
    maker.pair("CD", "DPB")
    maker.rule("gap cd", "diff_pair_gap", pb.dp("CD_"), min=100_000)
    return maker.run()


@cache
def shadow() -> Run:
    """A board-wide clearance rule of 0.2 mm before the canary; one pair has a clearance rule of its own."""
    maker = _Maker()
    maker.rule("board", "clearance", Selector("all"), min=200_000, priority=0)
    maker.pair("CA", "DPA")
    maker.pair("CE", "DPA")
    maker.inside("CE")
    return maker.run()


@cache
def floor() -> Run:
    """A board minimum of 0.12 mm above the pair gap of 0.1 mm, with pairs 0.11 and 0.13 mm apart."""
    maker = _Maker()
    maker.pair("FA", "DPA", 110_000)
    maker.pair("FB", "DPA", 130_000)
    return maker.run(min_clearance=120_000)


@cache
def floor_gap() -> Run:
    """A board minimum of 0.2 mm and pairs 0.15 mm apart under a clearance rule of their own; the second
    also has a gap rule of 0.1 mm."""
    maker = _Maker()
    maker.pair("FG", "DPA")
    maker.inside("FG")
    maker.pair("FH", "DPA")
    maker.inside("FH")
    maker.rule("gap fh", "diff_pair_gap", pb.dp("FH_"), min=100_000)
    return maker.run(min_clearance=200_000)


def _judged(run: Run, found: bool) -> str:
    return rb.outcome(found) if run.canary else "inconclusive"


CASES: Mapping[str, tuple[Callable[[], str], str]] = MappingProxyType(
    {
        "gap-lowers": (lambda: _judged(classes(), "clearance" in classes().types("CA")), "absent"),
        "gap-above": (lambda: _judged(classes(), "clearance" in classes().types("CB")), "present"),
        "not-a-pair": (lambda: _judged(classes(), "clearance" in classes().types("CC")), "present"),
        "no-limits": (lambda: _judged(classes(), bool(classes().any_types("CF"))), "absent"),
        "via-gap": (lambda: _judged(classes(), bool(classes().any_types("CV"))), "absent"),
        "gap-rule-clearance": (lambda: _judged(classes(), "clearance" in classes().types("CD")), "present"),
        "rule-shadows": (lambda: _judged(shadow(), "clearance" in shadow().types("CA")), "present"),
        "rule-restores": (lambda: _judged(shadow(), "clearance" in shadow().types("CE")), "absent"),
        "floor": (
            lambda: _judged(
                floor(), floor().types("FA") >= (CLEARANCE | PAIR_GAP) and not floor().any_types("FB")
            ),
            "present",
        ),
        "floor-gap": (lambda: _judged(floor_gap(), bool(floor_gap().types("FG") & PAIR_GAP)), "present"),
        "floor-gap-rule": (
            lambda: _judged(floor_gap(), bool(floor_gap().types("FH") & (CLEARANCE | PAIR_GAP))),
            "absent",
        ),
    }
)
"""Case → its probe function and the outcome the design measured."""
RUNS: Mapping[str, Callable[[], Run]] = MappingProxyType(
    {
        **dict.fromkeys(
            ("gap-lowers", "gap-above", "not-a-pair", "no-limits", "via-gap", "gap-rule-clearance"), classes
        ),
        "rule-shadows": shadow,
        "rule-restores": shadow,
        "floor": floor,
        "floor-gap": floor_gap,
        "floor-gap-rule": floor_gap,
    }
)
"""Case → the run that judges it."""


def pair_class_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    return {f"pro-pair-{case}": (function, (9, 10)) for case, (function, _) in CASES.items()}


__all__ = ["CASES", "CLASSES", "RUNS", "Run", "classes", "floor", "floor_gap", "pair_class_probes", "shadow"]
