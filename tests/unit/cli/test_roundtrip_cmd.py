# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite roundtrip`` (capability cli-contract, "Roundtrip command"; change c0066). Hermetic: RT2 runs
against the fake ``kicad-cli``."""

from __future__ import annotations

from pathlib import Path

import _ipc
import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot

from fenolite.backends import registry
from fenolite.backends.base import ReadResult, RoundTrip, Validation
from fenolite.backends.kicad.pcb import EVIDENCE, opaque_count, read_board
from fenolite.core.errors import Issue

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
SYMBOLS = DATA / "libs" / "Mini.kicad_sym"
SHEET = DATA / "kicad" / "sheets" / "all_items.kicad_wks"
PROJECT = DATA / "kicad" / "project" / "empty_10.kicad_pro"


def test_authored_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER))
    result = env["result"]
    assert code == 0 and env["ok"] is True and env["issues"] == []
    assert result["kind"] == "kicad_pcb" and result["level"] == "rt1"
    assert result["rt0"] == {"passed": True, "difference": ""}
    assert result["rt1"] == {
        "passed": True,
        "difference": "",
        "opaque_count": opaque_count(read_board(TWO_LAYER)),
    }
    assert "rt2" not in result
    assert env["input"]["path"] == "two_layer.kicad_pcb" and env["evidence"]["hypotheses"] == ["H-K-PCB-READ"]


def test_level_rt0_runs_no_rebuild(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER), "--level", "rt0")
    assert code == 0 and env["result"] == {
        "kind": "kicad_pcb",
        "level": "rt0",
        "rt0": {"passed": True, "difference": ""},
    }
    assert env["evidence"]["hypotheses"] == ["H-K-SEXPR-STRICT"]


@pytest.mark.parametrize(("path", "kind"), [(SYMBOLS, "kicad_sym"), (SHEET, "kicad_wks")])
def test_kind_without_a_rebuild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: Path, kind: str
) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(path))
    assert code == 0
    assert (env["result"]["kind"], env["result"]["level"], env["result"]["rt1"]) == (
        kind,
        "rt0",
        "not-applicable",
    )


class _Failing:
    name = "kicad"

    def validate(self, path: Path, *, issues: list[Issue] | None = None) -> Validation:
        verdict = RoundTrip("RT1", False, False, True, True, 3, "/kicad_pcb/footprint[0]/pad[1]")
        return Validation(ReadResult(read_board(path), (), EVIDENCE), verdict)


def test_failed_level_is_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(registry, "for_path", lambda path: _Failing())
    code, env, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER))
    assert code == 5 and err["code"] == "FEN-5001" and env["ok"] is False
    assert env["result"]["level"] == "rt0" and env["result"]["rt1"]["passed"] is False
    failed = [i for i in env["issues"] if i["code"] == "roundtrip.failed"]
    assert len(failed) == 1 and failed[0]["severity"] == "error"
    assert failed[0]["where"] == "/kicad_pcb/footprint[0]/pad[1]"


def test_refused_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(tmp_path / "missing.kicad_pcb"))
    assert code == 3 and err["code"] == "FEN-3001"
    notes = tmp_path / "notes.txt"
    notes.write_text("x\n", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(notes))
    assert code == 2 and err["code"] == "FEN-2001"
    unbalanced = DATA / "kicad" / "sexpr" / "mirror" / "unbalanced.kicad_pcb"
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(unbalanced))
    assert code == 3 and err["code"] == "FEN-3004"
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(PROJECT))
    assert code == 3 and err["code"] == "FEN-3001"  # a project file without its board


def test_rt2_needs_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER), "--level", "rt2")
    assert code == 6 and err["code"] == "FEN-6001" and "--level rt1" in err["hint"]
    code, _, err, _ = run(monkeypatch, tmp_path, "roundtrip", str(SYMBOLS), "--level", "rt2")
    assert code == 2 and err["code"] == "FEN-2001"


def test_rt2_through_the_fake_tool_is_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10, built=True)
    board = root / "board.kicad_pcb"
    fake = fake_kicad_cli(
        tmp_path / "bin",
        writes=("x.kicad_prl",),
        rewrite_input=True,
        refill_board=board.read_text(encoding="utf-8") + "\n",
        ipcd356=_ipc.for_board(board),
    )
    before = tree_snapshot(root)
    code, env, _, _ = run(
        monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
    )
    assert code == 0, env["issues"]
    rt2 = env["result"]["rt2"]
    assert env["result"]["level"] == "rt2" and rt2["passed"] is True and rt2["judged"] is True
    assert {"normalised", "runs", "before", "after", "unstable", "differences"} <= set(rt2)
    assert any(c["args"][:2] == ["pcb", "drc"] for c in calls(fake))
    assert tree_snapshot(root) == before and not (root / "x.kicad_prl").exists()


# --- schematics (task 2.3b, after the schematic reader of c0060) ------------------------------------

FLAT = DATA / "kicad" / "schematic" / "flat.kicad_sch"


def test_schematic_reaches_rt1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fenolite.backends.kicad import sch

    hide_kicad(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(FLAT))
    result = env["result"]
    assert code == 0 and (result["kind"], result["level"]) == ("kicad_sch", "rt1")
    assert result["rt1"] == {
        "passed": True,
        "difference": "",
        "opaque_count": sch.opaque_count(sch.read_schematic(FLAT)),
    }
    assert "H-K-SCH-READ" in env["evidence"]["hypotheses"]


def test_schematic_rt1_failure_is_an_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    failed = RoundTrip("RT1", False, False, True, True, 4, "/kicad_sch/symbol[0]")
    monkeypatch.setattr("fenolite.backends.kicad.sch.roundtrip_schematic", lambda text, file="": failed)
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(FLAT))
    assert code == 5 and env["result"]["level"] == "rt0"
    assert [(i["code"], i["where"]) for i in env["issues"]] == [("roundtrip.failed", "/kicad_sch/symbol[0]")]


# --- RT2 of a project's schematic through ERC (task 2.4b, after c0062) ------------------------------


def _blink_with_fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **erc: object) -> tuple[Path, Path]:
    from _projects import built_blink_project

    tmp_path.mkdir(parents=True, exist_ok=True)
    hide_kicad(monkeypatch, tmp_path)
    root = built_blink_project(tmp_path / "blink")
    fake = fake_kicad_cli(tmp_path / "bin", upgrade="copy", **erc)  # type: ignore[arg-type]
    return root, fake


def _erc_runs(fake: Path) -> int:
    return sum(1 for call in calls(fake) if call["args"][:2] == ["sch", "erc"])


def test_rt2_of_a_project_with_a_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, fake = _blink_with_fake(monkeypatch, tmp_path)
    before = tree_snapshot(root)
    code, env, _, _ = run(
        monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
    )
    assert code == 0, env["issues"]
    sheet = env["result"]["rt2"]["schematic"]
    assert env["result"]["level"] == "rt2" and env["result"]["rt2"]["passed"] is True
    assert (sheet["passed"], sheet["judged"], sheet["exact"], sheet["difference"]) == (True, True, True, "")
    assert (
        sheet["redumped"] >= 1
        and sheet["kept"] == 0
        and sheet["violations"] == sheet["violations_redump"] == 0
    )
    assert _erc_runs(fake) == 3 and tree_snapshot(root) == before


def test_rt2_schematic_difference_of_kinds_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from _fakecli import erc_entry, erc_report_with

    clean, more = erc_report_with(), erc_report_with(erc_entry("pin_not_connected", "u1"))
    root, fake = _blink_with_fake(monkeypatch, tmp_path, erc_sequence=(clean, clean, more))
    code, env, err, _ = run(
        monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
    )
    sheet = env["result"]["rt2"]["schematic"]
    assert code == 5 and err["code"] == "FEN-5001" and env["result"]["level"] == "rt1"
    assert (sheet["passed"], sheet["judged"], sheet["exact"]) == (False, True, False) and _erc_runs(fake) == 3
    failed = [i for i in env["issues"] if i["code"] == "roundtrip.failed"]
    assert (
        len(failed) == 1
        and "pin_not_connected" in failed[0]["where"]
        and "blink.kicad_sch" in failed[0]["message"]
    )


def test_rt2_schematic_is_not_judged_when_erc_does_not_repeat(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from _fakecli import erc_entry, erc_report_with

    clean, more = erc_report_with(), erc_report_with(erc_entry("pin_not_connected", "u1"))
    root, fake = _blink_with_fake(monkeypatch, tmp_path, erc_sequence=(clean, more, clean))
    code, env, _, _ = run(
        monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
    )
    sheet = env["result"]["rt2"]["schematic"]
    assert code == 0, env["issues"]
    assert env["result"]["level"] == "rt1" and (sheet["passed"], sheet["judged"]) == (False, False)
    assert not [i for i in env["issues"] if i["code"] == "roundtrip.failed"]


def test_rt2_schematic_holds_when_erc_names_another_item(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """KiCad names another pin of one violation in each run: the kinds agree, RT2 holds, ``exact`` is
    false."""
    from _fakecli import erc_entry, erc_report_with

    here = erc_report_with(erc_entry("power_pin_not_driven", "u1", severity="warning", x=1.0))
    there = erc_report_with(erc_entry("power_pin_not_driven", "u2", severity="warning", x=2.0))
    for name, sequence in (("first", (here, there, here)), ("second", (here, here, there))):
        root, fake = _blink_with_fake(monkeypatch, tmp_path / name, erc_sequence=sequence)
        code, env, _, _ = run(
            monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
        )
        sheet = env["result"]["rt2"]["schematic"]
        assert code == 0 and env["result"]["level"] == "rt2", env["issues"]
        assert (sheet["passed"], sheet["judged"], sheet["exact"]) == (True, True, False)
        assert "attempts" not in sheet and _erc_runs(fake) == 3


def test_rt2_schematic_without_an_erc_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, fake = _blink_with_fake(monkeypatch, tmp_path, erc_report="")
    code, env, _, _ = run(
        monkeypatch, root, "roundtrip", str(root), "--level", "rt2", "--kicad-cli", str(fake)
    )
    assert code == 5 and env["result"]["level"] == "rt1"
    assert [i["where"] for i in env["issues"] if i["code"] == "check.oracle-failed"] == ["blink.kicad_sch"]
    assert env["result"]["rt2"]["schematic"]["judged"] is False


# --- Altium input (change c0090, capability altium-verification, "Round-trip level RT-A3") ----------------

ALTIUM = DATA / "altium"


def test_roundtrip_altium_own_sample_holds_rta3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Own sample": RT-A3 of a committed project holds, the unwritten kinds are counted, and no
    file is written under the sample folder or the working directory."""
    hide_kicad(monkeypatch, tmp_path)
    before = tree_snapshot(ALTIUM / "board6")
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", str(ALTIUM / "board6"), "--level", "rta3")
    result = env["result"]
    assert code == 0 and env["ok"] is True
    assert (result["kind"], result["level"]) == ("altium", "rta3")
    assert result["rta3"]["holds"] is True and result["rta3"]["differences"] == 0
    assert result["rta3"]["presentation"] == "regenerated"
    # the board holds two texts and six graphics on a mechanical layer, which no record of the writer
    # carries, and the lines of its library footprints are records without a model entity
    assert result["unwritten"] == result["rta3"]["unwritten"]
    assert (result["unwritten"]["text"], result["unwritten"]["graphic"]) == (2, 6)
    assert result["unwritten"]["record:footprint-graphics"] == 33
    assert [i["code"] for i in env["issues"]] == ["check.rta3-unwritten"]
    assert env["evidence"]["level"] == "INFERRED" and "H-A-VER-RTA3" in env["evidence"]["hypotheses"]
    assert tree_snapshot(ALTIUM / "board6") == before
    assert not [p for p in tmp_path.rglob("*") if p.suffix.lower() in (".pcbdoc", ".schdoc", ".prjpcb")]


