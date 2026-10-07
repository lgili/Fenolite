# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output job of an Altium build (capability altium-build, "Output job in an Altium build"; changes
c0087 and c0138): the lens, the project file and the ``build`` options."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from _altium import blink_tree, sample
from _altium_job import blink_output, kept_project_issues

from fenolite.backends.altium import outjob
from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.read.outjob import read_outjob, record_fields
from fenolite.backends.altium.read.project import read_project
from fenolite.cli import main as cli_main
from fenolite.dsl import to_model
from fenolite.exports.preset import Preset, read_preset
from fenolite.lens.altium import build_altium, kept_documents

PROJECT_FILES = ("blink.PcbDoc", "blink.PcbLib", "blink.PrjPcb", "blink.SchDoc", "blink.SchLib")
KINDS = ["gerbers", "drill", "pos", "bom", "schematic_print", "pcb_print"]
JOB_HYPOTHESES = {
    "H-A-OUTJOB-GERBER-ACCEPT",
    "H-A-OUTJOB-GERBER-LAYERS",
    "H-A-OUTJOB-GERBER-RECORD",
    "H-A-OUTJOB-OPEN",
    "H-A-OUTJOB-READBACK",
    "H-A-OUTJOB-RUN-2",
}
"""What the evidence of a build with a job names (change c0138)."""
BLINK_LAYERS = [
    {"id": 16973830, "name": "Top Overlay"},
    {"id": 16973832, "name": "Top Paste"},
    {"id": 16973834, "name": "Top Solder"},
    {"id": 16777217, "name": "Top Layer"},
    {"id": 16842751, "name": "Bottom Layer"},
    {"id": 16973835, "name": "Bottom Solder"},
    {"id": 16973833, "name": "Bottom Paste"},
    {"id": 16973831, "name": "Bottom Overlay"},
    {"id": 16908301, "name": "Mechanical 13"},
    {"id": 16908302, "name": "Mechanical 14"},
    {"id": 16908303, "name": "Mechanical 15"},
    {"id": 16908304, "name": "Mechanical 16"},
]
"""``result.outjob.gerber.layers`` of the two-layer blink, in the order of the record's ``Plot.Set``."""
C0087_JOB_SHA256 = "e6ac379aeb0e508866b8c45e6bc1e6516da1e50a2b3cf9f6117e68a81051db9e"
"""The SHA-256 of ``blink.OutJob`` as a build before change c0138 wrote it (commit ``9aba2dff``; the
committed sample of change c0087 had these bytes)."""


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
    assert built.files["blink.OutJob"] == outjob.write_outjob(
        outjob.from_preset(Preset(), name="blink", copper=(1, 32))
    )
    assert JOB_HYPOTHESES <= set(built.evidence.hypotheses)
    assert "H-A-OUTJOB-RUN" not in built.evidence.hypotheses
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
    assert list(summary) == ["file", "media", "outputs", "gerber", "defaults"]
    preset = read_preset('schema = "fenolite.export-preset.v0"\n[pos]\nunits = "in"\n')
    assert blink_output(outjob=True, outjob_preset=preset).summary["outjob"]["defaults"] == ["pos.units"]  # type: ignore[index]


def test_gerber_record_of_the_built_job() -> None:
    """Scenarios "The Gerber record of the built job" and "The set holds no outline": the summary is what
    the written record holds, and no entry of it is the outline."""
    built = blink_output(outjob=True)
    gerber = built.summary["outjob"]["gerber"]  # type: ignore[index]
    assert list(gerber) == ["unit", "decimals", "layers", "outline"]
    assert gerber["unit"] == "Metric" and gerber["decimals"] == 4
    assert gerber["layers"] == BLINK_LAYERS
    assert gerber["outline"] == {"plotted": False, "reason": outjob.OUTLINE_REASON}
    assert list(gerber["outline"]) == ["plotted", "reason"]
    assert not [layer for layer in gerber["layers"] if "utline" in layer["name"] or "Keep" in layer["name"]]
    (group,) = read_outjob(built.files["blink.OutJob"]).groups
    assert [len(output.settings) for output in group.outputs] == [1, 0, 0, 0, 0, 0]
    fields = record_fields(group.outputs[0].settings[0].item)
    assert len(fields) == 44 and [name for name, _ in fields] == [f.name for f in outjob.GERBER_FIELDS]
    plot = dict(fields)["Plot.Set"]
    assert plot == outjob.LAYER_SET_HEAD + "".join(f",{layer['id']}~1" for layer in BLINK_LAYERS)
    section = read_outjob(built.files["blink.OutJob"]).ini.section("OutputGroup1")
    assert section is not None and [section.get(f"OutputDefault{i}") for i in range(1, 7)] == ["0"] * 6


