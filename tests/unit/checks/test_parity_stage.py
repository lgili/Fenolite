# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``parity`` stage (capability verification-loop, "Parity stage"; change c0072). The project is the
blink as ``build`` writes it, on disk; the DRC oracle is a fake whose parity entries the test chooses, so
no tool runs."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import _parityedit as edits
import fakes
import pytest
from _buildhelp import blink, build
from _schbuild import built_nested, write_files

from fenolite.backends.base import DrcItem, DrcViolation, ParityInputs, ProjectSet
from fenolite.backends.kicad import sch_netlist
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks import parity
from fenolite.checks.parity_stage import differences
from fenolite.checks.stages import (
    DEFAULT_STAGES,
    ORACLE_STAGES,
    STAGE_ORDER,
    CheckReport,
    StageResult,
    run_checks,
)
from fenolite.core.coords import Point
from fenolite.core.evidence import Level

DATA = Path(__file__).resolve().parents[2] / "data" / "kicad"
BOARD, SHEET = "blink.kicad_pcb", "blink.kicad_sch"


def project(folder: Path, change: object = None, *, schematic: bool = True) -> ProjectSet:
    """The blink under ``folder``, its board after ``change`` (a function of its text)."""
    files = build(blink(), 10).files
    text = files[BOARD].decode("utf-8")
    (folder / BOARD).write_text(change(text) if callable(change) else text, encoding="utf-8")
    if schematic:
        (folder / SHEET).write_bytes(files[SHEET])
    return project_set(folder / BOARD)


def uuid_of(folder: Path, ref: str, pad: str = "") -> str:
    """KiCad's id of the footprint ``ref`` of the board under ``folder``, or of its pad ``pad``."""
    design = read_board((folder / BOARD).read_text(encoding="utf-8"), file=BOARD)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    (footprint,) = [f for f in design.board.footprints if refs[f.component_id] == ref]
    if not pad:
        return footprint.native_ids["kicad"]
    return next(p.native_ids["kicad"] for p in footprint.pads if p.number == pad)


def entry(kind: str, description: str = "", *uuids: str) -> DrcViolation:
    items = tuple(DrcItem(uuid, "item", Point(0, 0)) for uuid in uuids)
    return DrcViolation(kind, description or kind, "warning", items)


def checked(found: ProjectSet, *stages: str, parity_entries: tuple[DrcViolation, ...] | None = None,
            oracle: object = None) -> CheckReport:  # fmt: skip
    """``run_checks`` with the KiCad backend; ``parity_entries`` makes a fake DRC oracle named ``kicad``
    that judged parity with those entries."""
    if parity_entries is not None:
        outcome = fakes.outcome(drc=fakes.report(parity=parity_entries), parity_judged=True)
        oracle = fakes.FakeOracle(outcome, name="kicad")
    return run_checks(
        project=found,
        stages=stages,
        model=None,
        built=False,
        validator=KicadBackend(),
        oracle=oracle,  # type: ignore[arg-type]
    )


def stage(report: CheckReport, name: str = "parity") -> StageResult:
    return next(s for s in report.stages if s.name == name)


def codes(result: StageResult) -> list[tuple[str, str]]:
    return [(i.code, i.where) for i in result.issues]


def on_gnd(text: str) -> str:
    return edits.renet(text, "R1", "2", "GND")


def test_stage_order_and_kind() -> None:
    at = STAGE_ORDER.index("parity")
    assert STAGE_ORDER[at - 1] == "drc.kicad" and at < STAGE_ORDER.index("roundtrip")
    assert "parity" in DEFAULT_STAGES and "parity" not in ORACLE_STAGES
    assert isinstance(KicadBackend(), ParityInputs)


def test_without_kicad(tmp_path: Path) -> None:
    result = stage(checked(project(tmp_path, on_gnd), "parity"))
    assert result.status == "errors" and codes(result) == [("parity.net-conflict", "R1-2")]
    assert result.issues[0].severity == "error" and "GND" in result.issues[0].message
    assert result.summary["netlist"] == "own" and result.summary["compared"] is False
    assert result.summary["parity.net-conflict"] == 1 and result.summary["nets_split"] == 1
    assert result.summary["differences"] == 0
    assert result.evidence.level is Level.INFERRED
    assert set(result.evidence.hypotheses) == {"H-K-PARITY-OWN", *sch_netlist.EVIDENCE.hypotheses}


