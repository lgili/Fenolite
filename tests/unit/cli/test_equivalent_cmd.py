# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite equivalent`` (capability design-equivalence, "Equivalent command" and "Triangle oracle";
change c0045). Hermetic: the two-path form runs no tool, and the triangle runs a fake ``kicad-cli``."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import blink, build
from _checkcli import hide_kicad, run, without_elapsed
from _fakecli import calls, fake_kicad_cli
from _projects import authored_project, tree_snapshot

from fenolite.backends import registry
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[2] / "data"
TWO_LAYER = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
BLINK = DATA / "altium" / "blink"
PCBDOC = BLINK / "blink.PcbDoc"
KEYS = {
    "level", "equivalent", "sides", "tolerances", "frame", "translation", "levels", "differences", "excluded",
    "profile",
}  # fmt: skip
SIDE_KEYS = {"path", "sha256", "backend", "netlist_source", "components", "footprints"}
EXCLUSIONS = """schema = 1
[[profile]]
name = "moved"
tool = "none"
tool_version = "1"
frame = "relative"
tolerance_nm = 5
tolerance_udeg = 0
[[profile.rule]]
id = "d1-rotation"
level = 4
kind = "rotation"
where = "D1"
attribution = "undecided"
reason = "an authored rule of the test"
hypothesis = "H-G-EQ-ROT"
"""


def _changed(tmp_path: Path, name: str = "copy.kicad_pcb", **moves: Any) -> Path:
    """A copy of the two-layer board, written with the KiCad backend: ``R1`` moved by 1 mm on x and its
    pad 1 put on the net of its pad 2 (``net=True``), every footprint moved (``shift``), ``D1`` turned
    (``turn``)."""
    design = read_board(TWO_LAYER.read_text(encoding="utf-8"), file=TWO_LAYER.name)
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    shift = moves.get("shift", Point(0, 0))
    footprints = []
    for footprint in design.board.footprints:
        ref = refs[footprint.component_id]
        at = Point(footprint.position.x + shift.x, footprint.position.y + shift.y)
        pads = footprint.pads
        if ref == "R1" and moves.get("r1", True):
            at = Point(at.x + 1_000_000, at.y)
        if ref == "R1" and moves.get("net", True):
            other = next(p.net_id for p in pads if p.number == "2")
            pads = tuple(dataclasses.replace(p, net_id=other) if p.number == "1" else p for p in pads)
        rotation = footprint.rotation + (moves.get("turn", 0) if ref == "D1" else 0)
        footprints.append(dataclasses.replace(footprint, position=at, pads=pads, rotation=rotation))
    changed = dataclasses.replace(
        design, board=dataclasses.replace(design.board, footprints=tuple(footprints))
    )
    folder = tmp_path / "changed"
    folder.mkdir(exist_ok=True)
    target = folder / name
    target.write_text(registry.get("kicad").write(changed).text, encoding="utf-8", newline="\n")
    return target


def _codes(env: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(i["code"], i["severity"], i["where"]) for i in env["issues"]]


def test_a_board_equals_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(TWO_LAYER))
    result = env["result"]
    assert code == 0 and env["ok"] is True and set(result) == KEYS
    assert (result["equivalent"], result["level"], result["profile"]) == (True, 4, None)
    assert [(lv["level"], lv["name"], lv["differences"], lv["excluded"]) for lv in result["levels"]] == [
        (1, "components", 0, 0), (2, "netlist", 0, 0), (3, "footprints", 0, 0), (4, "placement", 0, 0),
    ]  # fmt: skip
    assert [lv["compared"] for lv in result["levels"]] == [2, 4, 4, 2]
    assert result["sides"]["a"] == result["sides"]["b"] and set(result["sides"]["a"]) == SIDE_KEYS
    assert (
        result["sides"]["a"]["path"] == "two_layer.kicad_pcb" and result["sides"]["a"]["backend"] == "kicad"
    )
    assert (result["sides"]["a"]["netlist_source"], result["sides"]["a"]["footprints"]) == ("board", 2)
    assert len(result["sides"]["a"]["sha256"]) == 64
    assert result["tolerances"] == {"length_nm": 0, "angle_udeg": 0}
    assert (result["frame"], result["translation"]) == ("absolute", [0, 0])
    assert result["differences"] == [] and result["excluded"] == [] and env["issues"] == []
    assert env["input"]["path"] == "two_layer.kicad_pcb"
    assert env["evidence"] == {"level": "INFERRED", "oracle": None, "hypotheses": ["H-K-PCB-READ"]}


