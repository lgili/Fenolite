# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's ERC as an oracle of ``check``, on the running major (capability kicad-oracle, "ERC facts proved
per major", the copy set; verification-loop, "ERC stage"; ``H-K-ERC-COPYSET``; change c0062)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import _erccases as cases
import _schprojects
import pytest
from _checkrun import check, stage, without_elapsed
from _probes import major, run, version
from _projects import built_blink_project, hierarchy_project, tree_snapshot

from fenolite.backends.kicad import erc as ercmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad.projectset import project_set
from fenolite.core.evidence import Evidence

pytestmark = pytest.mark.needs_kicad
CORPUS_PROJECTS = 3


def test_copy_set() -> None:
    """ERC on the copy set gives the entries of ERC on a copy of the whole folder, for the built blink and
    the authored hierarchy, each with files the run must not need."""
    assert run("erc-copyset") == "equal"
    for root, sheet in cases.copyset_roots():
        project = project_set(root / f"{Path(sheet).stem}.kicad_pcb")
        assert sheet in project.files
        assert not {"notes.txt", "unrelated.kicad_sch", "unnamed.kicad_sym"} & set(project.files)
        assert not [name for name in project.files if name.endswith(".kicad_prl")]
        assert [p.name for p in root.glob("*.kicad_prl")], "the decoy settings file KiCad wrote"


@pytest.mark.needs_corpus
def test_copy_set_corpus_projects(tmp_path: Path) -> None:
    """The same on the first three corpus projects of the acceptance list that the running major loads."""
    chosen = [
        row
        for row in _schprojects.roots(major())
        if _schprojects.acceptance(row) and row.file.is_file() and _schprojects.loadable(row, major())
    ][:CORPUS_PROJECTS]
    if len(chosen) < CORPUS_PROJECTS:
        pytest.skip("fewer than three corpus projects of the acceptance list are cached")
    for row in chosen:
        root = _schprojects.project_folder(tmp_path, row, major())
        assert root is not None
        sheet = Path(row.path).name
        assert cases.copyset_of(root, sheet) == "equal", row.id


# -- the stage through ``fenolite check`` (verification-loop, "ERC stage")


def _blink(tmp_path: Path, name: str = "blink") -> Path:
    return built_blink_project(tmp_path / name, target=major())


def _edit(root: Path, files: dict[str, bytes], *names: str) -> None:
    for name in names:
        (root / name).write_bytes(files[name])


def test_stage_clean_built_project(tmp_path: Path) -> None:
    root = _blink(tmp_path)
    before = tree_snapshot(root)
    code, env, _, err = check(root, "--stages", "erc.kicad")
    assert code == 0, err or env.get("issues")
    erc = stage(env, "erc.kicad")
    assert erc["status"] == "ok" and erc["summary"]["violations"] == 0 and erc["summary"]["sheets"] == 1
    assert erc["evidence"]["oracle"] == f"kicad-cli {version()}"
    combined = Evidence.combine(ercmod.EVIDENCE, oraclemod.EVIDENCE)
    assert erc["evidence"]["level"] == combined.level.value
    assert env["issues"] == [] and env["result"]["project"]["built"] is True
    assert {"blink.kicad_sch", "sym-lib-table", "lib/Mini.kicad_sym"} <= set(
        env["result"]["project"]["files"]
    )
    assert tree_snapshot(root) == before


def test_stage_unconnected_pin_reported(tmp_path: Path) -> None:
    root = _blink(tmp_path)
    _edit(root, cases.without_labels(cases.blink_files(major()), ("R1", "1")), cases.SHEET)
    code, env, _, _ = check(root, "--stages", "erc.kicad")
    errors = [i for i in env["issues"] if i["severity"] == "error"]
    assert code == 5 and [(i["code"], i["where"]) for i in errors] == [
        ("kicad.erc.pin-not-connected", "R1-1")
    ]
    assert errors[0]["message"] == "pin_not_connected: Pin not connected"
    erc = stage(env, "erc.kicad")
    assert erc["status"] == "errors" and erc["summary"]["by_type"]["pin_not_connected"] == 1
    assert erc["summary"]["types"]["kicad.erc.pin-not-connected"] == "pin_not_connected"
    # the label left alone on the other pin of the net is named by its text
    single = cases.SINGLE_PIN_LABEL[major()].replace("_", "-")
    assert [(i["severity"], i["where"]) for i in env["issues"] if i["code"] == f"kicad.erc.{single}"] == [
        ("warning", "LED_DRV")
    ]