def test_hierarchical_project(tmp_path: Path) -> None:
    """A design with module sheets: the own netlist covers the tree, so no tool is needed (c0070)."""
    root = write_files(built_nested(), tmp_path / "nested")
    board = root / "nested.kicad_pcb"
    result = stage(checked(project_set(board), "parity"))
    assert result.status == "ok" and result.issues == () and result.summary["netlist"] == "own"
    board.write_text(edits.renet(board.read_text(encoding="utf-8"), "C1", "2", "VIN"), encoding="utf-8")
    result = stage(checked(project_set(board), "parity"))
    assert result.status == "errors" and codes(result) == [("parity.net-conflict", "C1-2")]


def test_agreeing_project(tmp_path: Path) -> None:
    result = stage(checked(project(tmp_path), "parity"))
    assert result.status == "ok" and result.issues == ()
    assert all(result.summary[key] == 0 for key in parity.SUMMARY_KEYS)


def test_agreement_with_the_oracle(tmp_path: Path) -> None:
    found = project(tmp_path, on_gnd)
    conflict = entry("net_conflict", "Pad net (GND) doesn't match", uuid_of(tmp_path, "R1", "2"))
    report = checked(found, "drc.kicad", "parity", parity_entries=(conflict,))
    assert ("kicad.drc.net-conflict", "R1-2") in codes(stage(report, "drc.kicad"))
    result = stage(report)
    assert result.issues == () and result.status == "ok"
    assert result.summary["compared"] is True and result.summary["differences"] == 0
    assert result.summary["parity.net-conflict"] == 1  # counted, and not reported twice
    assert stage(report, "drc.kicad").evidence.level is Level.KICAD_VERIFIED


def test_disagreement_is_reported(tmp_path: Path) -> None:
    found = project(tmp_path, on_gnd)
    result = stage(checked(found, "drc.kicad", "parity", parity_entries=()))
    assert codes(result) == [("parity.oracle-differs", "R1-2")]
    (differs,) = result.issues
    assert differs.severity == "warning" and result.status == "ok"
    assert "net_conflict" in differs.message and "fenolite reports it" in differs.message
    assert result.summary["compared"] is True and result.summary["differences"] == 1
    # the other way: the oracle holds an entry that Fenolite does not
    conflict = entry("net_conflict", "", uuid_of(tmp_path, "R1", "2"))
    missing = entry("missing_footprint", "Missing footprint R7 (1k)")
    result = stage(checked(found, "drc.kicad", "parity", parity_entries=(conflict, missing)))
    assert codes(result) == [("parity.oracle-differs", "R7")]
    assert "missing_footprint" in result.issues[0].message and "kicad reports it" in result.issues[0].message


def test_oracle_entries_by_reference(tmp_path: Path) -> None:
    """A renamed footprint: the oracle's entry for the missing one names it in its text only."""
    found = project(tmp_path, lambda text: edits.rename(text, "R1", "R99"))
    entries = (
        entry("missing_footprint", "Missing footprint R1 (330)"),
        entry("extra_footprint", "Extra footprint", uuid_of(tmp_path, "R99")),
    )
    result = stage(checked(found, "drc.kicad", "parity", parity_entries=entries))
    assert result.issues == () and result.summary["refs_one_side"] == 2
    # a text without the reference: the missing footprints are compared by their number
    untold = (entry("missing_footprint", "manquant"), entries[1])
    assert stage(checked(found, "drc.kicad", "parity", parity_entries=untold)).issues == ()


def test_symbol_and_footprint_findings_are_always_reported(tmp_path: Path) -> None:
    found = project(tmp_path, lambda text: edits.drop_pad(text, "R1", "2"))
    alone = stage(checked(found, "parity"))
    assert codes(alone) == [("parity.pin-without-pad", "R1-2")] and alone.status == "errors"
    # KiCad reports the same pin as a net conflict of the footprint
    entries = (entry("net_conflict", "No pad found for pin 2", uuid_of(tmp_path, "R1")),)
    result = stage(checked(found, "drc.kicad", "parity", parity_entries=entries))
    assert codes(result) == [("parity.pin-without-pad", "R1-2")] and result.summary["differences"] == 0


