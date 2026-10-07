# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite kit`` (capability cli-contract, "Kit command"). The runs here are simulated by Fenolite's own
writers and no record of them is committed."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main
from fenolite.cli import _kit
from fenolite.cli.cmd_kit import ISSUE_CODES
from fenolite.verify.kit import record
from fenolite.verify.kit.manifest import build_kit, load_kit

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests" / "unit" / "verify" / "kit"))
from _simulate import DATE, VERSION, simulate, simulated_judge  # noqa: E402

CONTRACT = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *argv: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """``(exit code, envelope, error)`` of ``fenolite kit <argv> --json`` run in ``cwd``."""
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.chdir(cwd)
        patch.setattr("sys.stdout", out)
        patch.setattr("sys.stderr", err)
        code = cli_main.main(["kit", *argv, "--json"])
    envelope = json.loads(out.getvalue()) if out.getvalue() else {}
    return code, envelope, json.loads(err.getvalue()) if err.getvalue() else {}


def snapshot(folder: Path) -> dict[str, bytes]:
    files = [path for path in sorted(folder.rglob("*")) if path.is_file()]
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in files}


@pytest.fixture
def run_folder(tmp_path: Path) -> Path:
    """A kit under ``tmp_path/work/kit`` with a complete simulated run (marked synthetic)."""
    folder = tmp_path / "work" / "kit"
    build_kit(folder, sources=_kit.kit_sources())
    simulate(folder)
    return folder


def test_build_is_deterministic_and_follows_the_write_rules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "Deterministic kit" through the command: dry run, confirm, receipt, equal folders."""
    args = ("build", "--seed", "1", "--timestamp", "2026-10-06T00:00:00Z")
    code, env, err = run(monkeypatch, tmp_path, *args, "--out", "a")
    assert code == 4 and err["code"] == "FEN-4001" and not (tmp_path / "a").exists()
    code, env, _ = run(monkeypatch, tmp_path, *args, "--out", "a", "--dry-run")
    assert code == 0 and not (tmp_path / "a").exists()
    plan = [entry["path"] for entry in env["result"]["plan"]]
    assert "a/kit.json" in plan and "a/results/form.json" in plan and "a/kit_script.pas" in plan
    code, env, _ = run(monkeypatch, tmp_path, *args, "--out", "a", "--confirm")
    assert code == 0 and [w["path"] for w in env["receipt"]["written"]] == plan
    assert run(monkeypatch, tmp_path, *args, "--out", "b", "--confirm")[0] == 0
    assert snapshot(tmp_path / "a") == snapshot(tmp_path / "b")
    result = env["result"]
    assert [s["name"] for s in result["samples"]] == ["flat", "tree", "routed", "board6", "libs"]
    assert result["kit_sha256"] == load_kit(tmp_path / "a").digest and result["seed"] == 1
    assert result["scripted"] == ["K2.1", "K2.2", "K2.3", "K2.4", "K2.5"]
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["hypotheses"] == ["H-A-KIT-STABLE"]
    code, other, _ = run(monkeypatch, tmp_path, "build", "--out", "c", "--dry-run")
    assert (
        code == 0 and other["result"]["seed"] == 0 and other["result"]["timestamp"] == "2026-01-01T00:00:00Z"
    )
    assert other["result"]["kit_sha256"] != result["kit_sha256"]


def test_status_without_a_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Help and example": exit 0 and no run."""
    code, env, err = run(monkeypatch, tmp_path, "status")
    assert code == 0 and err == {} and env["result"] == {"runs": [], "stale": [], "problems": []}
    code, env, _ = run(monkeypatch, tmp_path, "status", "--repo", str(ROOT))
    assert code == 0 and env["result"]["runs"] == []


