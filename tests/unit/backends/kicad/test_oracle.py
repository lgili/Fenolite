# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadOracle`` with a fake ``kicad-cli`` (capability kicad-oracle, "Check canary injection";
"Netlist oracle from IPC-D-356" and "RT2 oracle"; backend-protocol, "Oracle protocol" and "Netlist and
round-trip oracles"; changes c0013 and c0020). Hermetic: the fake reports the canary pair as KiCad would."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import _ipc
import pytest
from _fakecli import calls, erc_entry, erc_report_with, fake_kicad_cli, report_with
from _projects import (
    STEM,
    authored_project,
    built_blink_project,
    hierarchy_project,
    native_project,
    tree_snapshot,
)
from _resources import posix_tools

from fenolite.backends.base import (
    ErcOracle,
    NetlistOracle,
    Oracle,
    PadAssignment,
    Plotter,
    RoundTripOracle,
    SchematicNetlistOracle,
)
from fenolite.backends.kicad import canary
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad import erc as ercmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad import sch as schmod
from fenolite.backends.kicad.canary import CANARY_RULE_NAME, CANARY_UUIDS
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.backends.kicad.sch import read_schematic, rebuild_schematic
from fenolite.backends.kicad.sexpr import dumps
from fenolite.backends.kicad.sexpr import parse as parse_tree
from fenolite.core.evidence import Evidence, Level, strength


def _oracle(tmp_path: Path, **fake: object) -> tuple[KicadOracle, Path]:
    script = fake_kicad_cli(tmp_path / "bin", **fake)  # type: ignore[arg-type]
    cli = KicadCli(script, timeout=60.0)
    if fake.get("sleep"):
        # The quick ``version`` call runs under the generous limit and is cached, so that a loaded machine
        # cannot make it late; only the sleeping calls get the short limit.
        cli.version()
        cli.timeout = 1.0
    return KicadOracle(cli), script


def _drc_calls(script: Path) -> list[dict[str, object]]:
    return [c for c in calls(script) if c["args"][:2] == ["pcb", "drc"]]  # type: ignore[index]


def test_refill_copies_project_without_canary(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    saved = Path(__file__).resolve().parents[3] / "data" / "kicad" / "fill" / "triad_t9_refilled.kicad_pcb"
    oracle, script = _oracle(tmp_path, refill_board=saved.read_text(encoding="utf-8"))
    before = tree_snapshot(root)
    result = oracle.refill(project_set(root))
    call, repeat = _drc_calls(script)
    files: dict[str, str] = call["files"]  # type: ignore[assignment]
    assert files[board.name] == board.read_text(encoding="utf-8")
    assert CANARY_RULE_NAME not in files[f"{STEM}.kicad_dru"]
    assert repeat["files"] == files
    assert result.zones is not None and len(result.zones) == 1
    assert tree_snapshot(root) == before


def test_refill_timeout(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, _ = _oracle(tmp_path, sleep=10.0)
    result = oracle.refill(project_set(root))
    assert result.outcome == "timeout" and result.zones is None and result.returncode is None


def test_refill_missing_saved_board(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path)
    result = oracle.refill(project_set(authored_project(tmp_path, major=10)))
    assert result.zones is None and "no board" in result.message


def test_refill_unreadable_saved_board(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path, refill_board="not a board")
    result = oracle.refill(project_set(authored_project(tmp_path, major=10)))
    assert result.zones is None and "unreadable" in result.message


def test_refill_unsupported_makes_no_drc_run(tmp_path: Path) -> None:
    oracle, script = _oracle(tmp_path, version="9.0.9")
    result = oracle.refill(project_set(authored_project(tmp_path, major=9)))
    assert not result.supported and result.zones is None and _drc_calls(script) == []


def test_kicad_oracle_satisfies_the_protocol(tmp_path: Path) -> None:
    oracle: Oracle = KicadOracle(KicadCli(tmp_path / "kicad-cli"))
    assert oracle.name == "kicad"


def test_staging_outside_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_TWO_RUN", frozenset())  # one run: the canary run gives the report
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path, writes=("x.kicad_prl",))
    before = tree_snapshot(root)
    user_rules = (root / f"{STEM}.kicad_dru").read_bytes().decode("utf-8")
    outcome = oracle.drc(project_set(root))
    (call,) = _drc_calls(script)
    files: dict[str, str] = call["files"]  # type: ignore[assignment]
    assert files[f"{STEM}.kicad_dru"].startswith(user_rules)
    assert CANARY_RULE_NAME in files[f"{STEM}.kicad_dru"]
    assert all(u in files[f"{STEM}.kicad_pcb"] for u in CANARY_UUIDS)  # the staged board, not the original
    assert "--exit-code-violations" not in call["args"]  # type: ignore[operator]
    assert tree_snapshot(root) == before
    assert outcome.tool_writes == ("x.kicad_prl",)
    assert outcome.canary == "fired" and outcome.canary_reason == ""
    assert outcome.canary_removed == 1
    assert outcome.report is not None and outcome.report.violations == ()


def test_absent_when_the_report_lacks_the_pair(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    user = {"type": "clearance", "description": "user", "severity": "error",
            "items": [{"uuid": "u1", "description": "t", "pos": {"x": 1, "y": 2}}]}  # fmt: skip
    oracle, _ = _oracle(tmp_path, drc_report=report_with(user))
    outcome = oracle.drc(project_set(root))
    assert outcome.canary == "absent"
    assert outcome.report is not None and len(outcome.report.violations) == 1


def _clearances(count: int) -> str:
    return report_with(*(
        {"type": "clearance", "description": "user", "severity": "error",
         "items": [{"uuid": f"u{n}", "description": "t", "pos": {"x": n, "y": 2}}]}
        for n in range(count)
    ))  # fmt: skip


@pytest.mark.parametrize(
    ("count", "state", "reason"),
    [(canary.CLEARANCE_REPORT_LIMIT, "inconclusive", "clearance-limit"),
     (canary.CLEARANCE_REPORT_LIMIT - 1, "absent", "")],
)  # fmt: skip
def test_saturated_report_gives_no_verdict(tmp_path: Path, count: int, state: str, reason: str) -> None:
    """KiCad stops reporting clearance violations near 499, so a canary missing from such a report proves
    nothing (H-K-DRC-LIMIT); one violation below, its absence is the verdict. The run is not repeated."""
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path, drc_report=_clearances(count))
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == (state, reason)
    assert outcome.report is not None and len(outcome.report.violations) == count
    assert len(_drc_calls(script)) == 2  # the plain run and the canary run


def test_saturated_report_on_the_one_run_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_TWO_RUN", frozenset())
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path, drc_report=_clearances(canary.CLEARANCE_REPORT_LIMIT))
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "clearance-limit")
    assert len(_drc_calls(script)) == 1