def test_differences_give_exit_5(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    copy = _changed(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(copy))
    result = env["result"]
    assert code == 5 and env["ok"] is False and err["code"] == "FEN-5001"
    assert result["equivalent"] is False and result["level"] == 4
    assert _codes(env) == [("netlist.assignment-differs", "error", "R1-1"), ("equiv.position", "error", "R1")]
    assert [(d["level"], d["kind"], d["where"], d["field"]) for d in result["differences"]] == [
        (2, "net", "R1-1", "net"), (4, "position", "R1", "position"),
    ]  # fmt: skip
    assert (result["differences"][1]["a"], result["differences"][1]["b"]) == (
        "20000000,15000000",
        "21000000,15000000",
    )
    assert [lv["differences"] for lv in result["levels"]] == [0, 1, 0, 1]
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(copy), "--level", "1")
    assert code == 0 and env["result"]["equivalent"] is True and len(env["result"]["levels"]) == 1


def test_built_design_against_its_board(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project = authored_project(tmp_path, major=10, built=True)
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(project / ".fenolite"), str(project))
    result = env["result"]
    assert code == 0, env["issues"]
    assert (result["sides"]["a"]["backend"], result["sides"]["b"]["backend"]) == ("fenolite", "kicad")
    assert (result["sides"]["a"]["path"], result["sides"]["a"]["sha256"]) == (".fenolite", None)
    assert result["sides"]["b"]["path"] == "board.kicad_pcb" and result["level"] == 4
    assert env["evidence"]["level"] == "INFERRED"
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(project / "board.kicad_pro"), str(project))
    assert code == 0 and env["result"]["sides"]["a"]["path"] == "board.kicad_pcb"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((str(TWO_LAYER),), "give B or --against kicad-import"),
        ((str(TWO_LAYER), str(TWO_LAYER), "--against", "kicad-import"), "give B or --against kicad-import"),
        ((str(TWO_LAYER), str(TWO_LAYER), "--level", "5"), "--level is one of 1, 2, 3, 4"),
        ((str(TWO_LAYER), str(TWO_LAYER), "--level", "0"), "--level is one of 1, 2, 3, 4"),
        (
            (str(TWO_LAYER), str(TWO_LAYER), "--tolerance-nm", "-1"),
            "--tolerance-nm is a non-negative integer",
        ),
        ((str(TWO_LAYER), str(TWO_LAYER), "--tolerance-udeg", "-1"), "--tolerance-udeg is a non-negative"),
        ((str(TWO_LAYER), str(TWO_LAYER), "--profile", "moved"), "--exclusions and --profile go together"),
        ((str(TWO_LAYER), str(DATA / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod")), "is a library"),
        ((str(TWO_LAYER), str(DATA / "libs" / "Mini.kicad_sym")), "is a library"),
        ((str(TWO_LAYER), str(Path(__file__))), "equivalent does not read test_equivalent_cmd.py"),
        ((str(BLINK / "blink.SchDoc"), str(PCBDOC), "--level", "3"), "side a holds none; the highest level"),
        ((str(TWO_LAYER), "--against", "kicad-import"), "compares an Altium PCB document"),
    ],
)
def test_usage_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...], message: str
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "equivalent", *args)
    assert code == 2 and err["code"] == "FEN-2001" and message in err["message"], err
    assert env["ok"] is False and env["result"] == {}


def test_bad_option_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for extra in (("--level", "four"), ("--frame", "turned"), ("--tolerance-nm", "1.5"), ("--against", "x")):
        code, _, err, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(TWO_LAYER), *extra)
        assert code == 2 and err["code"] == "FEN-2001", extra