def test_preset_precision_is_carried() -> None:
    """Scenario "The preset's precision is carried", for both values a preset allows."""
    for precision in (5, 6):
        preset = read_preset(f'schema = "fenolite.export-preset.v0"\n[gerbers]\nprecision = {precision}\n')
        built = blink_output(outjob=True, outjob_preset=preset)
        summary = built.summary["outjob"]
        assert summary["gerber"]["decimals"] == precision and summary["defaults"] == []  # type: ignore[index]
        (group,) = read_outjob(built.files["blink.OutJob"]).groups
        fields = record_fields(group.outputs[0].settings[0].item)
        assert [value for name, value in fields if name == "NumberOfDecimals"] == [str(precision)] * 2
    preset = read_preset('schema = "fenolite.export-preset.v0"\n[gerbers]\nlayers = ["F.Cu"]\n')
    summary = blink_output(outjob=True, outjob_preset=preset).summary["outjob"]
    assert summary["defaults"] == ["gerbers.layers"]  # type: ignore[index]
    assert summary["gerber"]["layers"] == BLINK_LAYERS  # type: ignore[index]


def test_only_the_job_changes() -> None:
    """Scenario "Only the job changes": against the build before change c0138 the job differs by eight
    inserted lines and by nothing else; every other file is the one of a build without a job, or, for the
    project file, unchanged by this change (it lists the job as before)."""
    lines = blink_output(outjob=True).files["blink.OutJob"].decode("ascii").split("\n")
    added = [line for line in lines if line.startswith(("OutputDefault", "Configuration"))]
    assert [line.partition("=")[0] for line in added] == [
        "OutputDefault1",
        "Configuration1_Name1",
        "Configuration1_Item1",
        *(f"OutputDefault{i}" for i in range(2, 7)),
    ]
    assert all(line == f"OutputDefault{n}=0" for n, line in enumerate(added[3:], start=2))
    before = "\n".join(line for line in lines if line not in added).encode("ascii")
    assert hashlib.sha256(before).hexdigest() == C0087_JOB_SHA256


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
    assert "delete blink.PrjPcb and build again" in found[0].hint


KEPT_CODES = {
    "altium.outjob-not-listed",
    "altium.pcb-not-in-project",
    "altium.project-kept",
    "altium.schlib-not-in-project",
    "altium.sheets-not-in-project",
}


def test_project_file_as_built_gains_the_job() -> None:
    """Change c0138: a project file that is as a build wrote it (``project_digest``) and does not list the
    job is written again, as a build into an empty folder writes it, and is then no kept file; one that
    was changed since (no digest) is kept and is not in the state the build writes; one that lists the
    job is kept, and stays in the state with its digest when it is as built."""
    fresh = blink_output(outjob=True)
    again = blink_output(outjob=True, project_exists=True, project_digest="ab" * 32)
    assert again.files["blink.PrjPcb"] == fresh.files["blink.PrjPcb"]
    assert again.summary["kept"] == [] and not {i.code for i in again.issues} & KEPT_CODES
    assert again.files == fresh.files and [i.code for i in again.issues] == [i.code for i in fresh.issues]
    assert "blink.PrjPcb" in json.loads(again.files[".fenolite/build.json"])["files"]

    edited = blink_output(outjob=True, project_exists=True)
    assert "blink.PrjPcb" not in edited.files and edited.summary["kept"] == ["blink.PrjPcb"]
    assert {"altium.outjob-not-listed", "altium.project-kept"} <= {i.code for i in edited.issues}
    assert "blink.PrjPcb" not in json.loads(edited.files[".fenolite/build.json"])["files"]

    listed = blink_output(outjob=True, project_exists=True, outjob_listed=True, project_digest="cd" * 32)
    assert "blink.PrjPcb" not in listed.files and listed.summary["kept"] == ["blink.PrjPcb"]
    assert "altium.project-kept" in {i.code for i in listed.issues}
    record = json.loads(listed.files[".fenolite/build.json"])["files"]
    assert record["blink.PrjPcb"] == "cd" * 32 and list(record) == sorted(record)
    changed = blink_output(outjob=True, project_exists=True, outjob_listed=True)
    assert "blink.PrjPcb" not in json.loads(changed.files[".fenolite/build.json"])["files"]

    # without a job nothing is added, so the file is kept, and the state keeps knowing it
    plain = blink_output(project_exists=True, project_digest="ef" * 32)
    assert "blink.PrjPcb" not in plain.files and plain.summary["kept"] == ["blink.PrjPcb"]
    assert json.loads(plain.files[".fenolite/build.json"])["files"]["blink.PrjPcb"] == "ef" * 32