def test_parity_not_judged_by_the_oracle(tmp_path: Path) -> None:
    found = project(tmp_path, on_gnd)
    oracle = fakes.FakeOracle(fakes.outcome(parity_judged=False), name="kicad")
    result = stage(checked(found, "drc.kicad", "parity", oracle=oracle))
    assert codes(result) == [("parity.net-conflict", "R1-2")] and result.summary["compared"] is False


def test_no_schematic(tmp_path: Path) -> None:
    result = stage(checked(project(tmp_path, schematic=False), "parity"))
    assert (result.status, result.reason) == ("skipped", "no-schematic")


def wired(folder: Path) -> ProjectSet:
    """The blink board beside an authored schematic that holds wires: outside the own netlist."""
    found = project(folder, schematic=False)
    text = (DATA / "schematic" / "flat.kicad_sch").read_text(encoding="utf-8")
    (folder / SHEET).write_text(text, encoding="utf-8")
    return project_set(found.root / BOARD)


def test_netlist_unavailable(tmp_path: Path) -> None:
    result = stage(checked(wired(tmp_path), "parity"))
    assert (result.status, result.reason) == ("skipped", "netlist-unavailable")
    # an oracle that cannot export a schematic netlist changes nothing
    result = stage(checked(wired(tmp_path), "parity", oracle=fakes.FakeOracle()))
    assert (result.status, result.reason) == ("skipped", "netlist-unavailable")


def test_netlist_from_the_oracle(tmp_path: Path) -> None:
    found = wired(tmp_path)
    nets = fakes.netlist("schematic", ("R1-1", "LED_DRV"), ("R1-2", "LED_A"))
    oracle = fakes.FakeSchematicOracle(schematic_result=fakes.netlist_outcome(nets))
    result = stage(checked(found, "parity", oracle=oracle))
    assert result.status == "errors" and result.summary["netlist"] == "oracle"
    assert len(oracle.schematic_calls) == 1 and "H-FAKE-DRC" in result.evidence.hypotheses
    # the authored schematic is another circuit: its references are missing on the blink board
    assert result.summary["refs_one_side"] > 0
    # no export: an error of the stage, never a silent pass
    failing = fakes.FakeSchematicOracle(schematic_result=fakes.netlist_outcome(None))
    failed = stage(checked(found, "parity", oracle=failing))
    assert [i.code for i in failed.issues] == ["check.oracle-failed"] and failed.status == "errors"


def test_unreadable_schematic(tmp_path: Path) -> None:
    found = project(tmp_path)
    (tmp_path / SHEET).write_text("(kicad_sch (version", encoding="utf-8")
    result = stage(checked(found, "parity"))
    assert [i.code for i in result.issues] == ["check.read-refused"] and result.status == "errors"
    assert result.issues[0].where.startswith(SHEET)


def test_board_read_refused(tmp_path: Path) -> None:
    found = project(tmp_path)
    (tmp_path / BOARD).write_text("(kicad_pcb (version", encoding="utf-8")
    result = stage(checked(found, "parity"))
    assert (result.status, result.reason) == ("skipped", "read-refused")


def test_differences() -> None:
    own = Counter({("net_conflict", "R1-2"): 2, ("missing_footprint", "R1"): 1})
    oracle = Counter(
        {("net_conflict", "R1-2"): 1, ("extra_footprint", "X1"): 1, ("missing_footprint", "R1"): 1}
    )
    assert differences(own, oracle) == [
        ("extra_footprint", "X1", "kicad"),
        ("net_conflict", "R1-2", "fenolite"),
    ]
    # without a reference in the oracle's text, missing footprints are counted
    untold = Counter({("missing_footprint", ""): 2})
    assert differences(own, untold) == [
        ("missing_footprint", "", "kicad"),
        ("net_conflict", "R1-2", "fenolite"),
        ("net_conflict", "R1-2", "fenolite"),
    ]


@pytest.mark.parametrize("stages", [("parity",), ("drc.kicad", "parity")])
def test_two_runs_are_equal(tmp_path: Path, stages: tuple[str, ...]) -> None:
    found = project(tmp_path, on_gnd)
    entries = () if "drc.kicad" in stages else None
    first = stage(checked(found, *stages, parity_entries=entries))
    again = stage(checked(found, *stages, parity_entries=entries))
    assert first == again