def test_missing_and_unreadable_inputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(
        monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(tmp_path / "none.kicad_pcb")
    )
    assert code == 3 and err["code"] == "FEN-3001" and "none.kicad_pcb" in err["message"]
    broken = tmp_path / "broken.kicad_pcb"
    broken.write_text("(kicad_pcb", encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(broken))
    assert code == 3 and err["code"] == "FEN-3004"
    empty = tmp_path / "empty"
    empty.mkdir()
    code, _, err, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(empty))
    assert code == 2 and err["code"] == "FEN-2001"  # a folder that holds no project and no board


def test_readonly_and_hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("equivalent started a subprocess")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    project = authored_project(tmp_path, major=10, built=True)
    copy = _changed(tmp_path)
    before = tree_snapshot(project), tree_snapshot(copy.parent)
    work = tmp_path / "work"
    work.mkdir()
    code, _, _, _ = run(monkeypatch, work, "equivalent", str(project / ".fenolite"), str(project))
    assert code == 0
    code, _, _, _ = run(monkeypatch, work, "equivalent", str(project), str(copy), "--level", "1")
    assert code in (0, 5)
    assert (tree_snapshot(project), tree_snapshot(copy.parent)) == before
    assert list(work.iterdir()) == []


def test_output_is_deterministic_and_holds_no_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    copy = _changed(tmp_path)
    _, _, err_one, one = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(copy))
    _, _, err_two, two = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(copy))
    assert without_elapsed(one) == without_elapsed(two) and err_one == err_two
    assert str(tmp_path) not in one and str(TWO_LAYER.parent) not in one


def test_relative_paths_resolve_against_the_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    copy = _changed(tmp_path, net=False, r1=False)
    code, env, _, _ = run(monkeypatch, copy.parent, "equivalent", "copy.kicad_pcb", str(TWO_LAYER))
    assert code == 0 and env["result"]["sides"]["a"]["path"] == "copy.kicad_pcb"


def test_frame_tolerance_and_ignore_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    copy = _changed(tmp_path, net=False, r1=False, shift=Point(2_000_000, -1_000_000), turn=3)
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(TWO_LAYER), str(copy))
    assert code == 5
    assert _codes(env) == [
        ("equiv.position", "error", "D1"),
        ("equiv.rotation", "error", "D1"),
        ("equiv.position", "error", "R1"),
    ]
    args = ("equivalent", str(TWO_LAYER), str(copy), "--frame", "relative")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 5 and _codes(env) == [("equiv.rotation", "error", "D1")]
    assert env["result"]["translation"] == [2_000_000, -1_000_000] and env["result"]["frame"] == "relative"
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--tolerance-udeg", "3")
    assert code == 0 and env["result"]["tolerances"] == {"length_nm": 0, "angle_udeg": 3}
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--ignore-ref", "D*", "--ignore-ref", "X?")
    assert code == 0 and env["result"]["levels"][0]["summary"]["ignored"] == 1
    assert [lv["compared"] for lv in env["result"]["levels"]] == [1, 2, 2, 1]


