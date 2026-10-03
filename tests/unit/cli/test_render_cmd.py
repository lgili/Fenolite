# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite render`` against the fake ``kicad-cli`` (capability cli-contract, "Render command";
manufacturing-exports, "Render views"; change c0024). Hermetic."""

from __future__ import annotations

import hashlib
from pathlib import Path

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
