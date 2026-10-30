# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite verify-source`` (capability fidelity-proof; change c0278). Hermetic: no tool runs, except the
fake-less refusal of ``--upgrade`` without ``kicad-cli``."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run, without_elapsed
from _projects import tree_snapshot

from fenolite.checks.equivalence import EQUIVALENCE_CODES
from fenolite.cli import cmd_verify_source
from fenolite.cli import explain as cli_explain
from fenolite.cli.cmd_verify_source import ISSUE_CODES

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data"
FIDELITY = DATA / "fidelity"
SCRIPT = FIDELITY / "sensor_code" / "design.py"
ORIGINAL = FIDELITY / "sensor"
LIBS = DATA / "libs"
VIA = 'design.via("gnd_tie", mm(20), mm(25)'
MOVED = 'design.via("gnd_tie", mm(20.1), mm(25)'
ACCEPT_VIA = {
    "id": "A001",
    "level": 5,
    "kind": "via-missing",
    "where": "GND:via:*",
    "reason": "an authored acceptance of the test",
    "attribution": "fenolite",
    "decided": "2026-10-29",
}
ACCEPT_PIXELS = {**ACCEPT_VIA, "id": "A002", "level": 8, "kind": "render-pixels", "where": "*"}


def variant(folder: Path, old: str = "", new: str = "", provenance: dict[str, Any] | None = None) -> Path:
    """A copy of the authored script under ``folder``, with ``old`` replaced by ``new``, beside library
    tables that name the authored mini library by its absolute path, and a provenance file when given."""
    folder.mkdir(parents=True, exist_ok=True)
    text = SCRIPT.read_text(encoding="utf-8")
    if old:
        assert old in text, old
        text = text.replace(old, new)
    script = folder / "design.py"
    script.write_text(text, encoding="utf-8")
    for table in ("fp-lib-table", "sym-lib-table"):
        source = (SCRIPT.parent / table).read_text(encoding="utf-8")
        (folder / table).write_text(source.replace("${KIPRJMOD}/../../libs/", LIBS.as_posix() + "/"), "utf-8")
    if provenance is not None:
        (folder / "PROVENANCE.json").write_text(json.dumps(provenance), encoding="utf-8")
    return script


def fidelity(*accepted: dict[str, Any], **tolerances: int) -> dict[str, Any]:
    member: dict[str, Any] = {"accepted": list(accepted)}
    if tolerances:
        member["tolerances"] = tolerances
    return {"schema": "fenolite.provenance.v0", "fidelity": member}


def verify(
    monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any], str]:
    hide_kicad(monkeypatch, cwd)
    return run(monkeypatch, cwd, "verify-source", *args)


def codes(envelope: dict[str, Any]) -> list[str]:
    return [issue["code"] for issue in envelope["issues"]]


def statuses(envelope: dict[str, Any]) -> dict[str, str]:
    return {str(level["level"]): level["status"] for level in envelope["result"]["levels"]}


# --- the authored fixture --------------------------------------------------------------------------


def test_authored_board_proves_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    before = (tree_snapshot(SCRIPT.parent), tree_snapshot(ORIGINAL))
    code, env, err, _ = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL))
    assert code == 0, err
    result = env["result"]
    assert result["equivalent"] is True and result["differences"] == []
    assert statuses(env) == {
        "1": "equal", "2": "equal", "3": "equal", "4": "equal", "5": "equal", "6": "equal", "7": "equal",
        "S": "equal", "8": "equal",
    }  # fmt: skip
    routing = next(level for level in result["levels"] if level["level"] == 5)
    assert routing["summary"]["strict"]["vias"]["matched"] == 3
    assert result["build"] == {
        "target": "kicad-10", "files": result["build"]["files"], "copper_check": "refuse", "copy": False,
    }  # fmt: skip
    assert result["against"]["backend"] == "kicad" and "sensor.kicad_pcb" in result["against"]["files"]
    assert "fidelity.level-skipped" not in codes(env)
    drawn = next(level for level in result["levels"] if level["level"] == "S")
    assert drawn["summary"]["symbols"] == 3 and drawn["summary"]["extraction_issues"] == 0
    assert "H-K-DRAWN-CONNECT" in env["evidence"]["hypotheses"]
    assert (tree_snapshot(SCRIPT.parent), tree_snapshot(ORIGINAL)) == before