def test_profile_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(EXCLUSIONS, encoding="utf-8")
    copy = _changed(tmp_path, net=False, r1=False, shift=Point(2_000_000, -1_000_000), turn=3)
    args = ("equivalent", str(TWO_LAYER), str(copy), "--exclusions", str(rules), "--profile", "moved")
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    result = env["result"]
    assert code == 0 and result["equivalent"] is True
    assert result["profile"] == {"name": "moved", "tool_version": "1", "rules": 1}
    assert (result["frame"], result["tolerances"]) == ("relative", {"length_nm": 5, "angle_udeg": 0})
    assert result["excluded"] == [
        {"level": 4, "kind": "rotation", "where": "D1", "field": "rotation", "a": "30000000", "b": "30000003",
         "rule": "d1-rotation"}
    ]  # fmt: skip
    assert result["differences"] == [] and result["levels"][3]["excluded"] == 1
    assert _codes(env) == [("equiv.excluded", "info", "")]
    assert (
        env["issues"][0]["message"]
        == "rule d1-rotation excludes 1 difference(s): an authored rule of the test"
    )
    # an option on the command line overrides the profile's value
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--frame", "absolute", "--tolerance-nm", "0")
    assert code == 5 and env["result"]["frame"] == "absolute"
    assert env["result"]["tolerances"] == {"length_nm": 0, "angle_udeg": 0}
    assert [c for c in _codes(env) if c[1] == "error"] == [
        ("equiv.position", "error", "D1"), ("equiv.position", "error", "R1"),
    ]  # fmt: skip
    code, _, err, _ = run(monkeypatch, tmp_path, *args[:-1], "other")
    assert code == 2 and err["code"] == "FEN-2001" and "holds no profile 'other'" in err["message"]
    assert err["hint"] == "profiles: moved"
    rules.write_text(EXCLUSIONS.replace("level = 4", "level = 1"), encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, *args)
    assert code == 3 and err["code"] == "FEN-3004" and "d1-rotation" in err["message"]
    code, _, err, _ = run(monkeypatch, tmp_path, *args[:-3], str(tmp_path / "no.toml"), "--profile", "moved")
    assert code == 3 and err["code"] == "FEN-3001"


def test_schematic_side_runs_levels_1_and_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(BLINK / "blink.SchDoc"), str(PCBDOC))
    result = env["result"]
    assert code == 0 and result["level"] == 2 and result["equivalent"] is True
    assert (result["sides"]["a"]["netlist_source"], result["sides"]["b"]["netlist_source"]) == (
        "circuit",
        "board",
    )
    assert (result["sides"]["a"]["backend"], result["sides"]["a"]["footprints"]) == ("altium", 0)
    assert result["levels"][1]["summary"]["sources"] == {"a": "circuit", "b": "board"}
    assert result["levels"][1]["compared"] == 36
    code, env, _, _ = run(monkeypatch, tmp_path, "equivalent", str(BLINK / "blink.PrjPcb"), str(PCBDOC))
    assert code == 0 and env["result"]["level"] == 4


# --- two backends, one design ----------------------------------------------------------------------

REMAINING: dict[str, str] = {}
"""The kinds of difference that remain between the KiCad board built from the blink and the PCB document
written from the same design, each with its cause. None remains: the document holds lengths in units of
2.54 nm, so a length differs from the KiCad file's by at most 1 nm (38 pad sizes and drills and 30 pad
positions at tolerance 0), which ``--tolerance-nm 1`` covers; the two files place the board at different
origins, which ``--frame relative`` removes."""


def _built_blink(tmp_path: Path) -> Path:
    board = tmp_path / "built" / "blink.kicad_pcb"
    board.parent.mkdir()
    board.write_bytes(build(blink(), 10).files["blink.kicad_pcb"])
    return board


