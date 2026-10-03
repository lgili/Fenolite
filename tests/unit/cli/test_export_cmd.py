# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export`` against the fake ``kicad-cli`` (capability cli-contract, "Export command";
manufacturing-exports, "Export evidence"; change c0024). Hermetic."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import _schema
import pytest
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot

from fenolite.exports import EVIDENCE
from fenolite.exports.manifest import content_sha256

ALL = ("--all", "--manifest")
FILES = [
    "fab/drill/board-NPTH.drl",
    "fab/drill/board-PTH.drl",
    "fab/gerbers/board-Edge_Cuts.gbr",
    "fab/gerbers/board-F_Cu.gbr",
    "fab/gerbers/board-job.gbrjob",
    "fab/netlist/board.d356",
    "fab/pos/board-pos.csv",
    "fab/fenolite-artifacts.json",
]


@pytest.fixture
def root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    return authored_project(tmp_path, major=10)


def _fake(tmp_path: Path, **options: object) -> str:
    return str(fake_kicad_cli(tmp_path / "bin", **options))  # type: ignore[arg-type]


def test_plan_then_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", *ALL, "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0, env
    assert [p["path"] for p in env["result"]["plan"]] == FILES
    assert list(work.iterdir()) == []

    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    written = {w["path"]: w["sha256"] for w in env["receipt"]["written"]}
    assert list(written) == FILES
    for path, sha in written.items():
        assert hashlib.sha256((work / path).read_bytes()).hexdigest() == sha
    assert env["result"]["kinds"] == ["gerbers", "drill", "pos", "ipcd356"]
    assert env["result"]["board"] == "board.kicad_pcb" and env["result"]["out"] == "fab"
    assert env["result"]["tool_version"] == "10.0.6"


def test_manifest_matches_the_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    stamp = "2026-01-02T03:04:05+00:00"
    args = ("export", str(root), "--out", "fab", *ALL, "--kicad-cli", _fake(tmp_path), "--timestamp", stamp)
    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0, env
    text = (work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    assert manifest["generated"] == stamp
    board = (root / "board.kicad_pcb").read_bytes()
    assert manifest["board"]["path"] == "board.kicad_pcb"
    assert manifest["board"]["sha256"] == hashlib.sha256(board).hexdigest() == env["input"]["sha256"]
    assert manifest["board"]["format_version"] == int(env["input"]["format_version"])
    assert manifest["tool"] == {"name": "kicad-cli", "version": "10.0.6"}
    assert [e["path"] for e in manifest["artifacts"]] == sorted(p[4:] for p in FILES[:-1])
    for entry in manifest["artifacts"]:
        data = (work / "fab" / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data) and entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["content_sha256"] == content_sha256(data, entry["kind"])
    layers = {e["path"]: e["layer"] for e in manifest["artifacts"]}
    assert layers["gerbers/board-F_Cu.gbr"] == "F.Cu" and layers["gerbers/board-job.gbrjob"] is None
    result = {a["path"]: a for a in env["result"]["artifacts"]}
    assert all("evidence" not in a for a in result.values())
    assert result["pos/board-pos.csv"]["sha256"] == result["pos/board-pos.csv"]["content_sha256"]
    for needle in (str(tmp_path), str(Path.home()), "fenolite-kicad-"):
        assert needle not in text and needle not in json.dumps(env["result"])

    code, _, _, _ = run(monkeypatch, work, *args, "--confirm", "--no-backup")
    assert code == 0 and (work / "fab" / "fenolite-artifacts.json").read_text(encoding="utf-8") == text


def test_selected_kinds_only_and_no_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path)
    args = ("export", str(root), "--out", "fab", "--drill", "--pos", "--kicad-cli", fake, "--dry-run")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and env["result"]["kinds"] == ["drill", "pos"]
    assert [p["path"] for p in env["result"]["plan"]] == [
        "fab/drill/board-NPTH.drl",
        "fab/drill/board-PTH.drl",
        "fab/pos/board-pos.csv",
    ]
    exports = [c["args"][2] for c in calls(Path(fake)) if c["args"][:2] == ["pcb", "export"]]
    assert exports == ["drill", "pos"]


def test_confirmation_is_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", *ALL, "--kicad-cli", _fake(tmp_path))
    code, env, err, _ = run(monkeypatch, work, *args)
    assert code == 4 and err["code"] == "FEN-4001" and len(env["result"]["plan"]) == len(FILES)
    assert list(work.iterdir()) == []


def test_one_failing_kind_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path, export_fail=("drill",))
    code, env, err, _ = run(
        monkeypatch, work, "export", str(root), "--out", "fab", "--all", "--kicad-cli", fake, "--confirm"
    )
    assert code == 5 and err["code"] == "FEN-5001"
    (failure,) = env["issues"]
    assert failure["code"] == "export.failed" and failure["where"] == "drill"
    assert "plan" not in env["result"] and env["receipt"] is None
    assert not (work / "fab").exists()
    assert [a["kind"] for a in env["result"]["artifacts"]].count("gerbers") == 3  # the other kinds still ran


def test_no_kind_selected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--confirm")
    assert code == 2 and err["code"] == "FEN-2001"


def test_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--all", "--dry-run")
    assert code == 6 and err["code"] == "FEN-6001"


def test_unsupported_major(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path, version="8.0.9")
    code, _, err, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--all", "--kicad-cli", fake, "--dry-run"
    )
    assert code == 6 and err["code"] == "FEN-6002"


def test_missing_path_and_unreadable_board(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path)
    tail = ("--out", "fab", "--all", "--kicad-cli", fake, "--dry-run")
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(tmp_path / "nowhere"), *tail)
    assert code == 3 and err["code"] == "FEN-3001"
    bad = tmp_path / "bad.kicad_pcb"
    bad.write_text("(kicad_pcb (version 20260206) (unclosed", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "export", str(bad), *tail)
    assert code == 3 and err["code"].startswith("FEN-3")


def test_a_kind_that_writes_nothing_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path, export_files={"pos": {}})
    code, env, _, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--pos", "--kicad-cli", fake, "--dry-run"
    )
    assert code == 5 and env["issues"][0]["code"] == "export.failed"
    assert "wrote no file" in env["issues"][0]["message"]


def test_source_is_untouched(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path, writes=("x.kicad_prl",), rewrite_input=True)
    before = tree_snapshot(root)
    work = tmp_path / "elsewhere"
    work.mkdir()
    code, env, _, _ = run(
        monkeypatch, work, "export", str(root), "--out", "fab", *ALL, "--kicad-cli", fake, "--confirm"
    )
    assert code == 0, env
    assert tree_snapshot(root) == before and not (root / "x.kicad_prl").exists()
    assert env["result"]["tool_writes"] == ["x.kicad_prl"]
    assert (work / "fab" / "gerbers" / "board-F_Cu.gbr").is_file()


def test_evidence_in_the_envelope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, tmp_path, "export", str(root), "--out", "fab", "--pos", "--kicad-cli", _fake(tmp_path),
        "--dry-run",
    )  # fmt: skip
    assert code == 0
    assert env["evidence"]["level"] == EVIDENCE.level.value
    assert env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    assert env["evidence"]["hypotheses"] == ["H-K-EXPORT-FILES", "H-K-EXPORT-REPEAT"]