def test_kept_project_infos_name_what_the_file_lacks() -> None:
    """The infos about a kept project file name only the documents it does not list (change c0138): none
    for a file that lists everything, exactly the one about the PCB files for a file that lacks the PCB
    document, every one when nothing is known of the file, with a hint when it could not be read."""
    everything = kept_documents(
        ["blink.SchDoc", "BLINK.PcbDoc", "blink.OutJob", "blink.PcbLib", "blink.SchLib"]
    )
    built = blink_output(outjob=True, project_exists=True, project_listed=everything)
    assert {i.code for i in built.issues} & KEPT_CODES == {"altium.project-kept"}
    assert built.summary["kept"] == ["blink.PrjPcb"] and "blink.PrjPcb" not in built.files

    without_pcb = everything - {"blink.pcbdoc"}
    built = blink_output(outjob=True, project_exists=True, project_listed=without_pcb)
    assert {i.code for i in built.issues} & KEPT_CODES == {"altium.project-kept", "altium.pcb-not-in-project"}
    (found,) = [i for i in built.issues if i.code == "altium.pcb-not-in-project"]
    assert "blink.PcbDoc" in found.message and "blink.PcbLib" not in found.message and found.hint == ""

    unknown = blink_output(outjob=True, project_exists=True)
    assert {i.code for i in unknown.issues} & KEPT_CODES == {
        "altium.outjob-not-listed",
        "altium.pcb-not-in-project",
        "altium.project-kept",
        "altium.schlib-not-in-project",
    }
    assert not [i for i in unknown.issues if "could not be read" in i.hint]
    unread = blink_output(outjob=True, project_exists=True, project_unreadable=True)
    hints = {i.code: i.hint for i in unread.issues if i.code in KEPT_CODES}
    assert "could not be read" in hints["altium.pcb-not-in-project"]
    assert "could not be read" in hints["altium.schlib-not-in-project"]
    assert kept_documents(["Sub\\A.SchDoc"]) == frozenset({"sub/a.schdoc"})


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
    assert JOB_HYPOTHESES <= set(env["evidence"]["hypotheses"])
    assert list(result["outjob"]) == ["file", "media", "outputs", "gerber", "defaults", "preset"]
    gerber = result["outjob"]["gerber"]
    assert list(gerber) == ["unit", "decimals", "layers", "outline"]
    assert (gerber["unit"], gerber["decimals"], gerber["layers"]) == ("Metric", 4, BLINK_LAYERS)
    assert gerber["outline"] == {"plotted": False, "reason": outjob.OUTLINE_REASON}
    assert len(group.outputs[0].settings) == 1 and not any(o.settings for o in group.outputs[1:])

    off = tmp_path / "off"
    args = [str(blink_script), "--out", str(off), "--target", "altium", "--confirm", "--altium-outjob", "off"]
    code, env, err = run(monkeypatch, *args)
    assert code == 0, err
    assert env["result"]["outjob"] is None and not (off / "blink.OutJob").exists()
    for name in ("blink.SchDoc", "blink.PcbDoc", "blink.PcbLib", "blink.SchLib"):
        assert (off / name).read_bytes() == (out / name).read_bytes(), name
    project = (off / "blink.PrjPcb").read_bytes()
    assert b"OutJob" not in project

    # The project file of the build without a job is as that build wrote it (the state records it): the
    # next build adds the job to it, by writing it again as the first build of `out` wrote it, and keeps
    # the old file as a backup. This is the folder a build of 0.2.x leaves (case a of the design).
    code, env, err = run(monkeypatch, str(blink_script), "--out", str(off), "--target", "altium", "--confirm")
    assert code == 0, err
    assert (off / "blink.OutJob").is_file()
    assert (off / "blink.PrjPcb").read_bytes() == (out / "blink.PrjPcb").read_bytes()
    assert (off / "blink.PrjPcb.bak").read_bytes() == project
    documents = [d.path for d in read_project((off / "blink.PrjPcb").read_bytes()).documents]
    assert documents == ["blink.SchDoc", "blink.PcbDoc", "blink.OutJob", "blink.PcbLib", "blink.SchLib"]
    assert str(off / "blink.PrjPcb") in env["result"]["files"] and env["result"]["kept"] == []
    assert not {i["code"] for i in env["issues"]} & KEPT_CODES

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