def test_two_backends_one_design(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("equivalent started a subprocess")

    board = _built_blink(tmp_path)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    args = ("equivalent", str(board), str(PCBDOC), "--frame", "relative")
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--tolerance-nm", "1")
    result = env["result"]
    assert sorted({d["kind"] for d in result["differences"]}) == sorted(REMAINING), result["differences"]
    assert code == 0 and result["equivalent"] is True and result["level"] == 4
    assert (result["sides"]["a"]["backend"], result["sides"]["b"]["backend"]) == ("kicad", "altium")
    assert [lv["compared"] for lv in result["levels"]] == [3, 36, 36, 3]
    assert result["levels"][1]["summary"]["renamed"] == 0
    assert result["levels"][2]["summary"] == {"footprints": 3, "copper_unknown": 0}
    assert result["translation"] == [-74_600_000, -155_400_000]
    assert env["evidence"]["level"] == "INFERRED" and "H-K-PCB-READ" in env["evidence"]["hypotheses"]
    # without the tolerance only the rounding of the 2.54 nm unit shows, and nothing above level 2
    code, env, _, _ = run(monkeypatch, tmp_path, *args)
    kinds = {d["kind"] for d in env["result"]["differences"]}
    assert code == 5 and kinds == {"pad-size", "pad-drill", "pad-position", "position"}
    assert [lv["differences"] for lv in env["result"]["levels"]][:2] == [0, 0]
    # in the absolute frame every footprint differs by the origin of its file
    code, env, _, _ = run(monkeypatch, tmp_path, *args[:-2], "--tolerance-nm", "1")
    assert code == 5 and {d["kind"] for d in env["result"]["differences"]} == {"position"}
    assert len(env["result"]["differences"]) == 3


# --- the triangle, with a fake kicad-cli -----------------------------------------------------------

OUTPUT = (
    "Importing 'blink.PcbDoc' using Altium Designer format...\n"
    "07:06:18 PM: Warning: Layer 'Internal Plane 1' could not be mapped and will be skipped.\n"
    "07:06:18 PM: Warning: Layer 'Internal Plane 1' could not be mapped and will be skipped.\n"
    "19:06:18: Error: something else\n"
    "Successfully saved imported board to 'imported.kicad_pcb'\n"
)


def _fake(tmp_path: Path, version: str = "10.0.6", **options: Any) -> Path:
    return fake_kicad_cli(tmp_path / "bin", version=version, **options)


def _import_calls(fake: Path) -> list[list[str]]:
    return [call["args"] for call in calls(fake) if call["args"][:2] == ["pcb", "import"]]


def test_against_the_import_of_the_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _built_blink(tmp_path).read_text(encoding="utf-8")
    fake = _fake(tmp_path, imported=board, import_output=OUTPUT, import_warnings=["a report warning"])
    before = tree_snapshot(BLINK)
    args = ("equivalent", str(PCBDOC), "--against", "kicad-import", "--kicad-cli", str(fake))
    code, env, _, raw = run(monkeypatch, tmp_path, *args, "--tolerance-nm", "1")
    result = env["result"]
    assert code == 0, env["issues"]
    assert (result["equivalent"], result["level"], result["frame"]) == (True, 4, "relative")
    assert result["profile"]["name"] == "kicad-import" and result["profile"]["tool_version"] == "10.0"
    assert result["sides"]["a"]["backend"] == "altium" and len(result["sides"]["a"]["sha256"]) == 64
    assert result["sides"]["b"] == {
        "path": "blink.PcbDoc", "sha256": None, "backend": "kicad-import", "netlist_source": "board",
        "components": 3, "footprints": 3, "tool_version": "10.0.6",
    }  # fmt: skip
    assert result["translation"] == [74_600_000, 155_400_000]
    assert env["evidence"]["oracle"] == "kicad-cli" and env["evidence"]["level"] == "INFERRED"
    assert {"H-K-00", "H-K-PCB-READ"} <= set(env["evidence"]["hypotheses"])
    messages = [i["message"] for i in env["issues"] if i["code"] == "equiv.import-message"]
    assert messages == [
        "kicad-cli pcb import, 1 time(s): error: something else",
        "kicad-cli pcb import, 2 time(s): warning: Layer 'Internal Plane 1' could not be mapped and will be "
        "skipped.",
        "kicad-cli pcb import, 1 time(s): warning: a report warning",
    ]
    assert all(i["severity"] == "info" for i in env["issues"] if i["code"].startswith("equiv."))
    assert _import_calls(fake) == [
        ["pcb", "import", "--format", "altium", "--report-format", "json", "--report-file", "import.json",
         "-o", "imported.kicad_pcb", "blink.PcbDoc"]
    ]  # fmt: skip
    assert tree_snapshot(BLINK) == before and str(tmp_path) not in raw and "fenolite-kicad-" not in raw
    # an explicit option overrides the profile, as with two paths
    code, env, _, _ = run(monkeypatch, tmp_path, *args, "--frame", "absolute", "--tolerance-nm", "1")
    assert code == 5 and env["result"]["frame"] == "absolute"
    assert {i["code"] for i in env["issues"] if i["severity"] == "error"} == {"equiv.position"}


@pytest.mark.parametrize("version", ["9.0.9", "11.0.0"])
def test_against_needs_kicad_cli_10(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, version: str) -> None:
    fake = _fake(tmp_path, version=version, imported="(kicad_pcb)")
    code, env, err, _ = run(
        monkeypatch,
        tmp_path,
        "equivalent",
        str(PCBDOC),
        "--against",
        "kicad-import",
        "--kicad-cli",
        str(fake),
    )
    assert code == 6 and err["code"] == "FEN-6002" and "10.0" in err["hint"] and version in err["message"]
    assert env["ok"] is False and _import_calls(fake) == []


def test_against_without_a_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "equivalent", str(PCBDOC), "--against", "kicad-import")
    assert code == 6 and err["code"] == "FEN-6001"
    code, _, err, _ = run(
        monkeypatch, tmp_path, "equivalent", str(PCBDOC), "--against", "kicad-import", "--kicad-cli",
        str(tmp_path / "nowhere" / "kicad-cli"),
    )  # fmt: skip
    assert code == 6 and err["code"] == "FEN-6001"


