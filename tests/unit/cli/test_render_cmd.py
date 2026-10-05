# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite render`` against the fake ``kicad-cli`` (capability cli-contract, "Render command";
manufacturing-exports, "Render views"; change c0024; cli-contract, "Manifest option of producing
commands"; change c0065). Hermetic."""

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


@pytest.fixture
def root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hide_kicad(monkeypatch, tmp_path)
    return authored_project(tmp_path, major=10)


def _fake(tmp_path: Path, **options: object) -> str:
    return str(fake_kicad_cli(tmp_path / "bin", **options))  # type: ignore[arg-type]


def test_four_views(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path)
    before = tree_snapshot(root)
    code, env, _, _ = run(
        monkeypatch,
        work,
        "render",
        str(root),
        "--out",
        "r",
        "--svg",
        "--png",
        "--kicad-cli",
        fake,
        "--confirm",
    )
    assert code == 0, env
    names = ["back.svg", "bottom.png", "front.svg", "top.png"]
    assert [v["path"] for v in env["result"]["views"]] == names
    assert [w["path"] for w in env["receipt"]["written"]] == [f"r/{n}" for n in names]
    for view in env["result"]["views"]:
        data = (work / "r" / view["path"]).read_bytes()
        assert view["bytes"] == len(data) and view["sha256"] == hashlib.sha256(data).hexdigest()
        assert view["kind"] == view["path"].rsplit(".", 1)[1]
    assert (work / "r" / "top.png").read_bytes().startswith(b"\x89PNG")
    assert env["issues"] == [] and tree_snapshot(root) == before
    assert env["evidence"]["level"] == EVIDENCE.level.value
    assert env["evidence"]["oracle"] == "kicad-cli 10.0.6"
    svg = [c["args"] for c in calls(Path(fake)) if c["args"][:3] == ["pcb", "export", "svg"]]
    assert ["--mirror" in a for a in svg] == [True, False]  # back, then front
    assert all("--mode-single" in a for a in svg)
    png = [c["args"] for c in calls(Path(fake)) if c["args"][:2] == ["pcb", "render"]]
    assert all(a[a.index("--width") + 1] == "1600" and a[a.index("--height") + 1] == "1200" for a in png)


def test_plan_then_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    args = ("render", str(root), "--out", "views", "--svg", "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, work, *args, "--dry-run")
    assert code == 0
    assert [p["path"] for p in env["result"]["plan"]] == ["views/back.svg", "views/front.svg"]
    assert list(work.iterdir()) == []
    code, env, _, _ = run(monkeypatch, work, *args, "--confirm")
    assert code == 0 and sorted(p.name for p in (work / "views").iterdir()) == ["back.svg", "front.svg"]


def test_a_failing_view_is_a_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path, export_fail=("render",))
    code, env, err, _ = run(
        monkeypatch,
        work,
        "render",
        str(root),
        "--out",
        "r",
        "--svg",
        "--png",
        "--kicad-cli",
        fake,
        "--confirm",
    )
    assert code == 0 and err == {}
    assert sorted(p.name for p in (work / "r").iterdir()) == ["back.svg", "front.svg"]
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("render.failed", "warning", "bottom.png"),
        ("render.failed", "warning", "top.png"),
    ]
    assert all("fenolite-kicad-" not in i["message"] for i in env["issues"])


def test_no_view_at_all_still_exits_zero(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path, export_fail=("render",))
    code, env, _, _ = run(
        monkeypatch, tmp_path, "render", str(root), "--out", "r", "--png", "--kicad-cli", fake, "--confirm"
    )
    assert code == 0 and env["result"]["views"] == [] and len(env["issues"]) == 2
    assert not (tmp_path / "r").exists()


def test_size_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    fake = _fake(tmp_path)
    base = ("render", str(root), "--out", "r", "--png", "--kicad-cli", fake, "--dry-run")
    code, _, err, _ = run(monkeypatch, tmp_path, *base, "--width", "10")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, *base, "--height", "9000")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, _, _ = run(monkeypatch, tmp_path, *base, "--width", "640", "--height", "480")
    assert code == 0
    args = calls(Path(fake))[-1]["args"]
    assert args[args.index("--width") + 1] == "640" and args[args.index("--height") + 1] == "480"


def test_no_view_selected_and_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "render", str(root), "--out", "r", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, tmp_path, "render", str(root), "--out", "r", "--svg", "--dry-run")
    assert code == 6 and err["code"] == "FEN-6001"


def _manifest(folder: Path) -> dict[str, dict[str, object]]:
    manifest = json.loads((folder / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    return {e["path"]: e for e in manifest["artifacts"]}


def test_manifest_views_join_the_fabrication_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    fake = _fake(tmp_path)
    tool = ("--kicad-cli", fake, "--confirm")
    code, env, _, _ = run(
        monkeypatch, work, "export", str(root), "--out", "out", "--all", "--manifest", *tool
    )
    assert code == 0, env
    fabrication = sorted(_manifest(work / "out"))
    code, env, _, _ = run(
        monkeypatch, work, "render", str(root), "--out", "out", "--svg", "--manifest", *tool
    )
    assert code == 0, env
    assert [w["path"] for w in env["receipt"]["written"]] == [
        "out/back.svg", "out/front.svg", "out/fenolite-artifacts.json",
    ]  # fmt: skip
    assert [v["kind"] for v in env["result"]["views"]] == ["svg", "svg"]  # the result is as before
    listed = _manifest(work / "out")
    assert sorted(listed) == sorted([*fabrication, "back.svg", "front.svg"])
    board = hashlib.sha256((root / "board.kicad_pcb").read_bytes()).hexdigest()
    for name in ("back.svg", "front.svg"):
        view = listed[name]
        data = (work / "out" / name).read_bytes()
        assert (view["kind"], view["layer"], view["state"]) == ("render", None, "generated")
        assert view["sha256"] == view["content_sha256"] == hashlib.sha256(data).hexdigest()
        assert view["from"] == {"board": board} and view["tool"] == "kicad-cli 10.0.6"
    assert listed["gerbers/board-F_Cu.gbr"]["layer"] == "F.Cu"


def test_manifest_has_no_entry_for_a_failed_view(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    fake = _fake(tmp_path, export_fail=("render",))
    args = ("render", str(root), "--out", "r", "--svg", "--png", "--manifest", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0 and len(env["issues"]) == 2
    assert sorted(_manifest(tmp_path / "r")) == ["back.svg", "front.svg"]


def test_manifest_unreadable_refuses_the_views(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, root: Path
) -> None:
    (tmp_path / "r").mkdir()
    (tmp_path / "r" / "fenolite-artifacts.json").write_text("{", encoding="utf-8")
    args = ("render", str(root), "--out", "r", "--svg", "--manifest", "--kicad-cli", _fake(tmp_path))
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["manifest.unreadable"]
    assert sorted(p.name for p in (tmp_path / "r").iterdir()) == ["fenolite-artifacts.json"]
    assert env["receipt"] is None
