# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The document exports on the running ``kicad-cli`` (``H-K-EXPORT-DOCS``, ``H-K-EXPORT-DOCS-REPEAT``,
``H-K-EXPORT-MODELS``, ``H-K-EXPORT-SHEETS``, ``H-K-EXPORT-PDF-PAGE``; capability kicad-oracle, "Document
exports are probed on both majors"; change c0116). Nothing is downloaded: the model is the authored box
of ``tests/data/models/``."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import _doccases
import _schema
import pytest
from _models import BOX, BOX_REL, MODELS, official, with_models
from _probes import major, run, runner
from _projects import SCHEMATICS, authored_project, built_blink_project, tree_snapshot

from fenolite.exports.manifest import content_sha256
from fenolite.exports.plan import DOCUMENT_KINDS, KINDS

pytestmark = pytest.mark.needs_kicad
ROOT = Path(__file__).resolve().parents[3]
BYTE_EQUAL = {"ipc2581": False, "odb": False, "step": False, "pdf": False, "dxf": True, "sch-pdf": False}
"""Whether three exports are byte-equal, per kind, as recorded in ``docs/evidence/kicad-export.md``."""
REPEAT = {"bytes": "equal", "content": "equal", "none": "different"}
"""``Kind.repeat`` → the outcome of ``export-repeat-<kind>`` (three runs compared by ``content_sha256``)."""
FLAGS = ("--ipc2581", "--odb", "--step", "--pdf", "--dxf", "--sch-pdf")


@pytest.mark.parametrize("kind", DOCUMENT_KINDS)
def test_files(kind: str) -> None:
    assert run(f"export-files-{kind}") == "equal"
    for subject in _doccases.subjects(kind):
        result = _doccases.exported(kind, subject)
        if major() >= 10:  # 10.0 also writes the local settings of the project, outside the kind's folder
            assert any(name.endswith(".kicad_prl") for name in result.tool_writes), result.tool_writes


@pytest.mark.parametrize("kind", DOCUMENT_KINDS)
def test_repeat(kind: str) -> None:
    entry = KINDS[kind]
    assert run(f"export-repeat-{kind}") == REPEAT[entry.repeat]
    assert _doccases.byte_equal(kind) is BYTE_EQUAL[kind]
    assert entry.repeatable is BYTE_EQUAL[kind]
    if entry.repeat == "content":  # nothing but the known date line differs between two runs
        unknown = _doccases.unknown_lines(kind)
        assert not unknown, (
            f"{kind}: lines that differ between two runs and are no known date line: {unknown}"
        )


def test_models() -> None:
    assert run("export-models-var") == "equal"
    assert run("export-models-missing") == "equal"
    assert run("export-models-subst") == "equal"
    # the lines that `models.unread_refs` reads, as kicad-cli prints them
    path = official(major=major())
    missing = _doccases.step_run(path, {}, env={_doccases.variable(): "3dmodels"})
    printed = [line.strip() for line in missing.stdout.splitlines()]
    assert missing.returncode == 0 and all(line in printed for line in _doccases.missing_lines(path))
    from fenolite.backends.kicad.models import unread_refs

    assert unread_refs(missing.stdout) == _doccases.REFS


def test_models_other_major_variable() -> None:
    """9.0 does not read a ``KICAD9_`` path through ``KICAD10_3DMODEL_DIR`` (``H-K-EXPORT-MODELS``); on
    10.0 the same holds for a ``KICAD10_`` path and ``KICAD9_3DMODEL_DIR``."""
    other = 10 if major() == 9 else 9
    path = official(major=major())
    found = _doccases.step_run(
        path, {f"3dmodels/{BOX_REL}": BOX}, env={f"KICAD{other}_3DMODEL_DIR": "3dmodels"}
    )
    if _doccases.install_has_model() and major() >= 10:
        pytest.skip("an install is present: kicad-cli 10 may fall back on it")
    assert found.returncode == 0 and _doccases.bodies(found) == []


