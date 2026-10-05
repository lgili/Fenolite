# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite manifest`` on the built examples, against the running ``kicad-cli`` (capability
cli-contract, "Manifest command"; manufacturing-exports, "Artefact states" and "Project manifest";
change c0065).

The routed blink reaches ``native-verified`` for its board, because KiCad's DRC reports no error, and
``checked`` for the files made from it; the unrouted blink stops at ``roundtrip-ok``. The schematic is
an authored sheet put next to the board (``build`` writes none yet): it stops at ``roundtrip-ok`` on both
majors, because KiCad's ERC is not a stage of ``check`` before change c0062."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import _schema
import pytest
from _probes import major, runner
from _projects import tree_snapshot

pytestmark = pytest.mark.needs_kicad
ROOT = Path(__file__).resolve().parents[3]
ROUTED = ROOT / "examples" / "blink_routed" / "design.py"
UNROUTED = ROOT / "examples" / "blink_2layer" / "design.py"
SHEETS = {9: "flat_v9.kicad_sch", 10: "flat.kicad_sch"}
"""The authored flat schematic in the format of each major."""
STAMP = "2026-01-02T03:04:05+00:00"
NAME = "fenolite-artifacts.json"
ERC_HELD = "native-verified: erc.kicad is not a stage of this version of Fenolite"


def fenolite(cwd: Path, *args: str) -> tuple[int, dict[str, Any], str]:
    command = [sys.executable, "-m", "fenolite", *args, "--json"]
    run = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=900, check=False)
    return run.returncode, json.loads(run.stdout) if run.stdout.strip() else {}, run.stderr


def _built(work: Path, script: Path, name: str) -> Path:
    out = work / name
    code, _, err = fenolite(
        work, "build", str(script), "--out", str(out), "--kicad-version", str(major()), "--confirm"
    )
    assert code == 0, err
    return out