def test_verify_refuses_a_folder_that_is_no_kit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Verify refuses a folder that is no kit": exit 3 and FEN-3001."""
    (tmp_path / "empty").mkdir()
    code, _, err = run(monkeypatch, tmp_path, "verify", "empty")
    assert code == 3 and err["code"] == "FEN-3001"
    assert run(monkeypatch, tmp_path, "record", "empty", "--out", ".")[2]["code"] == "FEN-3001"


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for argv in (
        ("build",),
        ("verify",),
        ("verify", "x", "--out", "y"),
        ("status", "x"),
        ("build", "x", "--out", "y"),
    ):
        code, _, err = run(monkeypatch, tmp_path, *argv)
        assert code == 2 and err["code"] == "FEN-2001", argv
    (tmp_path / "none").mkdir()
    code, _, err = run(monkeypatch, tmp_path, "build", "--out", "k", "--samples", "none", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001" and "--samples" in err["hint"]


def test_verify_a_simulated_run(monkeypatch: pytest.MonkeyPatch, run_folder: Path) -> None:
    """Read-only; with the product's judge the repour step fails on Fenolite's own unpoured board, so the
    exit code is 5; the evidence of a synthetic run is never the kit label."""
    before = snapshot(run_folder)
    code, env, err = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert snapshot(run_folder) == before and env["receipt"] is None
    assert code == 5 and err["code"] == "FEN-5001"
    result = env["result"]
    assert result["counts"] == {"pass": len(result["steps"]) - 1, "fail": 1, "skipped": 0}
    assert [s["id"] for s in result["steps"] if s["outcome"] == "fail"] == ["K6.1"]
    assert result["synthetic"] and result["privacy"] == [] and result["altium_version"] == VERSION
    codes = {issue["code"] for issue in env["issues"]}
    assert codes == {"kit.step-failed", "kit.synthetic"} and codes <= set(ISSUE_CODES)
    assert env["evidence"]["level"] == "INFERRED"

    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert code == 0 and env["result"]["passed"] and env["evidence"]["level"] == "INFERRED"
    assert {h["id"]: h["outcome"] for h in env["result"]["hypotheses"]}["H-A-KIT-REPOUR"] == "pass"


def test_only_a_run_that_is_not_synthetic_carries_the_kit_label(
    monkeypatch: pytest.MonkeyPatch, run_folder: Path
) -> None:
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    simulate(run_folder, synthetic=False)
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert code == 0 and env["evidence"]["level"] == "ALTIUM-VERIFIED(kit)"
    simulate(run_folder, synthetic=False, skip=("K9.2",))
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert code == 0 and env["evidence"]["level"] == "INFERRED" and not env["result"]["passed"]
    assert "kit.step-skipped" in {issue["code"] for issue in env["issues"]}


def test_verify_lists_privacy_findings(monkeypatch: pytest.MonkeyPatch, run_folder: Path) -> None:
    home = "C:\\" + "Users" + "\\jdoe"
    (run_folder / "results" / "routed" / "outputs.txt").write_text("routed.GTL\n", encoding="utf-8")
    (run_folder / "results" / "flat" / "messages.txt").write_text(
        f"[Info] {home}\\flat.PrjPcb ok\n", encoding="utf-8"
    )
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert code == 0
    assert env["result"]["privacy"] == [
        {"file": "results/flat/messages.txt", "offset": 7, "kind": "home-folder", "text": home}
    ]
    assert [i["where"] for i in env["issues"] if i["code"] == "kit.privacy"] == ["results/flat/messages.txt"]


def test_record_refuses_a_synthetic_run(
    monkeypatch: pytest.MonkeyPatch, run_folder: Path, tmp_path: Path
) -> None:
    """No record, no archive and no row from a synthetic run, with or without ``--confirm``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    for flag in ("--dry-run", "--confirm"):
        code, env, err = run(monkeypatch, run_folder.parent, "record", "kit", "--out", str(repo), flag)
        assert code == 5 and err["code"] == "FEN-5001"
        assert env["issues"][0]["code"] == "kit.record-refused" and "synthetic" in env["issues"][0]["message"]
        assert env["result"]["rows"] == [] and env["receipt"] is None and "plan" not in env["result"]
    assert list(repo.iterdir()) == [] and not (run_folder.parent / "results.zip").exists()


def test_record_refuses_a_touched_kit(
    monkeypatch: pytest.MonkeyPatch, run_folder: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    simulate(run_folder, synthetic=False)
    (run_folder / "STEPS.md").write_text("edited\n", encoding="utf-8")
    code, env, _ = run(monkeypatch, run_folder.parent, "record", "kit", "--out", ".", "--confirm")
    assert code == 5 and "differ from kit.json" in env["issues"][0]["message"]
    assert not (run_folder.parent / "results.zip").exists()


def test_record_writes_the_archive_and_the_record(
    monkeypatch: pytest.MonkeyPatch, run_folder: Path, tmp_path: Path
) -> None:
    """The form of a record, on a simulated run whose form does not say synthetic; nothing of it is
    committed. Then ``status`` lists the run."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    simulate(run_folder, synthetic=False, script=True)
    work = run_folder.parent
    code, env, err = run(monkeypatch, work, "record", "kit", "--out", str(repo))
    assert code == 4 and err["code"] == "FEN-4001" and not (work / "results.zip").exists()
    code, env, _ = run(monkeypatch, work, "record", "kit", "--out", str(repo), "--confirm")
    assert code == 0, env["issues"]
    result = env["result"]
    archive = (work / "results.zip").read_bytes()
    made = json.loads(
        (repo / "docs" / "evidence" / "altium-kit" / f"{result['run_id']}.json").read_text("utf-8")
    )
    assert record.record_problems(made) == [] and made["archive"]["size"] == len(archive)
    assert result["run_id"].startswith(DATE + "-") and result["archive"] == made["archive"]
    rows = {row["id"]: row for row in result["rows"]}
    assert rows["H-A-KIT-RESAVE"]["label"] == f"ALTIUM-VERIFIED(kit; {VERSION}; {DATE}; {result['run_id']})"
    assert "H-A-KIT-SCRIPT" in rows and "H-A-KIT-REPOUR" in rows
    assert [w["path"] for w in env["receipt"]["written"]][0] == "results.zip"
    text = json.dumps(made)
    assert str(tmp_path) not in text and tmp_path.name not in text

    code, env, _ = run(monkeypatch, repo, "status")
    assert code == 0 and [r["run_id"] for r in env["result"]["runs"]] == [result["run_id"]]
    assert env["result"]["stale"] == [] and "H-A-KIT-RESAVE" in env["result"]["runs"][0]["passed"]
    # a second record of the same run is the same file; one with other content is refused
    target = repo / "docs" / "evidence" / "altium-kit" / f"{result['run_id']}.json"
    target.write_text(target.read_text("utf-8").replace('"Windows"', '"Linux"'), encoding="utf-8")
    code, env, _ = run(monkeypatch, work, "record", "kit", "--out", str(repo), "--confirm")
    assert code == 5 and "never edited" in env["issues"][0]["message"]


def test_the_contract_lists_the_codes() -> None:
    section = CONTRACT[CONTRACT.index("\n## kit\n") :]
    for code, severity in ISSUE_CODES.items():
        assert f"| `{code}` | {severity} |" in section, code
    for action in ("build", "verify", "record", "status"):
        assert f"fenolite kit {action}" in section


def test_a_project_file_saved_again_is_reported_and_refuses_nothing(
    monkeypatch: pytest.MonkeyPatch, run_folder: Path, tmp_path: Path
) -> None:
    """Change c0139: Altium writes a sample's own project file again when the project is saved. With the
    same documents it is an info and the run is recorded; with another list it is ``kit.file-changed``."""
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    simulate(run_folder, synthetic=False)
    project = run_folder / "flat" / "flat.PrjPcb"
    own = project.read_bytes()
    assert own.startswith(b"[Design]\r\n")
    project.write_bytes(own.replace(b"[Design]\r\n", b"[Design]\r\nHierarchyMode=0\r\n", 1))
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert code == 0 and env["result"]["passed"] and env["result"]["kit_problems"] == []
    assert env["result"]["kit_resaved"] == ["flat/flat.PrjPcb"]
    found = [issue for issue in env["issues"] if issue["code"] == "kit.project-resaved"]
    assert [(issue["severity"], issue["where"]) for issue in found] == [("info", "flat/flat.PrjPcb")]
    repo = tmp_path / "repo"
    repo.mkdir()
    code, env, _ = run(monkeypatch, run_folder.parent, "record", "kit", "--out", str(repo), "--dry-run")
    assert code == 0 and env["result"]["rows"] and len(env["result"]["plan"]) == 2

    project.write_bytes(own.replace(b"DocumentPath=flat.PcbDoc", b"DocumentPath=other.PcbDoc", 1))
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    assert code == 5 and env["result"]["kit_resaved"] == []
    assert env["result"]["kit_problems"] == ["flat/flat.PrjPcb differs from its digest in kit.json"]
    code, env, _ = run(monkeypatch, run_folder.parent, "record", "kit", "--out", str(repo), "--dry-run")
    assert code == 5 and env["issues"][0]["code"] == "kit.record-refused"


def test_a_file_of_another_kind_is_named_by_verify(monkeypatch: pytest.MonkeyPatch, run_folder: Path) -> None:
    """Change c0139: the schematic saved where step K5.1 wants the PCB document."""
    monkeypatch.setattr(_kit, "judge_document", simulated_judge)
    wrong = (run_folder / "board6" / "board6.SchDoc").read_bytes()
    (run_folder / "results" / "board6" / "board6.PcbDoc").write_bytes(wrong)
    code, env, _ = run(monkeypatch, run_folder.parent, "verify", "kit")
    failed = [step for step in env["result"]["steps"] if step["outcome"] == "fail"]
    assert code == 5 and [step["id"] for step in failed] == ["K5.1"]
    assert failed[0]["reasons"] == [
        "resave: the file is a schematic document, and the step wants a PCB document: "
        "save board6.PcbDoc of the sample, not another document of its project"
    ]