@pytest.mark.kicad_min_major(10)
def test_models_install() -> None:
    """Recorded on 10.0.6 only: with no model variable in the run, the bodies of an official model come
    from the install of the running ``kicad-cli``, for a ``KICAD9_`` and a ``KICAD10_`` path. Not a pinned
    probe: the outcome depends on whether the machine has an install with models."""
    if not _doccases.install_has_model():
        pytest.skip("no KiCad install with 3D models on this machine")
    assert _doccases.models_install_bodies(10) == sorted(_doccases.REFS)
    assert _doccases.models_install_bodies(9) == sorted(_doccases.REFS)


def test_sheets() -> None:
    assert run("export-sheets-missing") == "present"
    assert _doccases.pages(_doccases.sheet_run(_doccases.hierarchy())) == 2  # one page per sheet instance


def test_page() -> None:
    outcome = run("export-pdf-page")
    box = _doccases.page_box()
    assert box is not None
    if major() >= 10:
        assert outcome == "equal", box
    else:  # recorded on 9.0: the probe file pins what was seen
        assert outcome in {"equal", "different"}, box


# --- the loop ---------------------------------------------------------------------------------------


def fenolite(cwd: Path, *args: str, env: dict[str, str] | None = None) -> tuple[int, dict[str, Any], str]:
    command = [sys.executable, "-m", "fenolite", *args, "--json"]
    environment = {**os.environ, **(env or {})}
    found = subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=900, check=False, env=environment
    )
    return found.returncode, json.loads(found.stdout) if found.stdout.strip() else {}, found.stderr


def _matches(folder: Path, manifest: dict[str, Any]) -> None:
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    written = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    assert written == sorted([*(e["path"] for e in manifest["artifacts"]), "fenolite-artifacts.json"])
    for entry in manifest["artifacts"]:
        data = (folder / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data) and entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["content_sha256"] == content_sha256(data, entry["kind"])
        assert entry["state"] == "generated" and entry["tool"] == f"kicad-cli {runner().version()}"


