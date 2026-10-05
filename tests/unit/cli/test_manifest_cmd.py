# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite manifest`` (capability cli-contract, "Manifest command"; manufacturing-exports, "Project
manifest"; change c0065). Hermetic: the stages that need a tool run against the fake ``kicad-cli``.

The schematics are the authored sheets of ``tests/data/kicad/schematic``, copied next to a board: ``build``
writes no schematic yet. KiCad's ERC is not a stage of ``check`` yet (c0062), so no test here can give a
sheet ``native-verified``; the tests pin that it is not claimed."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import _ipc
import _netexport
import _schema
import pytest
from _asmcli import built, isolate
from _checkcli import hide_kicad, run
from _fakecli import calls, fake_kicad_cli, report_with
from _projects import authored_project, tree_snapshot

import fenolite
from fenolite.backends.kicad.libs import LibRow, LibTable, write_lib_table
from fenolite.cli.cmd_manifest import COMMAND, design_files
from fenolite.exports.manifest import STATES

DATA = Path(__file__).resolve().parents[2] / "data" / "kicad"
TWO_LAYER = DATA / "board" / "two_layer.kicad_pcb"
HIER = DATA / "schematic" / "hier"
SYMBOLS = DATA.parent / "libs" / "Mini.kicad_sym"
STAMP = ("--timestamp", "2026-01-02T03:04:05+00:00")
NAME = "fenolite-artifacts.json"
CLEARANCE = {
    "type": "clearance",
    "description": "Clearance violation",
    "severity": "error",
    "items": [
        {"uuid": "00000000-0000-0000-0000-000000000001", "description": "Track", "pos": {"x": 1, "y": 0}}
    ],
}


@pytest.fixture(autouse=True)
def hidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    isolate(monkeypatch, tmp_path)