def test_hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("verify-source ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    code, env, err, _ = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL))
    assert code == 0, err
    assert all(status in ("equal", "skipped") for status in statuses(env).values())


def test_no_temporary_residue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The temporary folder is gone and no temporary path is in the reply."""
    system = tmp_path / "system-tmp"  # a private temporary root: parallel runs share the real one
    system.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(system))
    before = {p.name for p in system.glob("fenolite-verify-*")}
    _, _, _, out = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL))
    assert {p.name for p in system.glob("fenolite-verify-*")} == before
    assert "fenolite-verify-" not in out and tempfile.gettempdir() not in out.replace(str(tmp_path), "")


def test_deterministic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, _, _, first = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL))
    _, _, _, second = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL))
    assert without_elapsed(first) == without_elapsed(second)


def test_levels_subset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = verify(
        monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL), "--levels", "1-3,S"
    )
    assert code == 0 and statuses(env) == {"1": "equal", "2": "equal", "3": "equal", "S": "equal"}


# --- differences and acceptances -------------------------------------------------------------------


def test_one_planted_difference(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "moved", VIA, MOVED)
    code, env, _, _ = verify(monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL))
    assert code == 5 and env["result"]["equivalent"] is False
    vias = [i for i in env["issues"] if i["code"] == "equiv.via-missing"]
    assert len(vias) == 2 and all(i["where"].startswith("GND:via:top-bottom:") for i in vias)
    assert statuses(env)["5"] == "differs"
    pixels = [i for i in env["issues"] if i["code"] == "equiv.render-pixels"]
    assert pixels and "the visual diff names" in pixels[0]["hint"]


def test_a_fenolite_limit_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "moved", VIA, MOVED, fidelity(ACCEPT_VIA, ACCEPT_PIXELS))
    code, env, err, _ = verify(monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL))
    assert code == 0, err
    assert statuses(env)["5"] == "accepted" and statuses(env)["8"] == "accepted"
    accepted = env["result"]["accepted"]
    assert {row["rule"] for row in accepted} == {"A001", "A002"}
    assert {row["kind"] for row in accepted if row["rule"] == "A001"} == {"via-missing"}
    assert env["result"]["provenance"]["accepted"] == 2


def test_fixed_since(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "fixed", provenance=fidelity(ACCEPT_VIA))
    code, env, _, _ = verify(monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL))
    unused = [i for i in env["issues"] if i["code"] == "fidelity.accepted-unused"]
    assert code == 0 and [i["where"] for i in unused] == ["A001"] and unused[0]["severity"] == "warning"


def test_an_entry_of_a_skipped_level_is_not_unused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = {**ACCEPT_VIA, "level": "S", "kind": "item-missing", "where": "*"}
    script = variant(tmp_path / "skipped", provenance=fidelity(entry))
    code, env, _, _ = verify(
        monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL), "--levels", "1-7"
    )
    assert code == 0 and "fidelity.accepted-unused" not in codes(env)


def test_kind_of_another_level(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "bad", provenance=fidelity({**ACCEPT_VIA, "level": 6}))
    code, _, err, _ = verify(monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL))
    assert code == 3 and err["code"] == "FEN-3004" and "A001" in err["message"]


def test_provenance_tolerance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "tol", provenance=fidelity(length_nm=100))
    _, env, _, _ = verify(monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL))
    assert env["result"]["tolerances"]["length_nm"] == 100
    _, env, _, _ = verify(
        monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL), "--tolerance-nm", "0"
    )
    assert env["result"]["tolerances"]["length_nm"] == 0


# --- recording -------------------------------------------------------------------------------------


def test_record_a_passing_proof(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(
        tmp_path / "rec", provenance={"schema": "fenolite.provenance.v0", "library": {"id": "x"}}
    )
    args = (str(script), "--against", str(ORIGINAL), "--record", "--timestamp", "2026-11-01T00:00:00Z")
    code, env, _, _ = verify(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0
    plan_id = env["result"]["plan_id"]
    assert [row["path"] for row in env["result"]["plan"]] == ["rec/PROVENANCE.json"]
    code, env, err, _ = verify(monkeypatch, tmp_path, *args, "--confirm", "--plan", plan_id)
    assert code == 0, err
    assert [w["path"] for w in env["receipt"]["written"]] == ["rec/PROVENANCE.json"]
    written = json.loads((tmp_path / "rec" / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert written["library"] == {"id": "x"}
    proof = written["fidelity"]["proof"]
    assert proof["date"] == "2026-11-01T00:00:00Z" and proof["levels"]["5"] == "equal"
    assert set(proof["levels"].values()) <= {"equal", "skipped"}
    code, again, _, _ = verify(monkeypatch, tmp_path, *args, "--dry-run")
    assert again["result"]["plan"][0]["sha256"] == env["receipt"]["written"][0]["sha256"]


def test_accept_writes_an_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "acc", VIA, MOVED)
    code, env, _, _ = verify(
        monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL), "--levels", "1-7"
    )
    key = next(f"{d['level']}:{d['kind']}:{d['where']}" for d in env["result"]["differences"] if d["b"])
    first = next(f"{d['level']}:{d['kind']}:{d['where']}" for d in env["result"]["differences"] if d["a"])
    args = (
        str(script), "--against", str(ORIGINAL), "--levels", "1-7", "--record", "--accept", first, "--accept",
        key, "--reason", "planted by the test", "--timestamp", "2026-11-01T00:00:00Z",
    )  # fmt: skip
    code, env, err, _ = verify(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0, err
    assert [e["id"] for e in env["result"]["new_accepted"]] == ["A001", "A002"]
    written = json.loads((tmp_path / "acc" / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert [e["decided"] for e in written["fidelity"]["accepted"]] == ["2026-11-01", "2026-11-01"]
    assert written["fidelity"]["proof"]["levels"]["5"] == "accepted"


def test_accept_needs_a_reason(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = verify(
        monkeypatch, tmp_path, str(SCRIPT), "--against", str(ORIGINAL), "--record", "--accept",
        "5:via-missing:GND:via:top-bottom:1000,2000",
    )  # fmt: skip
    assert code == 2 and err["code"] == "FEN-2001"


# --- inputs and failures ---------------------------------------------------------------------------


def test_build_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant(tmp_path / "broken", '"Mini:Mini_R_0603"', '"Mini:No_Such_Land"')
    code, env, _, _ = verify(monkeypatch, tmp_path, str(script), "--against", str(ORIGINAL))
    assert code == 5 and codes(env)[0] == "fidelity.build-failed" and len(codes(env)) >= 2
    assert set(statuses(env).values()) == {"skipped"}


def _old_project(tmp_path: Path) -> Path:
    old = tmp_path / "old"
    shutil.copytree(ORIGINAL, old)
    board = old / "sensor.kicad_pcb"
    text = board.read_text(encoding="utf-8")
    head = text.split("\n", 2)
    assert "(version " in head[1]
    board.write_text(text.replace(head[1], "\t(version 20240108)", 1), encoding="utf-8")
    return old


def test_old_file_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(_old_project(tmp_path)))
    assert code == 3 and err["code"] == "FEN-3003"
    assert "--upgrade" in err["hint"] and "kicad-cli pcb upgrade" in err["hint"]


def test_upgrade_without_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    old = _old_project(tmp_path)
    code, _, err, _ = verify(monkeypatch, tmp_path, str(SCRIPT), "--against", str(old), "--upgrade")
    assert code == 6 and err["code"] == "FEN-6001"


@pytest.mark.parametrize(
    ("args", "code", "error"),
    [
        (("missing.py", "--against", str(ORIGINAL)), 3, "FEN-3001"),
        ((str(SCRIPT), "--against", str(ORIGINAL / "nothing")), 3, "FEN-3001"),
        ((str(SCRIPT), "--against", str(SCRIPT)), 2, "FEN-2001"),
        ((str(ORIGINAL / "sensor.kicad_pcb"), "--against", str(ORIGINAL)), 2, "FEN-2001"),
        ((str(SCRIPT), "--against", str(ORIGINAL), "--levels", "9"), 2, "FEN-2001"),
        ((str(SCRIPT), "--against", str(ORIGINAL), "--render-pitch-um", "0"), 2, "FEN-2001"),
    ],
)
def test_usage_and_input_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...], code: int, error: str
) -> None:
    found, _, err, _ = verify(monkeypatch, tmp_path, *args)
    assert found == code and err["code"] == error, err


def test_altium_original(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Level S is skipped for an Altium original, and the other levels run."""
    blink = ROOT / "examples" / "blink_2layer" / "design.py"
    project = DATA / "altium" / "blink" / "blink.PrjPcb"
    _, env, err, _ = verify(
        monkeypatch, tmp_path, str(blink), "--against", str(project), "--frame", "relative"
    )
    assert env, err
    levels = {str(level["level"]): level for level in env["result"]["levels"]}
    assert levels["S"]["status"] == "skipped" and levels["S"]["reason"] == "altium-drawing-unread"
    assert levels["1"]["status"] != "skipped" and levels["2"]["status"] != "skipped"
    assert env["result"]["against"]["backend"] == "altium"


# --- codes and documentation -----------------------------------------------------------------------


def test_codes_are_closed_and_explained(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    emitted = {code for code in ISSUE_CODES}
    source = Path(cmd_verify_source.__file__).read_text(encoding="utf-8")
    assert {code for code in emitted if f'"{code}"' in source} == set(ISSUE_CODES)
    assert ("fenolite.cli.cmd_verify_source", "ISSUE_CODES") in cli_explain.TABLES
    for code in ISSUE_CODES:
        found, env, _, _ = run(monkeypatch, tmp_path, "explain", code)
        assert found == 0, code
    assert not set(ISSUE_CODES) & set(EQUIVALENCE_CODES)


def test_docs_name_every_code() -> None:
    contract = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    section = contract.split("\n## verify-source\n", 1)[1].split("\n## ", 1)[0]
    for code in ISSUE_CODES:
        assert f"`{code}`" in section, code
    page = (ROOT / "docs" / "fidelity.md").read_text(encoding="utf-8")
    for words in ("fidelity.accepted", "fidelity.proof", "--record", "Reading a failed level"):
        assert words in page


def test_discoverable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "capabilities", "--no-tools")
    entry = next(c for c in env["result"]["commands"] if c["name"] == "verify-source")
    assert code == 0 and entry["mutates"] is True and entry["schema"] == "fenolite.verify-source.v0"
