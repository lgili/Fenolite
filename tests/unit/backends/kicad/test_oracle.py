# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``KicadOracle`` with a fake ``kicad-cli`` (capability kicad-oracle, "Check canary injection";
"Netlist oracle from IPC-D-356" and "RT2 oracle"; backend-protocol, "Oracle protocol" and "Netlist and
round-trip oracles"; changes c0013 and c0020). Hermetic: the fake reports the canary pair as KiCad would."""

from __future__ import annotations

import json
from pathlib import Path

import _ipc
import pytest
from _fakecli import calls, fake_kicad_cli, report_with
from _projects import STEM, authored_project, native_project, tree_snapshot

from fenolite.backends.base import NetlistOracle, Oracle, RoundTripOracle
from fenolite.backends.kicad import canary
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad.canary import CANARY_RULE_NAME, CANARY_UUIDS
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.core.evidence import Level, strength


def _oracle(tmp_path: Path, **fake: object) -> tuple[KicadOracle, Path]:
    script = fake_kicad_cli(tmp_path / "bin", **fake)  # type: ignore[arg-type]
    timeout = 3.0 if fake.get("sleep") else 60.0
    return KicadOracle(KicadCli(script, timeout=timeout)), script


def _drc_calls(script: Path) -> list[dict[str, object]]:
    return [c for c in calls(script) if c["args"][:2] == ["pcb", "drc"]]  # type: ignore[index]


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
    assert set(outcome.evidence.hypotheses) >= {"H-K-DRC-JSON", "H-K-CHECK-COPYSET", "H-K-CHECK-CANARY-2"}


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
    drc_only, netlist, rt2 = oraclemod._protocols(oracle)  # pyright: ignore[reportPrivateUsage]
    assert drc_only is netlist is rt2 is oracle
