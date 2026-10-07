# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` on Altium input (capabilities altium-verification, "Check on Altium inputs" and
"Altium check stage evidence", and verification-loop, "Check command input"; change c0044). No external
tool runs: ``subprocess`` is patched to raise in every test."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from _altium_built import built_blink
from _checkcli import run, without_elapsed
from _needles import absent

from fenolite.backends.altium import cfb as compound_writer
from fenolite.checks.documents import ALL_DOCUMENT_STAGES, DOCUMENT_STAGES
from fenolite.core.evidence import Level, strength
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[3]
BLINK = ROOT / "tests" / "data" / "altium" / "blink"
RAN = ("model.validate", "erc.lite", "netlist.assignment_compare", "roundtrip.rta0", "roundtrip.rta1")


@pytest.fixture(autouse=True)
def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("check ran a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _stages(envelope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {stage["name"]: stage for stage in envelope["result"]["stages"]}


def _copy(tmp_path: Path) -> Path:
    return Path(shutil.copytree(BLINK, tmp_path / "blink"))


def _cut(path: Path) -> None:
    path.write_bytes(path.read_bytes()[:100])


def test_own_project_is_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, raw = run(monkeypatch, tmp_path, "check", str(BLINK / "blink.PrjPcb"))
    assert code == 0 and env["ok"] is True
    project = env["result"]["project"]
    assert (project["backend"], project["project"], project["board"], project["built"]) == (
        "altium",
        "blink.PrjPcb",
        "blink.PcbDoc",
        False,
    )
    names = ["blink.PcbDoc", "blink.PcbLib", "blink.PrjPcb", "blink.SchDoc", "blink.SchLib"]
    assert project["files"] == names and project["skipped"] == []
    assert [d["name"] for d in project["documents"]] == names
    assert project["documents"][0] == {"name": "blink.PcbDoc", "kind": "altium_pcbdoc", "role": "pcb"}
    stages = _stages(env)
    assert list(stages) == list(DOCUMENT_STAGES)
    assert {name: stages[name]["status"] for name in RAN} == dict.fromkeys(RAN, "ok")
    assert (stages["roundtrip.rta2"]["status"], stages["roundtrip.rta2"]["reason"]) == (
        "skipped",
        "native-input",
    )
    (pair,) = stages["netlist.assignment_compare"]["summary"]["pairs"]
    assert (pair["a"], pair["b"], pair["differences"]) == ("schematic", "pcb", 0) and pair["common"] == 36
    assert stages["roundtrip.rta0"]["summary"]["unjudged"] == {"not-a-container": 1}
    assert stages["roundtrip.rta1"]["summary"]["documents"] == 5
    assert not [i for i in env["issues"] if i["severity"] == "error"]
    assert env["input"]["path"] == "blink.PrjPcb" and env["input"]["kind"] == "altium_prjpcb"
    assert len(env["input"]["sha256"]) == 64 and absent(str(ROOT), raw)


def test_levels_on_the_own_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Levels on the own project": no oracle label, and the envelope is the lowest stage."""
    _, env, _, raw = run(monkeypatch, tmp_path, "check", str(BLINK / "blink.PrjPcb"))
    stages = _stages(env)
    levels = {name: Level(stages[name]["evidence"]["level"]) for name in RAN}
    top = strength(Level.CORPUS_VERIFIED)
    assert all(strength(level) <= top for level in levels.values())
    assert all(stage["evidence"]["oracle"] is None for stage in stages.values())
    for label in ("ORACLE-VERIFIED", "KICAD-VERIFIED", "ALTIUM-VERIFIED"):
        assert label not in raw
    assert env["evidence"]["level"] == min(levels.values(), key=strength).value
    register = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    for stage, row in (("roundtrip.rta0", "H-A-VER-RTA0"), ("roundtrip.rta1", "H-A-VER-RTA1")):
        named = row in stages[stage]["evidence"]["hypotheses"]
        assert named is not register[row].result.startswith("confirmed"), row
    assert "H-A-VER-ERC" in stages["erc.lite"]["evidence"]["hypotheses"]
    assert "H-K-CHECK-ERC" in stages["erc.lite"]["evidence"]["hypotheses"]
    assert "H-A-IMP-NETLIST" in stages["netlist.assignment_compare"]["evidence"]["hypotheses"]
    assert stages["roundtrip.rta2"]["evidence"]["level"] == "UNVERIFIED"


def test_one_library_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(BLINK / "blink.PcbLib"))
    stages = _stages(env)
    assert code == 0 and env["issues"] == []
    assert (stages["roundtrip.rta0"]["status"], stages["roundtrip.rta1"]["status"]) == ("ok", "ok")
    assert stages["model.validate"]["status"] == "skipped"
    assert stages["erc.lite"]["reason"] == "no-schematic"
    assert stages["netlist.assignment_compare"]["reason"] == "single-source"
    project = env["result"]["project"]
    assert (project["project"], project["board"], project["files"]) == (None, None, ["blink.PcbLib"])
    assert env["input"]["kind"] == "altium_pcblib"
    assert env["evidence"]["level"] in ("INFERRED", "CORPUS-VERIFIED")