def test_unproven_major(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_SUPPORT", frozenset())
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "placement-unproven")
    (call,) = _drc_calls(script)
    files: dict[str, str] = call["files"]  # type: ignore[assignment]
    assert files[f"{STEM}.kicad_pcb"] == (root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8")
    assert files[f"{STEM}.kicad_dru"] == (root / f"{STEM}.kicad_dru").read_text(encoding="utf-8")


def test_selector_unproven(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "SELECTOR_SUPPORT", {"net": frozenset({9})})
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "selector-unproven")


def test_names_already_taken(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    board.write_text(
        board.read_text(encoding="utf-8").replace('"LED_A"', '"FENOLITE_CANARY_A"'), encoding="utf-8"
    )
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "names-taken")
    assert outcome.report is not None


def test_clearance_ignored(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    path = root / f"{STEM}.kicad_pro"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["board"]["design_settings"].setdefault("rule_severities", {})["clearance"] = "ignore"
    path.write_text(json.dumps(data), encoding="utf-8")
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "clearance-ignored")


def test_not_applicable_without_rules(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(native_project(tmp_path, rules=None)))
    assert outcome.canary == "not-applicable" and outcome.report is not None


def test_board_unparsed(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    board = root / f"{STEM}.kicad_pcb"
    board.write_bytes(board.read_bytes() + b" trailing")
    oracle, _ = _oracle(tmp_path)
    assert oracle.drc(project_set(root)).canary_reason == "board-unparsed"


def test_missing_report(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path, drc_report="")
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.report is None
    assert (outcome.canary, outcome.canary_reason) == ("inconclusive", "no-report")
    assert outcome.returncode == 3 and outcome.message == "Failed to load board"
    assert outcome.evidence.level == Level.UNVERIFIED


@posix_tools  # a timeout kills the .cmd launcher of the fake, not its Python child
def test_timeout(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path, sleep=10.0)
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.outcome == "timeout" and outcome.returncode is None and outcome.report is None
    assert outcome.canary_reason == "no-report"


def test_two_run_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(canary, "CANARY_TWO_RUN", frozenset({10}))
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path)
    outcome = oracle.drc(project_set(root))
    plain, staged = _drc_calls(script)
    assert not any(u in plain["files"][f"{STEM}.kicad_pcb"] for u in CANARY_UUIDS)  # type: ignore[index]
    assert all(u in staged["files"][f"{STEM}.kicad_pcb"] for u in CANARY_UUIDS)  # type: ignore[index]
    assert outcome.canary == "fired" and outcome.canary_removed == 0


