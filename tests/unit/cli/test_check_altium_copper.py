# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` and ``fenolite parity`` on Altium input with the two stages of change c0088
(capability altium-verification, "Copper check on Altium boards", "Parity on Altium projects" and
"Document stage order"). The faults are planted in the design script and written by the build
(``tests/_altium_drc.py``); the committed samples are checked as they are. No tool runs."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from _altium_drc import CROSSING, DOCUMENT, NEAR, PROJECT, build_altium, cli, coded, native, plant, stages
from _projects import tree_snapshot
from _routed import Routed

from fenolite.checks.documents import DOCUMENT_STAGES
from fenolite.checks.parity import SUMMARY_KEYS

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "altium"
COMMITTED = ("blink", "routed", "board6")


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *lines: str) -> tuple[Routed, Path]:
    """The routed blink with ``lines`` in its script, built for Altium in warn mode, and a native copy."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, *lines)
    code, env, err = build_altium(routed, "--copper-check", "warn", "--confirm")
    assert code == 0, (env.get("issues"), err)
    return routed, native(routed.out, tmp_path / "native")


@pytest.mark.parametrize("name", COMMITTED)
def test_committed_samples_have_no_finding(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unedited project gives no copper finding and no parity finding, and the folder is not touched."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    folder = SAMPLES / name
    before = tree_snapshot(folder)
    code, env, err = cli(routed, "check", str(folder), "--stages", "copper.clearance,parity")
    assert code == 0, err
    found = stages(env)
    assert list(found) == ["copper.clearance", "parity"]
    copper, parity = found["copper.clearance"], found["parity"]
    assert copper["status"] == "ok" and parity["status"] == "ok"
    assert (copper["summary"]["shorts"], copper["summary"]["clearance"]) == (0, 0)
    assert copper["summary"]["unsupported"] == {} and copper["summary"]["items"]["pad"] >= 36
    assert copper["summary"]["rules"]["opaque_clearance_rules"] == 0
    assert not any(parity["summary"][key] for key in SUMMARY_KEYS)
    assert parity["summary"]["netlist"] == "own" and parity["summary"]["compared"] is False
    assert "H-A-DRC-SAME" in copper["evidence"]["hypotheses"]
    assert "H-A-DRC-PARITY" in parity["evidence"]["hypotheses"]
    assert tree_snapshot(folder) == before and not (folder / ".fenolite").exists()


def test_unpoured_polygons_are_said(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Unpoured polygons are said": the routed sample holds two polygons that are not poured."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, env, _ = cli(routed, "check", str(SAMPLES / "routed"), "--stages", "copper.clearance")
    assert code == 0
    (stage,) = stages(env).values()
    (said,) = coded(env, "copper.item-unsupported")
    assert said["severity"] == "warning" and said["message"].startswith("2 unpoured zone(s)")
    assert stage["summary"]["unpoured"] == 2 and stage["evidence"]["level"] == "UNVERIFIED"
    # the blink has no polygon: the stage keeps the level of the import
    code, env, _ = cli(routed, "check", str(SAMPLES / "blink"), "--stages", "copper.clearance")
    (stage,) = stages(env).values()
    assert stage["summary"]["unpoured"] == 0 and stage["evidence"]["level"] == "INFERRED"
    assert coded(env, "copper.item-unsupported") == []


def test_default_stages_and_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, env, _ = cli(routed, "check", str(SAMPLES / "blink"))
    assert code == 0 and list(stages(env)) == list(DOCUMENT_STAGES)
    assert [stage["status"] for stage in stages(env).values()][:7] == ["ok"] * 7


def test_a_short_on_an_altium_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A short on an Altium board": exit 5 and one ``copper.short`` that names the two nets,
    on the built folder and on a native copy alike."""
    routed, copy = planted(tmp_path, monkeypatch, CROSSING)
    for folder in (routed.out, copy):
        code, env, _ = cli(routed, "check", str(folder), "--stages", "copper.clearance")
        assert code == 5
        (short,) = coded(env, "copper.short")
        assert short["severity"] == "error" and "LED_A" in short["message"] and "LED_DRV" in short["message"]
        (stage,) = stages(env).values()
        assert stage["status"] == "errors" and stage["summary"]["shorts"] == 1
    # the default stages find it as well, and a document given alone
    code, env, _ = cli(routed, "check", str(copy / PROJECT))
    assert code == 5 and len(coded(env, "copper.short")) == 1
    code, env, _ = cli(routed, "check", str(copy / DOCUMENT), "--stages", "copper.clearance")
    assert code == 5 and len(coded(env, "copper.short")) == 1