def test_one_schematic_alone_in_both_forms(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sample = ROOT / "tests" / "data" / "altium" / "sample"
    for path, kind, judged in (
        (sample / "altium_sample.SchDoc", "altium_schdoc_ascii", 0),
        (sample / "binary" / "altium_sample.SchDoc", "altium_schdoc_binary", 1),
    ):
        code, env, _, _ = run(monkeypatch, tmp_path, "check", str(path))
        stages = _stages(env)
        assert code == 0 and env["input"]["kind"] == kind
        assert stages["erc.lite"]["status"] == "ok" and stages["model.validate"]["status"] == "ok"
        assert stages["roundtrip.rta0"]["summary"]["documents"] == judged
        assert stages["roundtrip.rta0"]["status"] == ("ok" if judged else "skipped")
        assert (
            stages["roundtrip.rta1"]["summary"]["bytes_equal"]
            == stages["roundtrip.rta1"]["summary"]["streams"]
        )


def test_unreadable_single_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = tmp_path / "blink.PcbDoc"
    shutil.copy(BLINK / "blink.PcbDoc", board)
    _cut(board)
    code, env, error, _ = run(monkeypatch, tmp_path, "check", str(board))
    assert code == 3 and error["code"] == "FEN-3004" and env["ok"] is False
    assert [i["code"] for i in env["issues"]] == ["check.read-refused"]
    assert env["issues"][0]["where"].startswith("blink.PcbDoc")
    assert str(tmp_path) not in error["where"] and error["where"].startswith("blink.PcbDoc")


def test_project_with_one_unreadable_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _cut(root / "blink.PcbDoc")
    code, env, error, _ = run(monkeypatch, tmp_path, "check", str(root))
    stages = _stages(env)
    assert code == 5 and error["code"] == "FEN-5001"
    first = env["issues"][0]
    assert first["code"] == "check.read-refused" and first["where"].startswith("blink.PcbDoc")
    assert [i["code"] for i in env["issues"]].count("check.read-refused") == 1
    assert stages["netlist.assignment_compare"]["reason"] == "single-source"
    assert stages["model.validate"]["status"] == "ok" and set(stages["model.validate"]["summary"]) == {
        "schematic"
    }
    assert stages["roundtrip.rta1"]["summary"]["unjudged"] == {"read-refused": 1}


def test_missing_document_is_a_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _copy(tmp_path)
    (root / "blink.PcbLib").unlink()
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root / "blink.PrjPcb"))
    assert code == 0
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"][:1]] == [
        ("check.document-missing", "warning", "blink.PcbLib")
    ]
    assert env["result"]["project"]["skipped"] == [{"name": "blink.PcbLib", "reason": "missing"}]


def test_dispatch_of_a_project_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Altium project folder dispatched"; ``--kicad-cli`` and ``--timeout`` are ignored."""
    root = _copy(tmp_path)
    code, env, _, _ = run(
        monkeypatch, tmp_path, "check", str(root), "--kicad-cli", str(tmp_path / "none"), "--timeout", "1"
    )
    assert code == 0 and env["result"]["project"]["project"] == "blink.PrjPcb"
    assert {stage["name"] for stage in env["result"]["stages"]} <= set(DOCUMENT_STAGES)
    assert env["input"]["path"] == "blink.PrjPcb"
    assert not (root / ".fenolite").exists()