def test_changed_project_file_is_not_rewritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path
) -> None:
    """A project file without the job that was changed since the build (as when Altium saved it), or that
    the folder's state does not record, is kept as before, whatever ``--discard-layout``: the build says
    that it does not list the job and how to get it listed."""
    base = [str(blink_script), "--target", "altium", "--confirm"]
    edited = tmp_path / "edited"
    assert run(monkeypatch, *base, "--out", str(edited), "--altium-outjob", "off")[0] == 0
    project = edited / "blink.PrjPcb"
    changed = project.read_bytes() + b"; saved by hand\r\n"
    project.write_bytes(changed)
    for extra in ((), ("--discard-layout",)):
        code, env, err = run(monkeypatch, *base, "--out", str(edited), *extra)
        assert code == 0, err
        assert project.read_bytes() == changed and not (edited / "blink.PrjPcb.bak").exists()
        assert env["result"]["kept"] == [str(project)] and (edited / "blink.OutJob").is_file()
        (found,) = [i for i in env["issues"] if i["code"] == "altium.outjob-not-listed"]
        assert "Add Existing to Project" in found["message"] and "delete blink.PrjPcb" in found["hint"]

    lost = tmp_path / "lost"
    assert run(monkeypatch, *base, "--out", str(lost), "--altium-outjob", "off")[0] == 0
    before = (lost / "blink.PrjPcb").read_bytes()
    shutil.rmtree(lost / ".fenolite")
    code, env, err = run(monkeypatch, *base, "--out", str(lost))
    assert code == 0, err
    assert (lost / "blink.PrjPcb").read_bytes() == before and not (lost / "blink.PrjPcb.bak").exists()
    assert "altium.outjob-not-listed" in {i["code"] for i in env["issues"]}


def test_kept_project_file_stays_known(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path
) -> None:
    """The first situation that the record of a kept project file closes (design of c0138, "Found on
    2026-10-07 (implementation)", 12): two builds with ``--altium-outjob off`` and then one with the job.
    The second build keeps the project file and records it again, because its bytes are the recorded ones,
    so the third still knows it as built: the job gets listed, and ``blink.PrjPcb.bak`` holds the old
    file. A kept file that lists everything gives no info about what it lacks."""
    out = tmp_path / "out"
    base = [str(blink_script), "--out", str(out), "--target", "altium", "--confirm"]
    project = out / "blink.PrjPcb"
    for _ in range(2):
        code, env, err = run(monkeypatch, *base, "--altium-outjob", "off")
        assert code == 0, err
    assert env["result"]["kept"] == [str(project)] and str(project) not in env["result"]["files"]
    assert str(project) not in json.dumps(env.get("receipt"))
    assert {i["code"] for i in env["issues"]} & KEPT_CODES == {"altium.project-kept"}
    before = project.read_bytes()
    record = json.loads((out / ".fenolite" / "build.json").read_text(encoding="utf-8"))["files"]
    assert record["blink.PrjPcb"] == hashlib.sha256(before).hexdigest()
    code, env, err = run(monkeypatch, *base)
    assert code == 0, err
    assert b"blink.OutJob" in project.read_bytes() and env["result"]["kept"] == []
    assert (out / "blink.PrjPcb.bak").read_bytes() == before
    assert str(project) in json.dumps(env.get("receipt"))


def test_folder_whose_state_lost_the_project_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path
) -> None:
    """The second situation: a folder that a build before change c0138 rebuilt once, whose state holds
    every file but the kept project file. Nothing records the project file, so the build cannot know it
    as built and keeps it (recording it now would turn any edited file into one "as built"): the info and
    its hint say how to get the job listed, and deleting the project file does it."""
    out = tmp_path / "out"
    base = [str(blink_script), "--out", str(out), "--target", "altium", "--confirm"]
    assert run(monkeypatch, *base, "--altium-outjob", "off")[0] == 0
    state = out / ".fenolite" / "build.json"
    record = json.loads(state.read_text(encoding="utf-8"))
    del record["files"]["blink.PrjPcb"]
    state.write_text(json.dumps(record), encoding="utf-8", newline="\n")
    project = out / "blink.PrjPcb"
    before = project.read_bytes()
    for _ in range(2):
        code, env, err = run(monkeypatch, *base)
        assert code == 0, err
        assert project.read_bytes() == before and not (out / "blink.PrjPcb.bak").exists()
        assert {i["code"] for i in env["issues"]} & KEPT_CODES == {
            "altium.outjob-not-listed",
            "altium.project-kept",
        }
        assert "blink.PrjPcb" not in json.loads(state.read_text(encoding="utf-8"))["files"]
    project.unlink()
    code, env, err = run(monkeypatch, *base)
    assert code == 0, err
    assert b"blink.OutJob" in project.read_bytes() and env["result"]["kept"] == []