def _no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _read(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert _schema.validate(data, _schema.load("fenolite.artifacts.v0.json")) == []
    assert [e["path"] for e in data["artifacts"]] == sorted(e["path"] for e in data["artifacts"])
    assert NAME not in [e["path"] for e in data["artifacts"]]
    assert set(data["states"]) == set(STATES) and sum(data["states"].values()) == len(data["artifacts"])
    for item in data["artifacts"]:
        file = path.parent / item["path"]
        assert item["sha256"] == hashlib.sha256(file.read_bytes()).hexdigest(), item["path"]
        assert item["bytes"] == file.stat().st_size
    return data


def _by_path(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {e["path"]: e for e in data["artifacts"]}


def _with_schematic(root: Path, stem: str) -> None:
    """The authored two-sheet schematic as the project's own."""
    shutil.copyfile(HIER / "top.kicad_sch", root / f"{stem}.kicad_sch")
    shutil.copyfile(HIER / "child.kicad_sch", root / "child.kicad_sch")


def _with_symbols(root: Path) -> None:
    """The authored Mini symbol library, named by a ``${KIPRJMOD}`` row of the symbol table, a row the
    command must not follow (it leaves the project) and a disabled one."""
    (root / "symbols").mkdir()
    shutil.copyfile(SYMBOLS, root / "symbols" / "Mini.kicad_sym")
    rows = (
        LibRow("Mini", "KiCad", "${KIPRJMOD}/symbols/Mini.kicad_sym"),
        LibRow("Away", "KiCad", "${KIPRJMOD}/../away.kicad_sym"),
        LibRow("Global", "KiCad", "${KICAD10_SYMBOL_DIR}/Device.kicad_sym"),
        LibRow("Off", "KiCad", "${KIPRJMOD}/notes.kicad_sym", disabled=True),
    )
    text = write_lib_table(LibTable("symbol", rows), target=10)
    (root / "sym-lib-table").write_text(text, encoding="utf-8", newline="\n")
    (root.parent / "away.kicad_sym").write_bytes(SYMBOLS.read_bytes())
    (root / "notes.kicad_sym").write_bytes(SYMBOLS.read_bytes())


def _checked_project(tmp_path: Path, **options: Any) -> tuple[Path, str]:
    """A built authored project with a schematic, and a fake ``kicad-cli`` whose DRC reports nothing."""
    root = authored_project(tmp_path, major=10, built=True)
    _with_schematic(root, "board")
    board = root / "board.kicad_pcb"
    fake = fake_kicad_cli(
        tmp_path / "bin",
        ipcd356=_ipc.for_board(board),
        netlist=_netexport.for_board(board),  # check compares the schematic's netlist (c0063)
        refill_board=board.read_text(encoding="utf-8") + "\n",
        **options,
    )
    return root, str(fake)


def test_hashes_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _no_subprocess(monkeypatch)
    args = ("manifest", str(TWO_LAYER), "--no-check", "--out", "m.json")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, env
    assert [p["path"] for p in env["result"]["plan"]] == ["m.json"] and not (tmp_path / "m.json").exists()
    assert env["result"]["manifest"] == "m.json" and env["result"]["check"] is None
    assert [(a["path"], a["kind"], a["state"]) for a in env["result"]["artifacts"]] == [
        ("two_layer.kicad_pcb", "kicad_pcb", "generated")
    ]
    assert set(env["result"]["artifacts"][0]) == {"path", "kind", "state", "stale", "held"}
    assert env["result"]["states"]["generated"] == 1
    assert env["result"]["project"]["schematic"] is None
    assert env["result"]["project"]["board"]["path"] == "two_layer.kicad_pcb"
    assert env["evidence"] == {"level": "UNVERIFIED", "oracle": None, "hypotheses": []}
    assert env["input"]["path"] == "two_layer.kicad_pcb"
    assert COMMAND.example_args == (str(TWO_LAYER), "--no-check", "--out", NAME, "--dry-run")
    assert COMMAND.mutation_example_args == COMMAND.example_args[:-1] and COMMAND.mutates


def test_design_files_of_a_built_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = built(monkeypatch, tmp_path)
    _no_subprocess(monkeypatch)
    (board,) = folder.glob("*.kicad_pcb")
    _with_schematic(folder, board.stem)
    _with_symbols(folder)
    (folder / "lib" / "Mini.pretty" / ".DS_Store").write_bytes(b"hidden")
    (folder / "lib" / "Mini.pretty" / "r.step").write_bytes(b"ISO-10303-21;\n")
    code, env, _, _ = run(monkeypatch, tmp_path, "manifest", str(folder), "--no-check", "--confirm")
    assert code == 0, env
    assert env["result"]["manifest"] == f"{folder.name}/{NAME}"
    assert [w["path"] for w in env["receipt"]["written"]] == [f"{folder.name}/{NAME}"]
    data = _read(folder / NAME)
    listed = _by_path(data)
    stem = board.stem
    assert sorted(listed) == design_files(board) == [
        "blink.kicad_dru", "blink.kicad_pcb", "blink.kicad_pro", "blink.kicad_sch", "child.kicad_sch",
        "fp-lib-table", "lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod",
        "lib/Mini.pretty/Mini_QFP-32_7x7mm_P0.8mm.kicad_mod", "lib/Mini.pretty/Mini_R_0603.kicad_mod",
        "lib/Mini.pretty/r.step", "sym-lib-table", "symbols/Mini.kicad_sym",
    ]  # fmt: skip
    kinds = {name: item["kind"] for name, item in listed.items()}
    assert kinds[f"{stem}.kicad_pcb"] == "kicad_pcb" and kinds["child.kicad_sch"] == "kicad_sch"
    assert kinds["fp-lib-table"] == kinds["sym-lib-table"] == "lib-table"
    assert kinds["symbols/Mini.kicad_sym"] == "kicad_sym" and kinds["lib/Mini.pretty/r.step"] == "file"
    authored = {
        f"{stem}.kicad_sch", "child.kicad_sch", "sym-lib-table", "symbols/Mini.kicad_sym",
        "lib/Mini.pretty/r.step",
    }  # fmt: skip
    for name, item in listed.items():
        assert (item["state"], item["stale"], item["layer"], item["from"]) == ("generated", False, None, {})
        assert item["content_sha256"] == item["sha256"] and item["evidence"] == "UNVERIFIED"
        assert item["tool"] == (None if name in authored else f"fenolite {fenolite.__version__}"), name
    assert not [name for name in listed if name.startswith(".fenolite") or name.endswith(".kicad_prl")]
    assert data["project"]["board"]["path"] == f"{stem}.kicad_pcb"
    assert data["project"]["schematic"]["path"] == f"{stem}.kicad_sch"
    assert data["project"]["schematic"]["format_version"] == 20260306
    assert data["tool"] == {"name": "fenolite", "version": fenolite.__version__} and data["check"] is None
    assert data["board"] == data["project"]["board"]

    # an edited file loses its writer
    board.write_bytes(board.read_bytes() + b"\n")
    code, env, _, _ = run(monkeypatch, tmp_path, "manifest", str(folder), "--no-check", "--confirm")
    assert code == 0, env
    again = _by_path(_read(folder / NAME))
    assert again[board.name]["tool"] is None and again[board.name]["sha256"] != listed[board.name]["sha256"]
    assert again[f"{stem}.kicad_pro"]["tool"] == f"fenolite {fenolite.__version__}"
    assert sorted(again) == sorted(listed)  # neither the manifest nor its backup is listed
    assert (folder / (NAME + ".bak")).is_file()


def _export(monkeypatch: pytest.MonkeyPatch, root: Path, fake: str, *kinds: str) -> None:
    args = ("export", str(root), "--out", "fab", *(kinds or ("--all",)), "--manifest", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, root, *args, "--confirm")
    assert code == 0, env


def test_artefact_folder_is_included(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, fake = _checked_project(tmp_path)
    _export(monkeypatch, root, fake)
    (root / "fab" / "notes.txt").write_text("by hand\n", encoding="utf-8")
    args = ("manifest", str(root), "--artifacts", str(root / "fab"), "--no-check")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0, env
    listed = _by_path(_read(root / NAME))
    fabrication = sorted(name for name in listed if name.startswith("fab/"))
    assert fabrication == [
        "fab/drill/board-NPTH.drl", "fab/drill/board-PTH.drl", "fab/gerbers/board-Edge_Cuts.gbr",
        "fab/gerbers/board-F_Cu.gbr", "fab/gerbers/board-job.gbrjob", "fab/netlist/board.d356",
        "fab/pos/board-pos.csv",
    ]  # fmt: skip
    gerber = listed["fab/gerbers/board-F_Cu.gbr"]
    assert (gerber["kind"], gerber["layer"], gerber["tool"]) == ("gerbers", "F.Cu", "kicad-cli 10.0.6")
    assert gerber["from"] == {"board": listed["board.kicad_pcb"]["sha256"]}
    assert gerber["content_sha256"] != gerber["sha256"] and gerber["evidence"] == "KICAD-VERIFIED"
    assert (gerber["state"], gerber["held"]) == ("generated", "checked: the board is generated")
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("manifest.unlisted", "info", "fab/notes.txt")
    ]
    assert "fab/notes.txt" not in listed and "notes.txt" not in listed  # the decoy of the project
    assert "sym-lib-table" in listed and "board.kicad_prl" not in listed


def test_artefact_folder_outside_the_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    args = ("manifest", str(root), "--no-check", "--dry-run", "--artifacts")
    code, _, err, _ = run(monkeypatch, tmp_path, *args, str(elsewhere))
    assert code == 2 and err["code"] == "FEN-2001" and err["where"] == "--artifacts"
    code, _, err, _ = run(monkeypatch, tmp_path, *args, str(root / "missing"))
    assert code == 3 and err["code"] == "FEN-3001"


def test_states_from_a_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, fake = _checked_project(tmp_path)
    _export(monkeypatch, root, fake)
    before = tree_snapshot(root)
    args = ("manifest", str(root), "--artifacts", "fab", "--kicad-cli", fake, *STAMP)
    code, env, _, _ = run(monkeypatch, root, *args, "--dry-run")
    assert code == 0, env["issues"]
    assert tree_snapshot(root) == before  # the stages ran on copies, and nothing was written
    assert any(c["args"][:2] == ["pcb", "drc"] for c in calls(Path(fake)))
    result = env["result"]
    stages = {s["name"]: s for s in result["check"]["stages"]}
    assert list(stages) == [
        "model.validate", "erc.kicad", "copper.clearance", "zone.fill", "drc.kicad",
        "parity", "netlist.assignment_compare", "roundtrip",
    ]  # fmt: skip
    assert stages["drc.kicad"] == {
        "name": "drc.kicad", "status": "ok", "level": "KICAD-VERIFIED", "oracle": "kicad-cli 10.0.6",
    }  # fmt: skip
    assert result["check"]["tool_version"] == "10.0.6" and stages["erc.kicad"]["status"] == "ok"
    shown = {a["path"]: a for a in result["artifacts"]}
    assert (shown["board.kicad_pcb"]["state"], shown["board.kicad_pcb"]["held"]) == ("native-verified", "")
    for name in ("board.kicad_pro", "board.kicad_dru", "fp-lib-table"):
        assert shown[name]["state"] == "native-verified", name
    assert [a["state"] for a in shown.values() if a["kind"] == "kicad_mod"] == ["native-verified"] * 4
    # the schematic side: KiCad's ERC is the stage ``erc.kicad`` (change c0062)
    for name in ("board.kicad_sch", "child.kicad_sch", "sym-lib-table"):
        assert (shown[name]["state"], shown[name]["held"]) == ("native-verified", ""), name
    assert stages["erc.kicad"]["level"] == "KICAD-VERIFIED"
    fabrication = [a for a in shown.values() if a["path"].startswith("fab/")]
    assert len(fabrication) == 7 and {a["state"] for a in fabrication} == {"checked"}
    assert result["states"] == {
        "generated": 0, "checked": 7, "roundtrip-ok": 0, "oracle-verified": 0, "native-verified": 11,
    }  # fmt: skip
    assert env["evidence"]["level"] == "INFERRED" and "H-K-SCH-READ" in env["evidence"]["hypotheses"]
    assert env["issues"] == [] or all(i["severity"] != "error" for i in env["issues"])

    code, env, _, _ = run(monkeypatch, root, *args, "--confirm")
    assert code == 0, env
    data = _read(root / NAME)
    assert data["tool"] == {"name": "kicad-cli", "version": "10.0.6"}
    assert data["check"] == result["check"] and data["states"] == result["states"]
    assert data["generated"] == STAMP[1]
    text = (root / NAME).read_text(encoding="utf-8")
    for needle in (str(tmp_path), str(Path.home()), "fenolite-kicad-"):
        assert needle not in text and needle not in json.dumps(env["result"])
    code, _, _, _ = run(monkeypatch, root, *args, "--confirm", "--no-backup")
    assert code == 0 and (root / NAME).read_text(encoding="utf-8") == text  # byte-identical


def test_errors_still_give_a_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, fake = _checked_project(tmp_path, drc_report=report_with(CLEARANCE))
    code, env, err, _ = run(monkeypatch, root, "manifest", str(root), "--kicad-cli", fake, "--confirm")
    assert code == 5 and err["code"] == "FEN-5001"
    assert "kicad.drc.clearance" in [i["code"] for i in env["issues"]]
    assert [w["path"] for w in env["receipt"]["written"]] == [NAME]
    data = _read(root / NAME)
    listed = _by_path(data)
    assert listed["board.kicad_pcb"]["state"] == "roundtrip-ok"
    assert listed["board.kicad_pcb"]["held"] == "native-verified: drc.kicad reported errors"
    # the DRC error holds the board side; the schematic side follows the ERC, which found nothing
    assert listed["board.kicad_pro"]["state"] == "checked" and data["states"]["native-verified"] == 3
    assert listed["board.kicad_sch"]["state"] == "native-verified"
    assert listed["board.kicad_pro"]["held"] == "native-verified: the board is roundtrip-ok"
    drc = next(s for s in data["check"]["stages"] if s["name"] == "drc.kicad")
    assert drc["status"] == "errors"


def test_stages_that_need_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    _no_subprocess(monkeypatch)
    args = ("manifest", str(root), "--stages", "model.validate,copper.clearance,roundtrip", "--dry-run")
    code, env, _, _ = run(monkeypatch, root, *args)
    assert code == 0, env["issues"]
    shown = {a["path"]: a for a in env["result"]["artifacts"]}
    assert shown["board.kicad_pcb"]["state"] == "roundtrip-ok"
    assert shown["board.kicad_pcb"]["held"] == "native-verified: drc.kicad did not run"
    assert env["result"]["check"]["tool_version"] is None
    code, _, err, _ = run(monkeypatch, root, "manifest", str(root), "--stages", "nothing", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_no_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    code, env, err, _ = run(monkeypatch, root, "manifest", str(root), "--dry-run")
    assert code == 6 and err["code"] == "FEN-6001" and env["ok"] is False
    assert "--no-check" in err["hint"] and "--stages" in err["hint"]
    assert not (root / NAME).exists()


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    for extra in (("--no-check",), ("--stages", "roundtrip"), ("--artifacts", str(root))):
        code, _, err, _ = run(monkeypatch, root, "manifest", str(root), "--verify", *extra)
        assert code == 2 and err["code"] == "FEN-2001" and err["where"] == extra[0]
    code, _, err, _ = run(monkeypatch, root, "manifest", str(root), "--no-check", "--stages", "roundtrip")
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(monkeypatch, root, "manifest", str(root / "nothing"), "--no-check", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001"
    code, _, err, _ = run(monkeypatch, root, "manifest", str(root), "--no-check")
    assert code == 4 and err["code"] == "FEN-4001" and not (root / NAME).exists()


def _written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, str]:
    """A project with exported files and a table, and its manifest just written from a check."""
    root, fake = _checked_project(tmp_path)
    _export(monkeypatch, root, fake)
    code, env, _, _ = run(
        monkeypatch, root, "pnp", str(root), "--out", "fab/pnp.csv", "--manifest", "--confirm"
    )
    assert code == 0, env
    args = ("manifest", str(root), "--artifacts", "fab", "--kicad-cli", fake)
    code, env, _, _ = run(monkeypatch, root, *args, "--confirm")
    assert code == 0, env["issues"]
    return root, fake


def test_verify_an_unchanged_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _written(monkeypatch, tmp_path)
    _no_subprocess(monkeypatch)
    before = tree_snapshot(root)
    code, env, _, _ = run(monkeypatch, tmp_path, "manifest", str(root), "--verify")
    assert code == 0, env
    assert env["result"]["verified"] is True and env["result"]["differences"] == []
    assert "check" not in env["result"] and "plan" not in env["result"] and env["receipt"] is None
    assert env["result"]["manifest"] == f"{root.name}/{NAME}"
    assert env["result"]["states"]["native-verified"] == 11 and len(env["result"]["artifacts"]) == 19
    assert env["evidence"]["level"] == "UNVERIFIED" and env["issues"] == []
    assert tree_snapshot(root) == before


def test_verify_after_an_edit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _written(monkeypatch, tmp_path)
    _no_subprocess(monkeypatch)
    gerber = root / "fab" / "gerbers" / "board-F_Cu.gbr"
    gerber.write_bytes(gerber.read_bytes() + b"X")
    board = root / "board.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    (root / "fab" / "drill" / "board-NPTH.drl").unlink()
    (root / "fab" / "readme.txt").write_text("by hand\n", encoding="utf-8")
    before = tree_snapshot(root)
    code, env, err, _ = run(monkeypatch, tmp_path, "manifest", str(root), "--verify")
    assert code == 5 and err["code"] == "FEN-5001" and env["result"]["verified"] is False
    assert env["result"]["differences"] == [
        {"path": "board.kicad_pcb", "code": "manifest.changed"},
        {"path": "fab/drill/board-NPTH.drl", "code": "manifest.missing"},
        {"path": "fab/drill/board-PTH.drl", "code": "manifest.stale"},
        {"path": "fab/gerbers/board-Edge_Cuts.gbr", "code": "manifest.stale"},
        {"path": "fab/gerbers/board-F_Cu.gbr", "code": "manifest.changed"},
        {"path": "fab/gerbers/board-job.gbrjob", "code": "manifest.stale"},
        {"path": "fab/netlist/board.d356", "code": "manifest.stale"},
        {"path": "fab/pnp.csv", "code": "manifest.stale"},
        {"path": "fab/pos/board-pos.csv", "code": "manifest.stale"},
        {"path": "fab/readme.txt", "code": "manifest.unlisted"},
    ]
    severities = {(i["code"], i["severity"]) for i in env["issues"]}
    assert severities == {
        ("manifest.changed", "error"), ("manifest.missing", "error"), ("manifest.stale", "warning"),
        ("manifest.unlisted", "info"),
    }  # fmt: skip
    assert tree_snapshot(root) == before
    # the list is paged, and the verdict comes from the whole of it
    code, env, _, _ = run(monkeypatch, tmp_path, "manifest", str(root), "--verify", "--limit", "2")
    assert code == 5 and len(env["result"]["differences"]) == 2 and env["result"]["page"]["total"] == 10
    assert env["result"]["page"]["path"] == "differences" and env["result"]["verified"] is False


def test_verify_the_manifest_of_an_artefact_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--out`` names the manifest that ``export --manifest`` wrote: its paths are relative to its folder."""
    root, fake = _checked_project(tmp_path)
    _export(monkeypatch, root, fake)
    _no_subprocess(monkeypatch)
    args = ("manifest", str(root), "--verify", "--out", str(root / "fab" / NAME))
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 0 and env["result"]["verified"] is True and env["result"]["differences"] == [], env
    (root / "fab" / "pos" / "board-pos.csv").write_bytes(b"edited\n")
    (root / "fab" / "notes.txt").write_text("by hand\n", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 5 and env["result"]["differences"] == [
        {"path": "notes.txt", "code": "manifest.unlisted"},
        {"path": "pos/board-pos.csv", "code": "manifest.changed"},
    ]
    board = root / "board.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    codes = [d["code"] for d in env["result"]["differences"]]
    assert code == 5 and codes.count("manifest.stale") == 6 and codes.count("manifest.changed") == 1


def test_verify_needs_a_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "manifest", str(root), "--verify")
    assert code == 3 and err["code"] == "FEN-3001"
    (root / NAME).write_text("{", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "manifest", str(root), "--verify")
    assert code == 3 and err["code"] == "FEN-3004"
    assert (root / NAME).read_text(encoding="utf-8") == "{"


def test_writing_again_after_edits(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An artefact that is gone is left out, an edited one loses its source, and the files made from a
    board that changed are stale: none of them keeps a state it no longer deserves."""
    root, fake = _written(monkeypatch, tmp_path)
    (root / "fab" / "drill" / "board-NPTH.drl").unlink()
    position = root / "fab" / "pos" / "board-pos.csv"
    position.write_bytes(position.read_bytes() + b"R9,1k\n")
    stages = "model.validate,copper.clearance,drc.kicad,roundtrip"  # the fake refills one board text only
    args = ("manifest", str(root), "--artifacts", "fab", "--kicad-cli", fake, "--stages", stages)
    code, env, _, _ = run(monkeypatch, root, *args, "--confirm")
    assert code == 0, env["issues"]
    found = [
        (i["code"], i["severity"], i["where"]) for i in env["issues"] if i["code"].startswith("manifest.")
    ]
    assert found == [
        ("manifest.missing", "warning", "fab/drill/board-NPTH.drl"),
        ("manifest.changed", "warning", "fab/pos/board-pos.csv"),
    ]
    listed = _by_path(_read(root / NAME))
    assert "fab/drill/board-NPTH.drl" not in listed
    edited = listed["fab/pos/board-pos.csv"]
    assert (edited["state"], edited["stale"], edited["tool"], edited["from"]) == (
        "generated",
        False,
        None,
        {},
    )
    assert edited["held"] == "checked: no source is recorded"
    assert listed["fab/gerbers/board-F_Cu.gbr"]["state"] == "checked"

    board = root / "board.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    code, env, _, _ = run(monkeypatch, root, *args, "--confirm")
    assert code == 0, env["issues"]
    listed = _by_path(_read(root / NAME))
    gerber = listed["fab/gerbers/board-F_Cu.gbr"]
    assert (gerber["state"], gerber["stale"]) == ("generated", True)
    assert gerber["held"] == "checked: the board changed since the file was made"
    assert (
        listed["board.kicad_pcb"]["state"] == "native-verified" and listed["board.kicad_pcb"]["tool"] is None
    )
    stale = sorted(i["where"] for i in env["issues"] if i["code"] == "manifest.stale")
    assert stale == sorted(n for n, item in listed.items() if item["stale"]) and len(stale) == 6


def test_unreadable_folder_manifest(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    (root / "fab").mkdir()
    (root / "fab" / NAME).write_text("{", encoding="utf-8")
    (root / "empty").mkdir()
    args = ("manifest", str(root), "--artifacts", "fab", "--artifacts", "empty", "--no-check")
    code, env, _, _ = run(monkeypatch, root, *args, "--confirm")
    assert code == 5 and [(i["code"], i["where"]) for i in env["issues"]] == [
        ("manifest.unreadable", f"fab/{NAME}")
    ]
    assert not [name for name in _by_path(_read(root / NAME)) if name.startswith("fab/")]
    assert (root / "fab" / NAME).read_text(encoding="utf-8") == "{"


def test_the_project_folder_as_an_artefact_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A table written next to the board merges into the project manifest, and the next run keeps it."""
    root, _ = _checked_project(tmp_path)
    code, env, _, _ = run(monkeypatch, root, "manifest", str(root), "--no-check", "--confirm")
    assert code == 0, env
    code, env, _, _ = run(monkeypatch, root, "pnp", str(root), "--out", "pnp.csv", "--manifest", "--confirm")
    assert code == 0, env
    merged = _by_path(_read(root / NAME))
    assert "pnp.csv" in merged and merged["board.kicad_pcb"]["kind"] == "kicad_pcb"
    code, env, _, _ = run(
        monkeypatch, root, "manifest", str(root), "--artifacts", ".", "--no-check", "--confirm"
    )
    assert code == 0, env
    listed = _by_path(_read(root / NAME))
    assert listed["pnp.csv"]["kind"] == "pnp" and listed["pnp.csv"]["from"] == {
        "board": listed["board.kicad_pcb"]["sha256"]
    }
    assert [i["where"] for i in env["issues"] if i["code"] == "manifest.unlisted"] == ["notes.txt"]


def test_artifacts_are_paged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root, _ = _checked_project(tmp_path)
    args = ("manifest", str(root), "--no-check", "--dry-run", *STAMP)
    code, whole, _, _ = run(monkeypatch, root, *args)
    code, env, _, _ = run(monkeypatch, root, *args, "--limit", "3")
    assert code == 0 and env["result"]["artifacts"] == whole["result"]["artifacts"][:3]
    assert env["result"]["page"]["path"] == "artifacts"
    assert env["result"]["page"]["total"] == len(whole["result"]["artifacts"])
    assert env["result"]["states"] == whole["result"]["states"]
    assert env["result"]["plan"] == whole["result"]["plan"]  # the manifest that is written is whole