def test_stage_severity_follows_the_project(tmp_path: Path) -> None:
    """Scenario "Severities follow the project": a type set to ``warning`` is reported as a warning."""
    root = _blink(tmp_path)
    files = cases.with_severity(
        cases.without_labels(cases.blink_files(major()), ("R1", "1")), "pin_not_connected", "warning"
    )
    _edit(root, files, cases.SHEET, cases.PROJECT)
    code, env, _, _ = check(root, "--stages", "erc.kicad")
    found = [i for i in env["issues"] if i["code"] == "kicad.erc.pin-not-connected"]
    assert code == 0 and [(i["severity"], i["where"]) for i in found] == [("warning", "R1-1")]
    assert stage(env, "erc.kicad")["status"] == "ok"


def test_stage_native_project(tmp_path: Path) -> None:
    root = hierarchy_project(tmp_path / "hier", folder=cases.hierarchy_folder(), major=major())
    before = tree_snapshot(root)
    _, env, _, err = check(root, "--stages", "erc.kicad")
    assert env, err
    erc = stage(env, "erc.kicad")
    assert erc["status"] in ("ok", "errors") and erc["summary"]["sheets"] == 2
    assert env["result"]["project"]["built"] is False
    assert {"top.kicad_sch", "child.kicad_sch"} <= set(env["result"]["project"]["files"])
    assert all(i["code"].startswith("kicad.erc.") and i["where"] for i in env["issues"])
    assert tree_snapshot(root) == before


def test_stage_schematic_the_tool_cannot_load(tmp_path: Path) -> None:
    """KiCad refuses the schematic: the ERC stage fails, and the board is still judged without parity."""
    root = _blink(tmp_path)
    _edit(root, cases.unloadable(cases.blink_files(major())), cases.SHEET)
    code, env, _, _ = check(root, "--stages", "erc.kicad,drc.kicad")
    erc, drc = stage(env, "erc.kicad"), stage(env, "drc.kicad")
    failed = [i for i in env["issues"] if i["code"] == "check.oracle-failed"]
    assert code == 5 and [i["where"] for i in failed] == ["blink.kicad_sch"]
    assert "Failed to load schematic" in failed[0]["message"]
    assert erc["status"] == "errors" and erc["evidence"]["level"] == "UNVERIFIED"
    unchecked = [i for i in env["issues"] if i["code"] == "kicad.drc.parity-unchecked"]
    assert [(i["severity"], i["where"]) for i in unchecked] == [("warning", "blink.kicad_sch")]
    assert drc["summary"]["parity_judged"] is False and drc["summary"]["canary"] == "fired"
    assert drc["summary"]["violations_judged"] is True and drc["evidence"]["level"] != "UNVERIFIED"


def test_stage_deterministic_and_read_only(tmp_path: Path) -> None:
    """Two runs of every default stage on a project with ERC findings: equal output, no date, no path,
    and a folder that is byte for byte and time for time what it was."""
    root = _blink(tmp_path)
    _edit(root, cases.without_labels(cases.blink_files(major()), ("R1", "1"), ("D1", "2")), cases.SHEET)
    before = tree_snapshot(root)
    first, second = check(root)[2], check(root)[2]
    assert tree_snapshot(root) == before
    assert without_elapsed(first) == without_elapsed(second)
    env = json.loads(first)
    assert "erc.kicad" in [s["name"] for s in env["result"]["stages"]]
    assert stage(env, "erc.kicad")["summary"]["violations"] >= 2
    for forbidden in ("<tmp>", str(Path.home()), str(tmp_path), str(root), "fenolite-kicad-"):
        assert forbidden not in first, forbidden
    assert not re.search(r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d", first), "a report date reached the output"
    assert not list(root.glob("*.kicad_prl")) and stage(env, "erc.kicad")["summary"]["tool_writes"] == (
        ["blink.kicad_prl"] if major() >= 10 else []
    )