@pytest.fixture(scope="module")
def routed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The routed blink with exported files, views and a placement table in ``fab/``, and a schematic."""
    project = _built(tmp_path_factory.mktemp("manifest-routed"), ROUTED, "routed")
    (board,) = project.glob("*.kicad_pcb")
    sheet = ROOT / "tests" / "data" / "kicad" / "schematic" / SHEETS[major()]
    shutil.copyfile(sheet, project / f"{board.stem}.kicad_sch")
    cli = ("--kicad-cli", str(runner().path), "--confirm")
    for args in (
        ("export", str(project), "--out", "fab", "--all", "--manifest", *cli),
        ("render", str(project), "--out", "fab", "--svg", "--manifest", *cli),
        ("pnp", str(project), "--out", "fab/pnp.csv", "--manifest", "--confirm"),
    ):
        code, env, err = fenolite(project, *args)
        assert code == 0, (env.get("issues"), err)
    return project


def _manifest(project: Path, *flags: str) -> tuple[int, dict[str, Any], str]:
    cli = str(runner().path)
    return fenolite(
        project,
        "manifest",
        str(project),
        "--artifacts",
        "fab",
        "--kicad-cli",
        cli,
        "--timestamp",
        STAMP,
        *flags,
    )


def test_routed_blink_reaches_native_verified(routed: Path) -> None:
    (board,) = routed.glob("*.kicad_pcb")
    before = tree_snapshot(routed)
    code, env, err = _manifest(routed, "--dry-run")
    assert code == 0, (env.get("issues"), err)
    assert tree_snapshot(routed) == before  # KiCad only saw copies
    code, env, err = _manifest(routed, "--confirm")
    assert code == 0, (env.get("issues"), err)
    assert [w["path"] for w in env["receipt"]["written"]] == [NAME]
    text = (routed / NAME).read_text(encoding="utf-8")
    data = json.loads(text)
    assert _schema.validate(data, _schema.load("fenolite.artifacts.v0.json")) == []
    version = runner().version()
    assert data["tool"] == {"name": "kicad-cli", "version": version}
    assert data["check"]["tool_version"] == version and data["generated"] == STAMP
    stages = {s["name"]: s for s in data["check"]["stages"]}
    assert stages["drc.kicad"] == {
        "name": "drc.kicad", "status": "ok", "level": "KICAD-VERIFIED", "oracle": f"kicad-cli {version}",
    }  # fmt: skip
    for name in ("model.validate", "copper.clearance", "roundtrip"):
        assert stages[name]["status"] == "ok", name
    assert "erc.kicad" not in stages

    listed = {e["path"]: e for e in data["artifacts"]}
    for item in listed.values():
        file = routed / item["path"]
        assert item["sha256"] == hashlib.sha256(file.read_bytes()).hexdigest(), item["path"]
    top = listed[board.name]
    assert (top["state"], top["held"], top["stale"]) == ("native-verified", "", False)
    assert top["tool"] == f"fenolite {data['fenolite']}"  # the build record holds this hash
    for name in (f"{board.stem}.kicad_pro", "fp-lib-table"):
        assert listed[name]["state"] == "native-verified", name
    assert {e["state"] for e in data["artifacts"] if e["kind"] == "kicad_mod"} == {"native-verified"}
    sheet = listed[f"{board.stem}.kicad_sch"]
    assert (sheet["state"], sheet["held"], sheet["tool"]) == ("roundtrip-ok", ERC_HELD, None)
    assert data["project"]["schematic"]["sha256"] == sheet["sha256"]

    made = [e for e in data["artifacts"] if e["path"].startswith("fab/")]
    kinds = {e["kind"] for e in made}
    assert kinds == {"gerbers", "drill", "pos", "ipcd356", "render", "pnp"}
    for item in made:
        assert (item["state"], item["stale"], item["held"]) == ("checked", False, ""), item["path"]
        assert item["from"] == {"board": top["sha256"]}
        expected = "fenolite" if item["kind"] == "pnp" else f"kicad-cli {version}"
        assert item["tool"].startswith(expected), item["path"]
    assert data["states"]["generated"] == 0 and data["states"]["oracle-verified"] == 0
    assert data["states"]["roundtrip-ok"] == 1 and data["states"]["checked"] == len(made)
    assert env["result"]["states"] == data["states"]
    assert not [i for i in env["issues"] if i["severity"] == "error"]
    for needle in (str(routed.parent), str(Path.home()), "fenolite-kicad-"):
        assert needle not in text

    # a second run on unchanged files plans the same bytes
    code, env, err = _manifest(routed, "--dry-run")
    assert code == 0, err
    (plan,) = env["result"]["plan"]
    assert plan["sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_verify_passes_then_fails_after_an_edit(routed: Path) -> None:
    code, env, err = _manifest(routed, "--confirm", "--no-backup")
    assert code == 0, (env.get("issues"), err)
    before = tree_snapshot(routed)
    code, env, err = fenolite(routed.parent, "manifest", str(routed), "--verify")
    assert code == 0, (env.get("issues"), err)
    assert env["result"]["verified"] is True and env["result"]["differences"] == []
    assert tree_snapshot(routed) == before

    copy = routed.parent / "edited"
    shutil.copytree(routed, copy)
    gerber = next((copy / "fab" / "gerbers").glob("*-F_Cu.gbr"))
    gerber.write_bytes(gerber.read_bytes() + b"G04 edited*\n")
    code, env, _ = fenolite(copy.parent, "manifest", str(copy), "--verify")
    assert code == 5 and env["result"]["verified"] is False
    assert env["result"]["differences"] == [
        {"path": gerber.relative_to(copy).as_posix(), "code": "manifest.changed"}
    ]


def test_unrouted_blink_stops_at_roundtrip_ok(tmp_path_factory: pytest.TempPathFactory) -> None:
    project = _built(tmp_path_factory.mktemp("manifest-unrouted"), UNROUTED, "blink")
    (board,) = project.glob("*.kicad_pcb")
    code, env, _ = fenolite(
        project,
        "manifest",
        str(project),
        "--kicad-cli",
        str(runner().path),
        "--timestamp",
        STAMP,
        "--confirm",
    )
    assert code == 5  # KiCad reports the unconnected items, and the manifest is written all the same
    assert "kicad.drc.unconnected-items" in [i["code"] for i in env["issues"]]
    data = json.loads((project / NAME).read_text(encoding="utf-8"))
    listed = {e["path"]: e for e in data["artifacts"]}
    assert listed[board.name]["state"] == "roundtrip-ok"
    assert listed[board.name]["held"] == "native-verified: drc.kicad reported errors"
    assert data["states"]["native-verified"] == 0
    drc = next(s for s in data["check"]["stages"] if s["name"] == "drc.kicad")
    assert (drc["status"], drc["level"]) == ("errors", "KICAD-VERIFIED")