def test_evidence_never_above_its_parts(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.drc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    for part in (drcmod.EVIDENCE, oraclemod.EVIDENCE):
        assert strength(outcome.evidence.level) <= strength(part.level)
    assert set(outcome.evidence.hypotheses) >= {"H-K-DRC-JSON", "H-K-CHECK-COPYSET", "H-K-CHECK-CANARY-3"}


# -- netlist (c0020)


def _board(root: Path):  # type: ignore[no-untyped-def]
    return read_board((root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8"), file=f"{STEM}.kicad_pcb")


def test_netlist_pairs_every_pad(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    design = _board(root)
    oracle, script = _oracle(tmp_path, ipcd356=_ipc.text(_ipc.records(design)))
    before = tree_snapshot(root)
    outcome = oracle.netlist(project_set(root), board=design)
    assert outcome.netlist is not None and outcome.netlist.source == "export"
    assert outcome.netlist.uncovered == () and len(outcome.netlist.assignments) == len(_ipc.records(design))
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    assert outcome.evidence.level == oraclemod.padnets.EVIDENCE.level
    assert set(outcome.evidence.hypotheses) >= {"H-K-NET-IPC", "H-K-CHECK-COPYSET"}
    (call,) = [c for c in calls(script) if c["args"][:3] == ["pcb", "export", "ipcd356"]]
    assert f"{STEM}.kicad_pro" in call["files"]  # the project files travel with the board
    assert tree_snapshot(root) == before


def test_netlist_export_failure(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, _ = _oracle(tmp_path)  # no ipcd356 text: exit 3 without an export
    outcome = oracle.netlist(project_set(root), board=_board(root))
    assert outcome.netlist is None and outcome.outcome == "exit" and outcome.returncode == 3
    assert outcome.message == "Failed to load board" and outcome.evidence.level == Level.UNVERIFIED


def test_netlist_timeout(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, _ = _oracle(tmp_path, sleep=10.0, ipcd356="P  UNITS CUST 0\n")
    outcome = oracle.netlist(project_set(root), board=_board(root))
    assert outcome.netlist is None and outcome.outcome == "timeout" and outcome.returncode is None


def test_netlist_unreadable_export(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, _ = _oracle(tmp_path, ipcd356="no units line\n")
    outcome = oracle.netlist(project_set(root), board=_board(root))
    assert outcome.netlist is None and outcome.message.startswith("unreadable IPC-D-356 export")


# -- RT2 (c0020)


def _runs(script: Path, *words: str) -> list[dict[str, object]]:
    return [c for c in calls(script) if tuple(c["args"][: len(words)]) == words]  # type: ignore[index]


def test_rt2_normalised_on_10(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path)
    outcome = oracle.rt2(project_set(root))
    assert len(_runs(script, "pcb", "upgrade", "--force")) == 2 and len(_drc_calls(script)) == 3
    assert outcome.normalised is True and len(outcome.before) == 2 and outcome.after is not None
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    assert set(outcome.evidence.hypotheses) >= {"H-K-RT2-STABLE-2", "H-K-FMT-RESAVE", "H-K-DRC-JSON"}
    assert strength(outcome.evidence.level) <= strength(oraclemod.RT2_EVIDENCE.level)
    assert all("--exit-code-violations" not in c["args"] for c in _drc_calls(script))  # type: ignore[operator]


def test_rt2_repeats_both_sides_when_the_redump_differs(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=9)
    item = {"uuid": "u1", "description": "t", "pos": {"x": 1, "y": 2}}
    extra = {"type": "clearance", "description": "extra", "severity": "error", "items": [item]}
    same, other = report_with(), report_with(extra)
    oracle, script = _oracle(tmp_path, version="9.0.9", drc_sequence=(same, same, other, same))
    outcome = oracle.rt2(project_set(root))
    # two original runs, the re-dump run that differs, then three more runs of each side
    assert len(_drc_calls(script)) == 3 + 2 * oraclemod.RT2_REPEATS
    assert len(outcome.before) == 2 + oraclemod.RT2_REPEATS and len(outcome.repeats) == oraclemod.RT2_REPEATS
    assert outcome.after is not None and len(outcome.after.violations) == 1
    equal, _ = _oracle(tmp_path / "equal", version="9.0.9")
    assert equal.rt2(project_set(root)).repeats == ()


def test_drc_entries_leave_out_uuids_and_order() -> None:
    def violation(uid: str, x: int) -> dict[str, object]:
        item = {"uuid": uid, "description": "t", "pos": {"x": x, "y": 0}}
        return {"type": "clearance", "description": "d", "severity": "error", "items": [item]}

    first = drcmod.read_drc_report(report_with(violation("a", 1), violation("b", 2)))
    second = drcmod.read_drc_report(report_with(violation("c", 2), violation("d", 1)))
    assert first.entries() == second.entries() and len(first.entries()) == 2
    assert first.entries() != drcmod.read_drc_report(report_with(violation("a", 1))).entries()


def test_rt2_no_normaliser_on_9(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=9)
    oracle, script = _oracle(tmp_path, version="9.0.9")
    outcome = oracle.rt2(project_set(root))
    assert _runs(script, "pcb", "upgrade") == [] and len(_drc_calls(script)) == 3
    assert outcome.normalised is False and len(outcome.before) == 2 and outcome.after is not None
    assert "H-K-FMT-RESAVE" not in outcome.evidence.hypotheses


def test_rt2_normalisation_turned_off(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    script = fake_kicad_cli(tmp_path / "bin")
    outcome = KicadOracle(KicadCli(script, timeout=60.0), rt2_normalise=False).rt2(project_set(root))
    assert _runs(script, "pcb", "upgrade") == [] and outcome.normalised is False
    assert len(outcome.before) == 2 and outcome.after is not None


def test_rt2_no_canary_and_no_writes(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    log = tmp_path / "log"
    log.mkdir()
    oracle, _ = _oracle(tmp_path, log=log, writes=("x.kicad_prl",), rewrite_input=True)
    before = tree_snapshot(root)
    outcome = oracle.rt2(project_set(root))
    assert outcome.after is not None
    boards = sorted(log.glob("*.kicad_pcb"))
    rules = sorted(log.glob("*.kicad_dru"))
    assert len(boards) == 5 and rules
    assert not any("FENOLITE_CANARY_A" in b.read_text(encoding="utf-8") for b in boards)
    user = (root / f"{STEM}.kicad_dru").read_text(encoding="utf-8")
    assert all(r.read_text(encoding="utf-8") == user for r in rules)
    assert tree_snapshot(root) == before


@posix_tools  # a timeout kills the .cmd launcher of the fake, not its Python child
def test_rt2_failures_give_what_was_obtained(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, _ = _oracle(tmp_path, upgrade="fail")
    failed = oracle.rt2(project_set(root))
    assert failed.before == () and failed.after is None and failed.message.startswith("pcb upgrade failed")
    assert failed.evidence.level == Level.UNVERIFIED
    no_report, _ = _oracle(tmp_path / "b", drc_report="")
    missing = no_report.rt2(project_set(root))
    assert missing.before == () and missing.after is None and missing.message == "Failed to load board"
    slow, _ = _oracle(tmp_path / "c", sleep=10.0, version="9.0.9")
    timed_out = slow.rt2(project_set(root))
    assert timed_out.outcome == "timeout" and timed_out.returncode is None and timed_out.after is None


def test_rt2_unreadable_board(tmp_path: Path) -> None:
    root = native_project(tmp_path)
    (root / f"{STEM}.kicad_pcb").write_text("(kicad_pcb (version 20241229)) trailing", encoding="utf-8")
    oracle, script = _oracle(tmp_path)
    outcome = oracle.rt2(project_set(root))
    assert outcome.before == () and outcome.message.startswith("board not read") and _drc_calls(script) == []


def test_kicad_oracle_satisfies_the_three_protocols(tmp_path: Path) -> None:
    oracle = KicadOracle(KicadCli(tmp_path / "kicad-cli"))
    assert isinstance(oracle, NetlistOracle) and isinstance(oracle, RoundTripOracle)
    drc_only, netlist, rt2, erc = oraclemod._protocols(oracle)  # pyright: ignore[reportPrivateUsage]
    assert drc_only is netlist is rt2 is erc is oracle


def test_plot_outcome_holds_no_bytes(tmp_path: Path) -> None:
    """``KicadOracle.plot`` (c0024): name, size and hash per view, nothing written under the project."""
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path, writes=("x.kicad_prl",))
    assert isinstance(oracle, Plotter)
    before = tree_snapshot(root)
    outcome = oracle.plot(project_set(root))
    assert [v.name for v in outcome.views] == ["back.svg", "bottom.png", "front.svg", "top.png"]
    assert all(isinstance(v.bytes, int) and v.bytes > 0 and len(v.sha256) == 64 for v in outcome.views)
    assert outcome.failed == () and outcome.message == "" and outcome.tool_version == "10.0.6"
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    assert outcome.evidence.hypotheses == ("H-K-EXPORT-RENDER",)
    assert str(tmp_path) not in repr(outcome) and "fenolite-kicad-" not in repr(outcome)
    assert tree_snapshot(root) == before
    copied = [
        set(c["files"]) for c in calls(script) if c["args"][:2] in (["pcb", "export"], ["pcb", "render"])
    ]
    assert len(copied) == 4 and all(f"{STEM}.kicad_pro" in files for files in copied)


def test_plot_names_the_views_that_failed(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, _ = _oracle(tmp_path, export_fail=("render",))
    outcome = oracle.plot(project_set(root))
    assert [v.name for v in outcome.views] == ["back.svg", "front.svg"]
    assert outcome.failed == ("bottom.png", "top.png")
    assert "bottom.png: exit 1" in outcome.message and "<tmp>" not in outcome.message
    none, _ = _oracle(tmp_path / "second", export_fail=("render", "svg"))
    empty = none.plot(project_set(root))
    assert empty.views == () and len(empty.failed) == 4
    assert strength(empty.evidence.level) == strength(Level.UNVERIFIED)


# -- the schematic's netlist (c0063)

NETLISTS = Path(__file__).resolve().parents[3] / "data" / "kicad" / "netlist"
SHEETS = Path(__file__).resolve().parents[3] / "data" / "kicad" / "schematic"


def _with_schematic(tmp_path: Path, text: str = "(kicad_sch)\n") -> Path:
    root = authored_project(tmp_path, major=10)
    (root / f"{STEM}.kicad_sch").write_text(text, encoding="utf-8", newline="\n")
    return root


def _export(major: int = 10) -> str:
    return (NETLISTS / f"export_{major}.net").read_text(encoding="utf-8")


def test_schematic_netlist_elements(tmp_path: Path) -> None:
    root = _with_schematic(tmp_path)
    oracle, script = _oracle(tmp_path, netlist=_export())
    before = tree_snapshot(root)
    outcome = oracle.schematic_netlist(project_set(root))
    listed = outcome.netlist
    assert listed is not None and listed.source == "schematic" and listed.uncovered == ()
    assert PadAssignment("U1-10", "GND") in listed.assignments
    assert PadAssignment("U1-2", "unconnected-(U1-PA1-Pad2)") in listed.assignments
    assert len(listed.assignments) == 8
    dumped = repr(outcome)
    for part in ("2026-01-01", "/authored", "KIPRJMOD", str(tmp_path)):
        assert part not in dumped, part
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    assert outcome.evidence.level == oraclemod.netlistmod.EVIDENCE.level
    assert set(outcome.evidence.hypotheses) >= {"H-K-NETLIST-SHAPE", "H-K-CHECK-COPYSET"}
    (call,) = [c for c in calls(script) if c["args"][:3] == ["sch", "export", "netlist"]]
    assert call["args"][-1] == f"{STEM}.kicad_sch" and "kicadsexpr" in call["args"]
    assert f"{STEM}.kicad_pro" in call["files"]  # the project files travel with the schematic
    assert tree_snapshot(root) == before


def test_schematic_netlist_of_both_shapes_is_equal(tmp_path: Path) -> None:
    root = _with_schematic(tmp_path)
    nine, _ = _oracle(tmp_path / "nine", netlist=_export(9), version="9.0.9")
    ten, _ = _oracle(tmp_path / "ten", netlist=_export(10))
    first, second = nine.schematic_netlist(project_set(root)), ten.schematic_netlist(project_set(root))
    assert first.netlist is not None and first.netlist == second.netlist


def test_schematic_netlist_unloadable(tmp_path: Path) -> None:
    root = _with_schematic(tmp_path)
    oracle, _ = _oracle(tmp_path)  # no netlist text: "Failed to load schematic", exit 3
    outcome = oracle.schematic_netlist(project_set(root))
    assert outcome.netlist is None and outcome.outcome == "exit" and outcome.returncode == 3
    assert outcome.message == "Failed to load schematic" and outcome.evidence.level == Level.UNVERIFIED


def test_schematic_netlist_unreadable_export(tmp_path: Path) -> None:
    root = _with_schematic(tmp_path)
    oracle, _ = _oracle(tmp_path, netlist="(kicad_sch (version 20260306))")
    outcome = oracle.schematic_netlist(project_set(root))
    assert outcome.netlist is None and outcome.message.startswith("unreadable netlist export")
    assert "kicad_sch" in outcome.message and outcome.evidence.level == Level.UNVERIFIED


@posix_tools  # a timeout kills the .cmd launcher of the fake, not its Python child
def test_schematic_netlist_timeout(tmp_path: Path) -> None:
    root = _with_schematic(tmp_path)
    oracle, _ = _oracle(tmp_path, sleep=10.0, netlist=_export())
    outcome = oracle.schematic_netlist(project_set(root))
    assert outcome.netlist is None and outcome.outcome == "timeout" and outcome.returncode is None


def test_schematic_netlist_without_a_schematic(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    oracle, script = _oracle(tmp_path, netlist=_export())
    outcome = oracle.schematic_netlist(project_set(root))
    assert outcome.netlist is None and "no schematic" in outcome.message
    assert not [c for c in calls(script) if c["args"][:2] == ["sch", "export"]]


def test_schematic_files_are_the_copy_set(tmp_path: Path) -> None:
    root = authored_project(tmp_path, major=10)
    project = project_set(root)
    assert oraclemod.schematic_files(project) == {}
    (root / f"{STEM}.kicad_sch").write_bytes((SHEETS / "hier" / "top.kicad_sch").read_bytes())
    (root / "child.kicad_sch").write_bytes((SHEETS / "hier" / "child.kicad_sch").read_bytes())
    project = project_set(root)
    files = oraclemod.schematic_files(project)
    assert files == dict(project.files)  # the copy set holds the schematic and its sheets (c0062)
    assert files[f"{STEM}.kicad_sch"] == root / f"{STEM}.kicad_sch" and "child.kicad_sch" in files
    (root / f"{STEM}.kicad_sch").write_text("not a schematic", encoding="utf-8")
    assert f"{STEM}.kicad_sch" in oraclemod.schematic_files(project_set(root))


def test_kicad_oracle_satisfies_the_schematic_netlist_protocol(tmp_path: Path) -> None:
    oracle = KicadOracle(KicadCli(tmp_path / "kicad-cli"))
    assert isinstance(oracle, SchematicNetlistOracle)
    assert oraclemod._schematic_protocol(oracle) is oracle  # pyright: ignore[reportPrivateUsage]


# -- ERC (kicad-oracle, "ERC oracle"; change c0062)


def _sheet(root: Path, name: str):  # type: ignore[no-untyped-def]
    return parse_tree((root / name).read_text(encoding="utf-8"))


def _uuid(node) -> str:  # type: ignore[no-untyped-def]
    return node.find("uuid").atoms()[0].value


def _symbol(tree, ref: str):  # type: ignore[no-untyped-def]
    for symbol in tree.nodes("symbol"):
        if any([a.value for a in p.atoms()[:2]] == ["Reference", ref] for p in symbol.nodes("property")):
            return symbol
    raise KeyError(ref)


def _erc_calls(script: Path) -> list[dict[str, object]]:
    return [c for c in calls(script) if c["args"][:2] == ["sch", "erc"]]  # type: ignore[index]


def _on_root(root_uuid: str, *violations: dict[str, object]) -> str:
    sheet = {"path": "/", "uuid_path": f"/{root_uuid}", "violations": list(violations)}
    return json.dumps({"source": "blink.kicad_sch", "date": "d", "kicad_version": "10.0.6",
                       "coordinate_units": "mm", "sheets": [sheet]})  # fmt: skip


def test_erc_where_names_the_pin(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    tree = _sheet(root, "blink.kicad_sch")
    u1 = _symbol(tree, "U1")
    pin = next(p for p in u1.nodes("pin") if p.atoms()[0].value == "2")
    label = next(c for c in tree.nodes("global_label"))
    report = _on_root(
        _uuid(tree),
        erc_entry("pin_not_connected", _uuid(pin).upper(), x=1.397, y=0.5969),
        erc_entry("lib_symbol_issues", _uuid(u1), severity="warning"),
        erc_entry("isolated_pin_label", _uuid(label), severity="warning"),
        erc_entry("endpoint_off_grid", "99999999-0000-4000-8000-000000000000", severity="warning"),
    )
    oracle, script = _oracle(tmp_path, erc_report=report)
    outcome = oracle.erc(project_set(root))
    assert outcome.report is not None and outcome.outcome == "exit" and outcome.returncode == 0
    pin_item, symbol_item, label_item, unknown = (v.items[0] for v in outcome.report.violations)
    assert pin_item.where == "U1-2" and pin_item.position.x == 139_700_000
    assert symbol_item.where == "U1" and label_item.where == label.atoms()[0].value
    assert unknown.where == ""
    (call,) = _erc_calls(script)
    assert call["args"][-1] == "blink.kicad_sch" and "--exit-code-violations" not in call["args"]  # type: ignore[index, operator]
    assert not _drc_calls(script)  # no canary and no DRC run


def test_erc_where_two_uses_of_one_sheet(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "multi", folder="multi")
    top, cell = _sheet(root, "top.kicad_sch"), _sheet(root, "cell.kicad_sch")
    symbol = next(s for s in cell.nodes("symbol") if s.find("instances") is not None)
    uses = [f"/{_uuid(top)}/{_uuid(sheet)}" for sheet in top.nodes("sheet")]
    assert len(uses) == 2
    sheets = [
        {"path": f"/Cell{i}/", "uuid_path": use, "violations": [erc_entry("pin_not_driven", _uuid(symbol))]}
        for i, use in enumerate(uses)
    ]
    # A third entry lists the same symbol under the root, as KiCad does for the checks of a sheet file.
    report = erc_report_with(erc_entry("lib_symbol_issues", _uuid(symbol), severity="warning"), sheets=sheets)
    oracle, _ = _oracle(tmp_path, erc_report=report)
    outcome = oracle.erc(project_set(root))
    assert outcome.report is not None
    under_root, first, second = (v.items[0].where for v in outcome.report.violations)
    assert first and second and first != second
    assert under_root == ""  # two references for one uuid: no location is guessed
    assert [v.sheet for v in outcome.report.violations] == ["/", "/Cell0/", "/Cell1/"]


def test_erc_no_writes_in_the_project(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    oracle, script = _oracle(tmp_path, writes=("blink.kicad_prl",))
    before = tree_snapshot(root)
    outcome = oracle.erc(project_set(root))
    assert outcome.tool_writes == ("blink.kicad_prl",)
    assert tree_snapshot(root) == before
    (call,) = _erc_calls(script)
    assert set(call["sheets"]) == {"blink.kicad_sch"}  # type: ignore[call-overload]


def test_erc_copy_set_reaches_the_tool(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "hier")
    (root / "other.kicad_sch").write_bytes((root / "child.kicad_sch").read_bytes())
    oracle, script = _oracle(tmp_path)
    assert oracle.erc(project_set(root)).report is not None
    (call,) = _erc_calls(script)
    assert set(call["sheets"]) == {"top.kicad_sch", "child.kicad_sch"}  # type: ignore[call-overload]


def test_erc_missing_report(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    oracle, _ = _oracle(tmp_path, erc_report="")
    outcome = oracle.erc(project_set(root))
    assert outcome.report is None and outcome.returncode == 3
    assert outcome.message == "Failed to load schematic"
    assert outcome.evidence.level == Level.UNVERIFIED


def test_erc_unreadable_report_is_no_report(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    oracle, _ = _oracle(tmp_path, erc_report='{"source": "x"}')
    outcome = oracle.erc(project_set(root))
    assert outcome.report is None and outcome.message.startswith("unreadable ERC report")


@posix_tools  # a timeout kills the .cmd launcher of the fake, not its Python child
def test_erc_timeout(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    oracle, _ = _oracle(tmp_path, sleep=10.0)
    outcome = oracle.erc(project_set(root))
    assert outcome.outcome == "timeout" and outcome.returncode is None and outcome.report is None


def test_erc_without_a_schematic_runs_nothing(tmp_path: Path) -> None:
    oracle, script = _oracle(tmp_path)
    outcome = oracle.erc(project_set(authored_project(tmp_path, major=10)))
    assert outcome.report is None and "no schematic" in outcome.message
    assert _erc_calls(script) == [] and outcome.evidence.level == Level.UNVERIFIED


def test_erc_where_survives_a_sheet_that_does_not_parse(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "hier")
    top = _sheet(root, "top.kicad_sch")
    child = _sheet(root, "child.kicad_sch")
    in_child = next(s for s in child.nodes("symbol") if s.find("instances") is not None)
    in_top = next(s for s in top.nodes("symbol") if s.find("instances") is not None)
    report = _on_root(_uuid(top), erc_entry("a", _uuid(in_top)), erc_entry("b", _uuid(in_child)))
    project = project_set(root)
    (root / "child.kicad_sch").write_text("(kicad_sch (version 20250114)", encoding="utf-8")
    oracle, _ = _oracle(tmp_path, erc_report=report)
    outcome = oracle.erc(project)
    assert outcome.report is not None
    known, unknown = (v.items[0].where for v in outcome.report.violations)
    assert known and unknown == ""


def test_erc_evidence_never_above_its_parts(tmp_path: Path) -> None:
    oracle, _ = _oracle(tmp_path)
    outcome = oracle.erc(project_set(built_blink_project(tmp_path / "blink")))
    assert outcome.evidence.oracle == "kicad-cli 10.0.6"
    for part in (ercmod.EVIDENCE, oraclemod.EVIDENCE):
        assert strength(outcome.evidence.level) <= strength(part.level)
    assert set(outcome.evidence.hypotheses) >= {"H-K-ERC-JSON", "H-K-ERC-POS", "H-K-ERC-COPYSET"}
    assert outcome.evidence == dataclasses.replace(
        Evidence.combine(ercmod.EVIDENCE, oraclemod.EVIDENCE), oracle="kicad-cli 10.0.6"
    )


def test_first_line_drops_the_time_of_day() -> None:
    first = oraclemod._first_line  # pyright: ignore[reportPrivateUsage]
    assert first("\n10:50:25 PM: Error: Expecting kicad_sch\nmore") == "Error: Expecting kicad_sch"
    assert first("14:50:38: Error: Expecting 'kicad_sch'") == "Error: Expecting 'kicad_sch'"
    assert first("Failed to load board") == "Failed to load board" and first("  \n") == ""


# -- parity in the DRC run (kicad-oracle, "Parity in the DRC run"; change c0062)

PARITY_ENTRY = {
    "type": "net_conflict", "description": "Pad net (GND) doesn't match net given by schematic (LED_A).",
    "severity": "warning", "items": [{"uuid": "p1", "description": "Pad 2", "pos": {"x": 1, "y": 2}}],
}  # fmt: skip


def test_parity_flag_follows_the_schematic(tmp_path: Path) -> None:
    with_schematic = built_blink_project(tmp_path / "blink")
    oracle, script = _oracle(tmp_path / "a", parity=[PARITY_ENTRY])
    outcome = oracle.drc(project_set(with_schematic))
    runs = _drc_calls(script)
    assert len(runs) == (2 if oracle.major() in canary.CANARY_TWO_RUN else 1)
    assert all("--schematic-parity" in run["args"] for run in runs)  # type: ignore[operator]
    assert outcome.parity_judged is True and outcome.canary == "fired"
    assert outcome.report is not None and [v.type for v in outcome.report.schematic_parity] == [
        "net_conflict"
    ]
    assert all(set(run["sheets"]) == {"blink.kicad_sch"} for run in runs)  # type: ignore[call-overload]

    without, other = _oracle(tmp_path / "b", parity=[PARITY_ENTRY])
    plain = without.drc(project_set(authored_project(tmp_path, major=10)))
    assert _drc_calls(other) and not any("--schematic-parity" in run["args"] for run in _drc_calls(other))  # type: ignore[operator]
    assert plain.parity_judged is False and plain.report is not None and plain.report.schematic_parity == ()


def test_parity_unloadable_schematic_keeps_the_copper_verdict(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    line = "10:50:25 PM: Error: Expecting kicad_sch in '<tmp>/blink.kicad_sch', line 2, offset 1."
    oracle, script = _oracle(tmp_path, parity_fail=line)
    outcome = oracle.drc(project_set(root))
    flags = ["--schematic-parity" in run["args"] for run in _drc_calls(script)]  # type: ignore[operator]
    assert flags[0] is True and flags[-1] is False and False in flags
    assert outcome.report is not None and outcome.parity_judged is False
    assert outcome.canary == "fired"  # the verdict of the runs without the flag
    assert outcome.message == "Error: Expecting kicad_sch in '<tmp>/blink.kicad_sch', line 2, offset 1."
    assert strength(outcome.evidence.level) == strength(
        Evidence.combine(drcmod.EVIDENCE, oraclemod.EVIDENCE).level
    )


def test_parity_not_judged_when_the_tool_says_so(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    note = "Failed to fetch schematic netlist for parity tests."
    oracle, script = _oracle(tmp_path, parity_note=note)
    outcome = oracle.drc(project_set(root))
    assert all("--schematic-parity" in run["args"] for run in _drc_calls(script))  # type: ignore[operator]
    assert outcome.report is not None and outcome.parity_judged is False and outcome.message == note


def test_parity_no_report_at_all(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    oracle, _ = _oracle(tmp_path, drc_report="")
    outcome = oracle.drc(project_set(root))
    assert outcome.report is None and outcome.parity_judged is False
    assert outcome.message == "Failed to load board" and outcome.canary_reason == "no-report"


def test_rt2_of_the_board_asks_for_no_parity(tmp_path: Path) -> None:
    root = built_blink_project(tmp_path / "blink")
    oracle, script = _oracle(tmp_path)
    assert oracle.rt2(project_set(root)).after is not None
    assert not any("--schematic-parity" in run["args"] for run in _drc_calls(script))  # type: ignore[operator]


# -- RT2 for schematics (kicad-oracle, "Schematic RT2 over the corpus"; change c0062)


def test_rt2_erc_three_runs_and_no_write(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "hier")
    oracle, script = _oracle(tmp_path, writes=("top.kicad_prl",))
    before = tree_snapshot(root)
    outcome = oracle.rt2_erc(project_set(root))
    assert tree_snapshot(root) == before
    runs = _erc_calls(script)
    assert len(runs) == 3 and not _drc_calls(script)
    assert len(outcome.before) == 2 and outcome.after is not None
    assert (outcome.redumped, outcome.kept) == (2, 0)
    for name in ("top.kicad_sch", "child.kicad_sch"):
        original = (root / name).read_text(encoding="utf-8")
        redump = dumps(rebuild_schematic(read_schematic(original, file=name)))
        assert runs[0]["sheets"][name] == original and runs[1]["sheets"][name] == original  # type: ignore[index]
        assert runs[2]["sheets"][name] == redump  # type: ignore[index]
    assert outcome.evidence == dataclasses.replace(
        Evidence.combine(ercmod.EVIDENCE, schmod.EVIDENCE, oraclemod.EVIDENCE), oracle="kicad-cli 10.0.6"
    )


def test_rt2_erc_keeps_a_sheet_it_cannot_read(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "hier")
    project = project_set(root)
    broken = "(kicad_sch (version 20250114)"
    (root / "child.kicad_sch").write_text(broken, encoding="utf-8")
    oracle, script = _oracle(tmp_path)
    outcome = oracle.rt2_erc(project)
    assert (outcome.redumped, outcome.kept) == (1, 1) and outcome.after is not None
    assert _erc_calls(script)[2]["sheets"]["child.kicad_sch"] == broken  # type: ignore[index]


def test_rt2_erc_failures_give_what_was_obtained(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "hier")
    none, _ = _oracle(tmp_path / "a", erc_report="")
    missing = none.rt2_erc(project_set(root))
    assert missing.before == () and missing.after is None and missing.message == "Failed to load schematic"
    assert missing.evidence.level == Level.UNVERIFIED and missing.returncode == 3
    good = erc_report_with()
    last, script = _oracle(tmp_path / "b", erc_sequence=(good, good, ""))
    third = last.rt2_erc(project_set(root))
    assert len(third.before) == 2 and third.after is None and third.evidence.level == Level.UNVERIFIED
    assert (third.redumped, third.kept) == (2, 0) and len(_erc_calls(script)) == 3
    no_sheet, other = _oracle(tmp_path / "c")
    absent = no_sheet.rt2_erc(project_set(authored_project(tmp_path, major=10)))
    assert absent.before == () and "no schematic" in absent.message and _erc_calls(other) == []


def test_kicad_oracle_satisfies_the_erc_protocol(tmp_path: Path) -> None:
    oracle = KicadOracle(KicadCli(tmp_path / "kicad-cli"))
    assert isinstance(oracle, ErcOracle)
    assert oraclemod._protocols(oracle)[3] is oracle  # pyright: ignore[reportPrivateUsage]