def _c0087_job(job: bytes) -> bytes:
    """The job a build before change c0138 wrote: ``job`` without its eight added lines."""
    lines = job.decode("ascii").split("\n")
    old = "\n".join(line for line in lines if not line.startswith(("OutputDefault", "Configuration")))
    data = old.encode("ascii")
    assert hashlib.sha256(data).hexdigest() == C0087_JOB_SHA256
    return data


def test_job_of_an_earlier_build_is_replaced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path
) -> None:
    """Two builds into one folder whose jobs differ (change c0138 changes the bytes of every job): the
    job that the folder's state records is replaced, with the old bytes in ``blink.OutJob.bak``, as every
    other planned file is. Measured with real builds of the commit before this change on 2026-10-07; here
    the earlier build is a build with another preset, and then the job and the state of a build of c0087."""
    out = tmp_path / "out"
    args = [str(blink_script), "--out", str(out), "--target", "altium", "--confirm"]
    job, backup, state = out / "blink.OutJob", out / "blink.OutJob.bak", out / ".fenolite" / "build.json"
    six = tmp_path / "six.toml"
    six.write_text('schema = "fenolite.export-preset.v0"\n[gerbers]\nprecision = 6\n', encoding="utf-8")
    code, _env, err = run(monkeypatch, *args, "--altium-outjob-preset", str(six))
    assert code == 0, err
    first = job.read_bytes()
    assert b"NumberOfDecimals=6" in first and not backup.exists()
    code, env, err = run(monkeypatch, *args)
    assert code == 0, err
    new = job.read_bytes()
    assert new != first and b"NumberOfDecimals=4" in new and backup.read_bytes() == first
    assert env["result"]["outjob"]["gerber"]["decimals"] == 4

    # the folder of a build of change c0087: its job, and a state that records that job's digest
    old = _c0087_job(new)
    job.write_bytes(old)
    record = json.loads(state.read_text(encoding="utf-8"))
    assert record["files"]["blink.OutJob"] == hashlib.sha256(new).hexdigest()
    record["files"]["blink.OutJob"] = C0087_JOB_SHA256
    state.write_text(json.dumps(record), encoding="utf-8", newline="\n")
    code, env, err = run(monkeypatch, *args)
    assert code == 0, err
    assert job.read_bytes() == new and backup.read_bytes() == old
    assert json.loads(state.read_text(encoding="utf-8"))["files"]["blink.OutJob"] == (
        hashlib.sha256(new).hexdigest()
    )


def test_job_without_its_state_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, blink_script: Path
) -> None:
    """Where a refusal remains: a job that differs from the one the build writes and that no state
    records (the ``.fenolite`` folder is lost), which the build cannot tell from an edited one. Exit 7,
    ``FEN-7001``, nothing written; the hint names ``--discard-layout``, which replaces it with a backup.
    The other files of the folder have the bytes the build writes and are not named."""
    out = tmp_path / "out"
    args = [str(blink_script), "--out", str(out), "--target", "altium", "--confirm"]
    assert run(monkeypatch, *args)[0] == 0
    job, backup = out / "blink.OutJob", out / "blink.OutJob.bak"
    new = job.read_bytes()
    old = _c0087_job(new)
    job.write_bytes(old)
    shutil.rmtree(out / ".fenolite")
    code, _env, err = run(monkeypatch, *args)
    assert code == 7 and "FEN-7001" in err and "blink.OutJob" in err and "--discard-layout" in err
    assert "blink.PcbDoc" not in err and "blink.SchDoc" not in err
    assert job.read_bytes() == old and not backup.exists() and not (out / ".fenolite").exists()
    code, _env, err = run(monkeypatch, *args, "--discard-layout")
    assert code == 0, err
    assert job.read_bytes() == new and backup.read_bytes() == old


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
    assert env["result"]["outjob"]["gerber"]["decimals"] == 4
    six = tmp_path / "six.toml"
    six.write_text('schema = "fenolite.export-preset.v0"\n[gerbers]\nprecision = 6\n', encoding="utf-8")
    code, env, err = run(monkeypatch, *base, "--altium-outjob-preset", str(six))
    assert code == 0, err
    assert env["result"]["outjob"]["gerber"]["decimals"] == 6 and env["result"]["outjob"]["defaults"] == []
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