def test_against_version_without_a_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = _built_blink(tmp_path).read_text(encoding="utf-8")
    fake = _fake(tmp_path, version="10.9.0", imported=board)
    code, env, _, _ = run(
        monkeypatch,
        tmp_path,
        "equivalent",
        str(PCBDOC),
        "--against",
        "kicad-import",
        "--kicad-cli",
        str(fake),
    )
    result = env["result"]
    warnings = [i for i in env["issues"] if i["code"] == "equiv.no-exclusion-profile"]
    assert len(warnings) == 1 and warnings[0]["severity"] == "warning" and "10.9.0" in warnings[0]["message"]
    assert result["profile"] is None and result["frame"] == "relative"
    assert result["tolerances"] == {"length_nm": 0, "angle_udeg": 0}
    assert result["sides"]["b"]["tool_version"] == "10.9.0"
    assert code == 5  # with no rule and no tolerance the rounding of the unit shows
    assert {d["kind"] for d in result["differences"]} == {"pad-size", "pad-drill", "pad-position", "position"}


@pytest.mark.parametrize("imported", [None, "(kicad_pcb", "(kicad_sch (version 20250114))"])
def test_against_oracle_failed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, imported: str | None) -> None:
    fake = _fake(tmp_path, imported=imported)
    code, env, err, raw = run(
        monkeypatch,
        tmp_path,
        "equivalent",
        str(PCBDOC),
        "--against",
        "kicad-import",
        "--kicad-cli",
        str(fake),
    )
    assert code == 5 and err["code"] == "FEN-5001"
    errors = [i for i in env["issues"] if i["severity"] == "error"]
    assert [(i["code"], i["where"]) for i in errors] == [("equiv.oracle-failed", "blink.PcbDoc")]
    result = env["result"]
    assert (result["equivalent"], result["level"], result["levels"], result["sides"]["b"]) == (
        False,
        0,
        [],
        None,
    )
    assert env["evidence"]["oracle"] == "kicad-cli" and str(tmp_path) not in raw
    if imported is None:
        assert "wrote no board (exit 0)" in errors[0]["message"]


def test_against_takes_no_exclusion_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rules = tmp_path / "rules.toml"
    rules.write_text(EXCLUSIONS, encoding="utf-8")
    fake = _fake(tmp_path, imported="(kicad_pcb)")
    args = ("equivalent", str(PCBDOC), "--against", "kicad-import", "--kicad-cli", str(fake))
    code, _, err, _ = run(monkeypatch, tmp_path, *args, "--exclusions", str(rules), "--profile", "moved")
    assert code == 2 and err["code"] == "FEN-2001" and _import_calls(fake) == []
    code, _, err, _ = run(
        monkeypatch, tmp_path, "equivalent", str(BLINK / "blink.SchDoc"), "--against", "kicad-import",
        "--kicad-cli", str(fake),
    )  # fmt: skip
    assert code == 2 and err["code"] == "FEN-2001" and _import_calls(fake) == []


def test_two_backends_design_type() -> None:
    """The registry reads both files of the two-backend case into designs."""
    for path in (TWO_LAYER, PCBDOC):
        backend = registry.for_path(path)
        assert backend is not None and isinstance(backend.read(path).content, Design)
