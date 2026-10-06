# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output job of an Altium build (capability altium-build, "Output job in an Altium build"; change
c0087): the lens, the project file and the ``build`` options."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from _altium import blink_tree, sample
from _altium_job import blink_output, kept_project_issues

from fenolite.backends.altium import outjob
from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.read.outjob import read_outjob
from fenolite.backends.altium.read.project import read_project
from fenolite.cli import main as cli_main
from fenolite.dsl import to_model
from fenolite.exports.preset import Preset, read_preset
from fenolite.lens.altium import build_altium

PROJECT_FILES = ("blink.PcbDoc", "blink.PcbLib", "blink.PrjPcb", "blink.SchDoc", "blink.SchLib")
KINDS = ["gerbers", "drill", "pos", "bom", "schematic_print", "pcb_print"]


def _project(files: dict[str, bytes]) -> set[str]:
    return {name for name in files if not name.startswith(".fenolite/")}


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


@pytest.fixture
def blink_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The blink script in a copy of its folder with the mini libraries, and no KiCad install in sight."""
    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in ("KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)
    return blink_tree(tmp_path / "tree") / "design.py"


def test_files_of_the_sample_with_a_job() -> None:
    """Scenario "Files of the sample with a job": one more file, listed after the PCB document."""
    plain, built = blink_output(), blink_output(outjob=True)
    assert _project(built.files) == {*PROJECT_FILES, "blink.OutJob"}
    assert _project(plain.files) == set(PROJECT_FILES) and plain.summary["outjob"] is None
    for name in PROJECT_FILES:
        if name != "blink.PrjPcb":
            assert built.files[name] == plain.files[name], name
    record = json.loads(built.files[".fenolite/build.json"])
    assert set(record["files"]) == {*PROJECT_FILES, "blink.OutJob"}
    assert record["files"]["blink.OutJob"] == hashlib.sha256(built.files["blink.OutJob"]).hexdigest()
    documents = [d.path for d in read_project(built.files["blink.PrjPcb"]).documents]
    assert documents == ["blink.SchDoc", "blink.PcbDoc", "blink.OutJob", "blink.PcbLib", "blink.SchLib"]
    assert built.files["blink.OutJob"] == outjob.write_outjob(outjob.from_preset(Preset(), name="blink"))
    assert {"H-A-OUTJOB-OPEN", "H-A-OUTJOB-READBACK", "H-A-OUTJOB-RUN"} <= set(built.evidence.hypotheses)
    assert not {"H-A-OUTJOB-OPEN"} & set(plain.evidence.hypotheses)
    assert not [i for i in built.issues if i.code == "altium.outjob-not-listed"]


def test_summary() -> None:
    summary = blink_output(outjob=True).summary["outjob"]
    assert isinstance(summary, dict)
    assert summary["file"] == "blink.OutJob" and summary["defaults"] == []
    assert summary["media"] == [{"name": "fab", "type": "GeneratedFiles"}, {"name": "doc", "type": "Publish"}]
    outputs = summary["outputs"]
    assert [o["kind"] for o in outputs] == KINDS and all(o["enabled"] for o in outputs)
    assert outputs[0] == {
        "kind": "gerbers",
        "type": "Gerber",
        "name": "Gerber Files",
        "category": "Fabrication",
        "document": "blink.PcbDoc",
        "enabled": True,
        "medium": "fab",
    }
    assert [o["medium"] for o in outputs] == ["fab", "fab", "fab", "fab", "doc", "doc"]
    preset = read_preset('schema = "fenolite.export-preset.v0"\n[pos]\nunits = "in"\n')
    assert blink_output(outjob=True, outjob_preset=preset).summary["outjob"]["defaults"] == ["pos.units"]  # type: ignore[index]


def test_no_job_without_a_pcb_document() -> None:
    """The sample has no footprint and no PCB document: no job, whatever the option says."""
    design = sample()
    built = build_altium(to_model(design), name=design.name, outjob=True)
    assert built.summary["pcb_document"] is None and built.summary["outjob"] is None
    assert not [name for name in built.files if name.endswith(".OutJob")]


def test_kept_project_file() -> None:
    """A kept project file that does not list the job gives the info; one that lists it gives none."""
    found = [i for i in kept_project_issues() if i.code == "altium.outjob-not-listed"]
    assert len(found) == 1 and found[0].severity == "info" and found[0].where == "blink.PrjPcb"
    built = blink_output(outjob=True, project_exists=True, outjob_listed=True)
    assert not [i for i in built.issues if i.code == "altium.outjob-not-listed"]
    assert "blink.PrjPcb" not in built.files and "blink.OutJob" in built.files


def test_project_file_bytes() -> None:
    """Without a job the project file keeps its bytes; with one it gains one section."""
    plain = write_prjpcb(schematic="a.SchDoc", pcb="a.PcbDoc", libraries=("a.PcbLib",))
    listed = write_prjpcb(schematic="a.SchDoc", pcb="a.PcbDoc", libraries=("a.PcbLib",), outjob="a.OutJob")
    assert write_prjpcb(schematic="a.SchDoc", pcb="a.PcbDoc", libraries=("a.PcbLib",), outjob=None) == plain
    assert listed == plain.replace(
        b"[Document3]\r\nDocumentPath=a.PcbLib\r\n",
        b"[Document3]\r\nDocumentPath=a.OutJob\r\n\r\n[Document4]\r\nDocumentPath=a.PcbLib\r\n",
    )
    with pytest.raises(ValueError, match="output job"):
        write_prjpcb(schematic="a.SchDoc", outjob="sub/a.OutJob")


# --- the build command ----------------------------------------------------------------------------------


def test_job_beside_the_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path) -> None:
    """Scenarios "Job beside the board", "Turned off" and "Kept project file"."""
    out = tmp_path / "out"
    code, env, err = run(monkeypatch, str(blink_script), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0, err
    result = env["result"]
    job = out / "blink.OutJob"
    assert job.is_file() and result["outjob"]["file"] == str(out / "blink.OutJob")
    assert result["outjob"]["preset"] is None and result["outjob"]["defaults"] == []
    assert [o["kind"] for o in result["outjob"]["outputs"]] == KINDS
    assert all(o["enabled"] for o in result["outjob"]["outputs"])
    documents = [d.path for d in read_project((out / "blink.PrjPcb").read_bytes()).documents]
    assert documents.index("blink.OutJob") == documents.index("blink.PcbDoc") + 1
    (group,) = read_outjob(job.read_bytes()).groups
    assert len(group.outputs) == 6 and len(group.media) == 2
    assert {"H-A-OUTJOB-OPEN", "H-A-OUTJOB-READBACK", "H-A-OUTJOB-RUN"} <= set(env["evidence"]["hypotheses"])

    off = tmp_path / "off"
    args = [str(blink_script), "--out", str(off), "--target", "altium", "--confirm", "--altium-outjob", "off"]
    code, env, err = run(monkeypatch, *args)
    assert code == 0, err
    assert env["result"]["outjob"] is None and not (off / "blink.OutJob").exists()
    for name in ("blink.SchDoc", "blink.PcbDoc", "blink.PcbLib", "blink.SchLib"):
        assert (off / name).read_bytes() == (out / name).read_bytes(), name
    project = (off / "blink.PrjPcb").read_bytes()
    assert b"OutJob" not in project

    # the kept project file of the build without a job does not list the job of the next build
    code, env, err = run(monkeypatch, str(blink_script), "--out", str(off), "--target", "altium", "--confirm")
    assert code == 0, err
    assert (off / "blink.PrjPcb").read_bytes() == project and (off / "blink.OutJob").is_file()
    assert "altium.outjob-not-listed" in {i["code"] for i in env["issues"]}

    # the project file of the first build lists it: a second build there reports nothing
    code, env, err = run(monkeypatch, str(blink_script), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0, err
    assert "altium.outjob-not-listed" not in {i["code"] for i in env["issues"]}


def test_edited_job_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path) -> None:
    """An output job that was edited since the build is refused like every other planned file."""
    out = tmp_path / "out"
    args = [str(blink_script), "--out", str(out), "--target", "altium", "--confirm"]
    assert run(monkeypatch, *args)[0] == 0
    job = out / "blink.OutJob"
    job.write_bytes(job.read_bytes().replace(b"Name=blink.OutJob", b"Name=edited"))
    code, _env, err = run(monkeypatch, *args)
    assert code != 0 and "blink.OutJob" in err
    assert b"Name=edited" in job.read_bytes()


def test_preset_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path) -> None:
    """Scenario "A preset names what the job does not set", and a preset that cannot be read."""
    preset = tmp_path / "fab.toml"
    preset.write_text('schema = "fenolite.export-preset.v0"\n[drill]\nunits = "in"\n', encoding="utf-8")
    base = [str(blink_script), "--out", str(tmp_path / "out"), "--target", "altium", "--dry-run"]
    code, env, err = run(monkeypatch, *base, "--altium-outjob-preset", str(preset))
    assert code == 0, err
    assert env["result"]["outjob"]["defaults"] == ["drill.units"]
    kinds = {Path(p["path"]).name: p["kind"] for p in env["result"]["plan"]}
    assert kinds["blink.OutJob"] == "altium_outjob"
    assert env["result"]["outjob"]["preset"] == {
        "file": str(preset),
        "sha256": hashlib.sha256(preset.read_bytes()).hexdigest(),
    }
    code, _env, err = run(monkeypatch, *base, "--altium-outjob-preset", str(tmp_path / "missing.toml"))
    assert code == 3 and "FEN-3001" in err
    preset.write_text('schema = "other"\n', encoding="utf-8")
    code, _env, err = run(monkeypatch, *base, "--altium-outjob-preset", str(preset))
    assert code == 3


@pytest.mark.parametrize(
    "extra",
    [
        ["--altium-outjob", "on"],
        ["--altium-outjob-preset", "x.toml"],
        ["--target", "altium", "--altium-outjob", "off", "--altium-outjob-preset", "x.toml"],
    ],
)
def test_usage_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path, extra: list[str]
) -> None:
    code, _env, err = run(monkeypatch, str(blink_script), "--out", str(tmp_path / "out"), "--dry-run", *extra)
    assert code == 2 and "FEN-2001" in err