def test_a_clearance_violation_on_an_altium_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, copy = planted(tmp_path, monkeypatch, NEAR)
    routed = Routed(tmp_path / "again", monkeypatch, confirm=False)
    code, env, _ = cli(routed, "check", str(copy), "--stages", "copper.clearance")
    assert code == 5
    (near,) = coded(env, "copper.clearance")
    assert near["severity"] == "error" and "rule:" in near["message"]
    assert coded(env, "copper.short") == []


def test_skips_without_a_pcb_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, env, _ = cli(routed, "check", str(SAMPLES / "tree"), "--stages", "copper.clearance,parity")
    assert code == 0
    found = stages(env)
    assert (found["copper.clearance"]["status"], found["copper.clearance"]["reason"]) == (
        "skipped",
        "single-source",
    )
    assert (found["parity"]["status"], found["parity"]["reason"]) == ("skipped", "single-source")
    code, env, _ = cli(routed, "check", str(SAMPLES / "blink" / "blink.PcbDoc"), "--stages", "parity")
    assert stages(env)["parity"]["reason"] == "no-schematic"


def renamed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Routed, Path]:
    """The routed blink built for Altium, with the PCB document of a build whose resistor is ``R99``."""
    routed = Routed(tmp_path / "a", monkeypatch, confirm=False)
    assert build_altium(routed, "--confirm")[0] == 0
    other = Routed(tmp_path / "b", monkeypatch, confirm=False)
    other.edit_script('Part("R1"', 'Part("R99"')
    assert build_altium(other, "--confirm")[0] == 0
    copy = native(routed.out, tmp_path / "native")
    shutil.copyfile(other.out / DOCUMENT, copy / DOCUMENT)
    return routed, copy


def test_renamed_designator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Renamed designator": the board holds ``R99`` where the schematic holds ``R1``."""
    routed, copy = renamed(tmp_path, monkeypatch)
    code, env, _ = cli(routed, "check", str(copy), "--stages", "parity")
    assert code == 5
    assert [found["where"] for found in coded(env, "parity.missing-footprint")] == ["R1"]
    assert [found["where"] for found in coded(env, "parity.extra-footprint")] == ["R99"]
    (stage,) = stages(env).values()
    assert stage["summary"]["refs_one_side"] == 2 and stage["summary"]["netlist"] == "own"
    # the command gives the same findings
    code, env, _ = cli(routed, "parity", str(copy))
    assert code == 5
    assert [(f["code"], f["key"]) for f in env["result"]["findings"]] == [
        ("parity.extra-footprint", "R99"),
        ("parity.missing-footprint", "R1"),
    ]


@pytest.mark.parametrize("given", ["folder", "project", "board"])
def test_parity_command_on_an_agreeing_project(
    given: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Agreeing project": exit 0 and every summary count 0, for the three forms of the path."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    folder = SAMPLES / "blink"
    path = {"folder": folder, "project": folder / "blink.PrjPcb", "board": folder / "blink.PcbDoc"}[given]
    before = tree_snapshot(folder)
    code, env, err = cli(routed, "parity", str(path))
    assert code == 0, err
    result = env["result"]
    assert list(result) == ["board", "schematic", "netlist", "summary", "findings"]
    assert (result["board"], result["schematic"], result["netlist"]) == (
        "blink.PcbDoc",
        "blink.SchDoc",
        "own",
    )
    assert not any(result["summary"].values()) and result["findings"] == [] and env["issues"] == []
    assert env["input"]["path"] == "blink.PcbDoc" and env["input"]["kind"] == "altium_pcbdoc"
    assert env["evidence"]["level"] == "INFERRED" and env["evidence"]["oracle"] is None
    assert tree_snapshot(folder) == before


def test_parity_command_refusals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, _, err = cli(routed, "parity", str(SAMPLES / "blink"), "--netlist", "kicad")
    assert code == 2 and "FEN-2001" in err and "--netlist" in err
    # a PCB document without a project beside it has no schematic to compare with
    alone = tmp_path / "alone"
    alone.mkdir()
    shutil.copyfile(SAMPLES / "blink" / "blink.PcbDoc", alone / "blink.PcbDoc")
    code, _, err = cli(routed, "parity", str(alone / "blink.PcbDoc"))
    assert code == 3 and "no schematic" in err
    # a project without a PCB document has no board
    code, _, err = cli(routed, "parity", str(SAMPLES / "tree"))
    assert code == 3 and "PCB document" in err
    # --netlist own is what the Altium branch does anyway
    code, env, _ = cli(routed, "parity", str(SAMPLES / "blink"), "--netlist", "own")
    assert code == 0 and env["result"]["netlist"] == "own"