def test_roundtrip_altium_levels_by_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each Altium level is the stage of that name; without ``--level`` an Altium input is judged at RT-A1,
    and RT-A2 of a file that no build wrote is not judged."""
    document = str(ALTIUM / "routed" / "routed.PcbDoc")
    for level in ("rta0", "rta1"):
        code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", document, "--level", level)
        assert code == 0 and env["result"]["level"] == level and env["result"][level]["status"] == "ok"
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", document)
    assert code == 0 and env["result"]["level"] == "rta1" and env["input"]["kind"] == "altium_pcbdoc"
    code, env, _, _ = run(monkeypatch, tmp_path, "roundtrip", document, "--level", "rta2")
    assert code == 0 and env["result"]["level"] == "none"
    assert (env["result"]["rta2"]["status"], env["result"]["rta2"]["reason"]) == ("skipped", "native-input")


def test_roundtrip_altium_and_kicad_levels_do_not_mix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    document = str(ALTIUM / "routed" / "routed.PcbDoc")
    code, _, error, _ = run(monkeypatch, tmp_path, "roundtrip", document, "--level", "rt1")
    assert code == 2 and error["code"] == "FEN-2001" and "rta0, rta1, rta2, rta3" in error["hint"]
    code, _, error, _ = run(monkeypatch, tmp_path, "roundtrip", str(TWO_LAYER), "--level", "rta3")
    assert code == 2 and error["code"] == "FEN-2001" and "rt0, rt1, rt2" in error["hint"]