def test_document_loop(tmp_path: Path) -> None:
    """Scenario "The loop leaves the project as it was": the authored project, given the authored
    hierarchy as its schematic and the authored model for one of its footprints."""
    root = authored_project(tmp_path, major=major())
    folder = "hier" if major() >= 10 else "hier_v9"
    (root / "board.kicad_sch").write_bytes((SCHEMATICS / folder / "top.kicad_sch").read_bytes())
    (root / "child.kicad_sch").write_bytes((SCHEMATICS / folder / "child.kicad_sch").read_bytes())
    board = root / "board.kicad_pcb"
    text = board.read_text(encoding="utf-8")
    ref = next(
        line.split('"')[3] for line in text.splitlines() if line.strip().startswith('(property "Reference"')
    )
    path = official(major=major())
    board.write_text(with_models(text, {ref: path}), encoding="utf-8", newline="\n")
    before = tree_snapshot(root)
    empty = tmp_path / "config-home"
    empty.mkdir()
    env = {f"KICAD{major()}_3DMODEL_DIR": str(MODELS), "KICAD_CONFIG_HOME": str(empty)}
    code, envelope, err = fenolite(
        tmp_path, "export", str(root), "--out", "fab", *FLAGS, "--manifest", "--kicad-cli",
        str(runner().path), "--confirm", env=env,
    )  # fmt: skip
    assert code == 0, (envelope.get("issues"), err)
    fab = tmp_path / "fab"
    manifest = json.loads((fab / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    _matches(fab, manifest)
    kinds = {e["kind"] for e in manifest["artifacts"]}
    assert kinds == set(DOCUMENT_KINDS)
    paths = {e["path"] for e in manifest["artifacts"]}
    assert {"ipc2581/board.xml", "odb/board.zip", "3d/board.step", "schematic/board.pdf"} <= paths
    assert "pdf/board-F_Cu.pdf" in paths and "dxf/board-Edge_Cuts.dxf" in paths
    by_path = {e["path"]: e for e in manifest["artifacts"]}
    board_sha = hashlib.sha256(board.read_bytes()).hexdigest()
    sheet_sha = hashlib.sha256((root / "board.kicad_sch").read_bytes()).hexdigest()
    assert by_path["3d/board.step"]["from"] == {"board": board_sha}
    assert by_path["schematic/board.pdf"]["from"] == {"schematic": sheet_sha}
    assert by_path["pdf/board-F_Cu.pdf"]["layer"] == "F.Cu"
    result = envelope["result"]
    assert result["repeat"] == {kind: KINDS[kind].repeat for kind in DOCUMENT_KINDS}
    box = next(m for m in result["models"] if m["path"] == path)
    assert box["source"] in {"env", "project"} and box["refs"] == [ref]
    assert box["sha256"] == hashlib.sha256(BOX.read_bytes()).hexdigest()
    assert not any(i["severity"] == "error" for i in envelope["issues"])
    assert not any(i["code"] == "export.model-unread" for i in envelope["issues"])
    assert tree_snapshot(root) == before  # the project folder is as it was


def test_document_loop_of_the_built_blink(tmp_path: Path) -> None:
    """The same loop on the blink that ``build`` writes, with the schematic of that build."""
    root = built_blink_project(tmp_path / "blink", target=major())
    before = tree_snapshot(root)
    code, envelope, err = fenolite(
        tmp_path, "export", str(root), "--out", "docs", "--sch-pdf", "--pdf", "--manifest", "--kicad-cli",
        str(runner().path), "--confirm",
    )  # fmt: skip
    assert code == 0, (envelope.get("issues"), err)
    manifest = json.loads((tmp_path / "docs" / "fenolite-artifacts.json").read_text(encoding="utf-8"))
    _matches(tmp_path / "docs", manifest)
    assert {e["kind"] for e in manifest["artifacts"]} == {"pdf", "sch-pdf"}
    layers = {e["layer"] for e in manifest["artifacts"] if e["kind"] == "pdf"}
    assert {"F.Cu", "B.Cu", "Edge.Cuts"} <= layers and None not in layers
    assert tree_snapshot(root) == before


def test_step_of_the_official_blink(tmp_path: Path) -> None:
    """A STEP of ``examples/blink_official`` with its official models, taken from the install or from the
    fetched cache. Without either, the test skips and names the fetch command; nothing is downloaded."""
    empty = tmp_path / "config-home"
    empty.mkdir()
    env = {"KICAD_CONFIG_HOME": str(empty)}
    design = ROOT / "examples" / "blink_official" / "design.py"
    code, envelope, err = fenolite(
        tmp_path, "build", str(design), "--out", "official", "--kicad-version", str(major()), "--confirm",
        env=env,
    )  # fmt: skip
    if code != 0:
        pytest.skip("the official libraries are not on this machine: examples/blink_official does not build")
    board = tmp_path / "official" / "blink_official.kicad_pcb"
    code, listed, err = fenolite(tmp_path, "models", str(board), env=env)
    assert code == 0, err
    counts = listed["result"]["counts"]
    if counts["missing"]:
        pytest.skip(
            f"{counts['missing']} of {counts['paths']} official models are on no source of this machine: "
            f"run 'uv run python tools/kicad_libs_fetch.py --models <board>' with FENOLITE_LIBS_CACHE set"
        )
    code, envelope, err = fenolite(
        tmp_path, "export", str(board), "--out", "fab", "--step", "--kicad-cli", str(runner().path),
        "--confirm", env=env,
    )  # fmt: skip
    assert code == 0, (envelope.get("issues"), err)
    models = envelope["result"]["models"]
    assert models and all(m["source"] in {"install", "cache", "env", "kicad-config"} for m in models)
    assert not any(
        i["code"] in {"export.model-unread", "kicad.lib.missing-3d-model"} for i in envelope["issues"]
    )
    assert (tmp_path / "fab" / "3d" / "blink_official.step").stat().st_size > 8000