def test_folder_with_two_backends(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "mixed"
    folder.mkdir()
    (folder / "a.kicad_pcb").write_text("(kicad_pcb)")
    shutil.copy(BLINK / "blink.PrjPcb", folder / "b.PrjPcb")
    code, _, error, _ = run(monkeypatch, tmp_path, "check", str(folder))
    assert code == 2 and error["code"] == "FEN-2001"
    assert "a.kicad_pcb" in error["hint"] and "b.PrjPcb" in error["hint"]
    # a KiCad folder with a stray Altium library and no project file stays KiCad input
    (folder / "b.PrjPcb").unlink()
    shutil.copy(BLINK / "blink.PcbLib", folder / "stray.PcbLib")
    code, _, error, _ = run(monkeypatch, tmp_path, "check", str(folder), "--stages", "roundtrip")
    assert error.get("code") != "FEN-2001" or "two backends" not in error.get("message", "")


def test_folder_without_exactly_one_project_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "two"
    folder.mkdir()
    for name in ("a.PrjPcb", "b.PrjPcb"):
        shutil.copy(BLINK / "blink.PrjPcb", folder / name)
    code, _, error, _ = run(monkeypatch, tmp_path, "check", str(folder))
    assert code == 2 and error["code"] == "FEN-2001"
    assert "a.PrjPcb" in error["hint"] and "b.PrjPcb" in error["hint"] and str(tmp_path) not in error["hint"]
    lone = tmp_path / "lone"
    lone.mkdir()
    shutil.copy(BLINK / "blink.SchDoc", lone / "blink.SchDoc")
    code, _, error, _ = run(monkeypatch, tmp_path, "check", str(lone))
    assert code == 2 and error["code"] == "FEN-2001" and "0 project files" in error["hint"]


def test_stage_names_and_missing_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = str(BLINK / "blink.PrjPcb")
    for stages in ("drc.kicad", "roundtrip", "model.validate,,erc.lite", ""):
        code, _, error, _ = run(monkeypatch, tmp_path, "check", project, "--stages", stages)
        assert code == 2 and error["code"] == "FEN-2001", stages
        assert error["hint"] == f"stages: {','.join(ALL_DOCUMENT_STAGES)}"
    code, env, _, _ = run(monkeypatch, tmp_path, "check", project, "--stages", "roundtrip.rta1,erc.lite")
    assert code == 0 and [s["name"] for s in env["result"]["stages"]] == ["erc.lite", "roundtrip.rta1"]
    for missing in ("gone.PcbDoc", "gone.PrjPcb"):
        code, _, error, _ = run(monkeypatch, tmp_path, "check", str(tmp_path / missing))
        assert code == 3 and error["code"] == "FEN-3001", missing


def test_failed_copy_lowers_the_stage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    real = compound_writer.write_compound

    def lossy(entries: Sequence[Any]) -> bytes:
        return real(entries[1:])

    monkeypatch.setattr(compound_writer, "write_compound", lossy)
    code, env, error, _ = run(
        monkeypatch, tmp_path, "check", str(BLINK / "blink.PcbDoc"), "--stages", "roundtrip.rta0"
    )
    (stage,) = env["result"]["stages"]
    assert code == 5 and error["code"] == "FEN-5001"
    assert stage["status"] == "errors" and stage["evidence"]["level"] == "UNVERIFIED"
    (found,) = env["issues"]
    assert found["code"] == "check.rta0-failed" and found["where"].startswith("blink.PcbDoc:")
    assert env["evidence"]["level"] == "UNVERIFIED"


def test_two_runs_are_equal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    outs = [run(monkeypatch, tmp_path, "check", str(BLINK))[3] for _ in range(2)]
    assert without_elapsed(outs[0]) == without_elapsed(outs[1])
    assert str(ROOT) not in outs[0] and str(tmp_path) not in outs[0]
    other = tmp_path / "elsewhere"
    other.mkdir()
    again = run(monkeypatch, other, "check", str(BLINK / "blink.PrjPcb"))[3]
    assert without_elapsed(again) == without_elapsed(outs[0])


def test_built_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A built blink: the model is the hub of the comparison, ``erc.lite`` runs on it, and RT-A2 is
    judged."""
    root = built_blink(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root))
    stages = _stages(env)
    assert code == 0, env["issues"]
    assert env["result"]["project"]["built"] is True
    assert [stage["status"] for stage in stages.values()] == ["ok"] * 8
    pairs = stages["netlist.assignment_compare"]["summary"]["pairs"]
    assert [(p["a"], p["b"], p["differences"]) for p in pairs] == [
        ("model", "schematic", 0),
        ("model", "pcb", 0),
    ]
    assert stages["model.validate"]["evidence"]["level"] == "INFERRED"
    assert stages["erc.lite"]["evidence"]["hypotheses"] == ["H-K-CHECK-ERC"]
    rta2 = stages["roundtrip.rta2"]
    assert rta2["summary"]["holds"] is True and rta2["evidence"]["level"] == "INFERRED"
    assert "H-A-VER-RTA2-3" in rta2["evidence"]["hypotheses"]
    assert "roundtrip.rta3" not in stages  # opt-in (change c0090)
    (root / ".fenolite" / "circuit.json").write_text("{", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(root))
    stages = _stages(env)
    assert code == 0 and env["issues"][0]["code"] == "check.cache-unreadable"
    assert stages["roundtrip.rta2"]["reason"] == "cache-unreadable"
    assert str(tmp_path) not in env["issues"][0]["message"]
