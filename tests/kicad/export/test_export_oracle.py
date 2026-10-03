# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export`` and ``fenolite render`` on the built blink, against the running ``kicad-cli``
(capability kicad-oracle, "Exports are probed on both majors", scenario "Blink exports on both majors";
change c0024)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import _schema
import pytest
from _probes import major, runner
from _projects import tree_snapshot

from fenolite.backends.kicad.plot import png_size
from fenolite.exports.manifest import content_sha256
from fenolite.exports.plan import KINDS

pytestmark = pytest.mark.needs_kicad
DESIGN = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"
STAMP = "2026-01-02T03:04:05+00:00"


def fenolite(cwd: Path, *args: str) -> tuple[int, dict[str, Any], str]:
    command = [sys.executable, "-m", "fenolite", *args, "--json"]
    run = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=900, check=False)
    return run.returncode, json.loads(run.stdout) if run.stdout.strip() else {}, run.stderr


@pytest.fixture(scope="module")
def blink(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("export-blink")
    out = work / "blink"
    code, _, err = fenolite(
        work, "build", str(DESIGN), "--out", str(out), "--kicad-version", str(major()), "--confirm"
    )
    assert code == 0, err
    return out


def export(blink: Path, out: str) -> tuple[dict[str, Any], dict[str, Any]]:
    cli = str(runner().path)
    code, env, err = fenolite(
        blink.parent, "export", str(blink), "--out", out, "--all", "--manifest", "--kicad-cli", cli,
        "--timestamp", STAMP, "--confirm",
    )  # fmt: skip
    assert code == 0, (env.get("issues"), err)
    manifest = json.loads((blink.parent / out / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    return env, manifest


def test_blink_loop(blink: Path) -> None:
    before = tree_snapshot(blink)
    env, manifest = export(blink, "fab")
    fab = blink.parent / "fab"
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    written = sorted(p.relative_to(fab).as_posix() for p in fab.rglob("*") if p.is_file())
    listed = [e["path"] for e in manifest["artifacts"]]
    assert written == sorted([*listed, "fenolite-artifacts.json"])
    assert {e["kind"] for e in manifest["artifacts"]} == set(KINDS)
    for entry in manifest["artifacts"]:
        data = (fab / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data) and entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["content_sha256"] == content_sha256(data, entry["kind"])
    gerbers = {e["layer"] for e in manifest["artifacts"] if e["kind"] == "gerbers" and e["layer"]}
    assert {"F.Cu", "B.Cu", "Edge.Cuts"} <= gerbers
    board = next(blink.glob("*.kicad_pcb"))
    assert manifest["board"]["path"] == board.name
    assert manifest["board"]["sha256"] == hashlib.sha256(board.read_bytes()).hexdigest()
    assert manifest["tool"]["version"] == runner().version()
    assert env["evidence"]["oracle"] == f"kicad-cli {runner().version()}"

    cli = str(runner().path)
    code, env, err = fenolite(
        blink.parent, "render", str(blink), "--out", "views", "--svg", "--png", "--width", "400",
        "--height", "300", "--kicad-cli", cli, "--confirm",
    )  # fmt: skip
    assert code == 0, err
    assert env["issues"] == [], env["issues"]
    views = blink.parent / "views"
    assert sorted(p.name for p in views.iterdir()) == ["back.svg", "bottom.png", "front.svg", "top.png"]
    size = png_size((views / "top.png").read_bytes())
    assert size is not None and 0 < size[0] <= 400 and 0 < size[1] <= 300
    assert b"<svg" in (views / "front.svg").read_bytes()
    assert tree_snapshot(blink) == before


def test_two_exports_differ_only_in_dated_files(blink: Path) -> None:
    """With one ``--timestamp``, two manifests are equal except ``sha256`` of the kinds KiCad dates."""
    _, first = export(blink, "fab-a")
    _, second = export(blink, "fab-b")
    assert first["generated"] == second["generated"] == STAMP

    def stable(manifest: dict[str, Any]) -> dict[str, Any]:
        entries = [
            {k: v for k, v in e.items() if KINDS[e["kind"]].repeatable or k not in ("sha256", "bytes")}
            for e in manifest["artifacts"]
        ]
        return {**manifest, "artifacts": entries}

    assert stable(first) == stable(second)
    assert [e["content_sha256"] for e in first["artifacts"]] == [
        e["content_sha256"] for e in second["artifacts"]
    ]


def test_render_stage_of_check(blink: Path) -> None:
    before = tree_snapshot(blink)
    code, env, err = fenolite(
        blink, "check", str(blink), "--stages", "render", "--kicad-cli", str(runner().path)
    )
    assert code == 0, err
    (stage,) = env["result"]["stages"]
    assert stage["status"] == "ok" and len(stage["summary"]["views"]) == 4 and env["issues"] == []
    assert tree_snapshot(blink) == before
