# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT-A2 on every example build (capability altium-verification, "Round-trip level RT-A2" and "RT-A2 on a
written model"; changes c0044 and c0090): each script under ``examples/`` is built for the Altium target
into ``tmp_path``, in the binary and in the ASCII schematic form, and ``fenolite check --stages
roundtrip.rta2`` judges the level. Since c0090 the stored model holds the board that was written, so
footprints, pads and copper are compared and no kind is only counted. Evidence of level INFERRED
(``H-A-VER-RTA2-3``): Fenolite's writers read by Fenolite's readers. An example that no Altium build
writes is named in ``REFUSED`` with the measured reason, and is held to that reason where the official
libraries are installed."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from _altium_built import BLINK, EXAMPLES, LIBRARY_VARIABLES, build_altium_example, built_blink

import fenolite.cli.main as cli_main
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.cfb import Storage, write_compound
from fenolite.backends.altium.read import cfb as read_cfb
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.roundtrip import RT_A2_SCOPE
from fenolite.checks.rta2 import CIRCUIT_KINDS
from fenolite.model.canonical import dump_texts, load_dir

FORMS = {"binary": (), "ascii": ("--altium-format", "ascii")}
OFFICIAL = "blink_official/design.py"
"""The one example that needs the official KiCad libraries: built only where they are installed."""
WITH_PCB = {
    "altium_hier_board/design.py",
    "blink_2layer/design.py",
    "blink_official/design.py",
    "blink_routed/design.py",
    "board_40parts/design.py",
}
"""The examples whose build writes a PCB document."""
SCHEMATIC_ONLY = {
    "altium_hier/design.py",
    "altium_hier/partial.py",
    "altium_kicad/design.py",
    "altium_kicad/no_connect.py",
    "altium_sample/design.py",
}
REFUSED = {
    "yardstick/design.py": (
        "needs the official KiCad libraries, and with them the Altium build is refused in both forms: "
        "altium.text-unwritable on the description of Isolator_Analog:AMC1200BDWV, which holds U+00B1"
    ),
}
"""The examples that no Altium build writes, each with the reason as measured (10.0.6 libraries,
2026-10-08): nothing is written, so there is nothing for RT-A2 to judge. ``test_refused_example_is_refused``
holds each entry to its reason where the libraries are installed, so that an example which starts to build
fails there and is moved to ``WITH_PCB`` or ``SCHEMATIC_ONLY``."""
SCRIPTS = sorted(path.relative_to(EXAMPLES).as_posix() for path in EXAMPLES.glob("*/*.py"))
PCB_KINDS = sorted(kind for kind in RT_A2_SCOPE.fields if kind not in CIRCUIT_KINDS)
"""The kinds compared with the PCB reading: every other kind of the scope."""
ROUTED = EXAMPLES / "blink_routed" / "design.py"


def _check(monkeypatch: pytest.MonkeyPatch, folder: Path) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", str(folder), "--stages", "roundtrip.rta2", "--json"])
    return code, json.loads(out.getvalue())


def _judge(monkeypatch: pytest.MonkeyPatch, folder: Path, *, pcb: bool) -> dict[str, Any]:
    code, env = _check(monkeypatch, folder)
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"]) == ("roundtrip.rta2", "ok")
    summary = stage["summary"]
    assert summary["level"] == "RT-A2" and summary["holds"] is True and summary["differences"] == 0
    assert summary["compared"]["schematic"] == sorted(CIRCUIT_KINDS)
    assert ("pcb" in summary["compared"]) is pcb
    assert stage["evidence"]["level"] == "INFERRED"
    assert "H-A-VER-RTA2-3" in stage["evidence"]["hypotheses"]
    assert "not_in_model" not in summary  # no kind is only counted
    assert not [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    return summary


def test_every_example_is_classified() -> None:
    """A new script under ``examples/`` must be named here, so that it is built and judged."""
    assert set(SCRIPTS) == WITH_PCB | SCHEMATIC_ONLY | set(REFUSED)
    assert not WITH_PCB & SCHEMATIC_ONLY and not (WITH_PCB | SCHEMATIC_ONLY) & set(REFUSED)
    assert all(reason for reason in REFUSED.values())


@pytest.mark.parametrize("form", sorted(FORMS))
@pytest.mark.parametrize("script", [s for s in SCRIPTS if s != OFFICIAL and s not in REFUSED])
def test_example_holds_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: str, form: str) -> None:
    code, folder, error = build_altium_example(monkeypatch, tmp_path, EXAMPLES / script, *FORMS[form])
    assert code == 0, error
    summary = _judge(monkeypatch, folder, pcb=script in WITH_PCB)
    if script in WITH_PCB:
        # the stored model holds the board that was written: every kind of the scope is compared
        assert summary["compared"]["pcb"] == PCB_KINDS
        board = load_dir(folder / ".fenolite").board
        assert board is not None and len(board.footprints) >= 3
        assert sum(len(footprint.pads) for footprint in board.footprints) >= 3


def test_module_sheets_hold_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = EXAMPLES / "altium_hier" / "design.py"
    code, folder, error = build_altium_example(monkeypatch, tmp_path, script, "--altium-sheets", "modules")
    assert code == 0, error
    assert len(list(folder.glob("*.SchDoc"))) > 1
    _judge(monkeypatch, folder, pcb=False)


@pytest.mark.needs_libs
@pytest.mark.parametrize("form", sorted(FORMS))
def test_official_example_holds_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str) -> None:
    code, folder, error = build_altium_example(monkeypatch, tmp_path, EXAMPLES / OFFICIAL, *FORMS[form])
    if code != 0:
        pytest.skip(f"the official libraries do not resolve here: {error[:200]}")
    _judge(monkeypatch, folder, pcb=True)


@pytest.mark.needs_libs
@pytest.mark.parametrize("form", sorted(FORMS))
@pytest.mark.parametrize("script", sorted(REFUSED))
def test_refused_example_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: str, form: str
) -> None:
    """An example of ``REFUSED`` is still refused for the reason its entry states: the build ends with
    findings, every error is the code that the reason names, and no file is written."""
    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in LIBRARY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    folder = tmp_path / "built"
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        args = ["build", str(EXAMPLES / script), "--out", str(folder), "--target", "altium", *FORMS[form]]
        code = cli_main.main([*args, "--confirm", "--json"])
    if code == 3:
        pytest.skip(f"the official libraries do not resolve here: {err.getvalue()[:200]}")
    assert code == 5, err.getvalue()
    errors = [i for i in json.loads(out.getvalue())["issues"] if i["severity"] == "error"]
    assert errors and all(i["code"] in REFUSED[script] and i["where"] in REFUSED[script] for i in errors)
    assert not folder.exists() or not any(folder.iterdir())


def test_built_blink_holds_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Built blink holds RT-A2"."""
    folder = built_blink(monkeypatch, tmp_path)
    summary = _judge(monkeypatch, folder, pcb=True)
    assert summary["compared"] == {"schematic": ["component", "net", "no_connect"], "pcb": PCB_KINDS}
    board = load_dir(folder / ".fenolite").board
    assert board is not None
    assert (len(board.footprints), sum(len(fp.pads) for fp in board.footprints)) == (3, 36)


def test_changed_document_is_caught_in_the_built_blink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "A changed document is caught": the stored model gives R1 another value."""
    folder = built_blink(monkeypatch, tmp_path)
    circuit = folder / ".fenolite" / "circuit.json"
    text = circuit.read_text(encoding="utf-8")
    assert text.count('"value": "330"') == 1 and BLINK.is_file()
    circuit.write_text(text.replace('"value": "330"', '"value": "470"'), encoding="utf-8", newline="\n")
    code, env = _check(monkeypatch, folder)
    assert code == 5
    failed = [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    assert [(i["severity"], i["where"]) for i in failed] == [("error", "schematic:/component/R1/value")]
    assert '"470"' in failed[0]["message"] and '"330"' in failed[0]["message"]
    summary = env["result"]["stages"][0]["summary"]
    assert (summary["holds"], summary["differences"]) == (False, 1)


def test_built_model_stores_the_written_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Regression (found by RT-A2): a component whose value is empty in the script is written with its
    symbol's name as the comment, and the built model stores that value."""
    script = EXAMPLES / "altium_sample" / "design.py"
    code, folder, error = build_altium_example(monkeypatch, tmp_path, script)
    assert code == 0, error
    model = load_dir(folder / ".fenolite")
    assert 'Part("J1"' in script.read_text(encoding="utf-8")
    assert model.by_ref["J1"].value == "HDR2"
    assert all(component.value for component in model.circuit.components)


def _move_first_track(document: Path) -> None:
    """Move the first free track of the PCB document by one mil in X, by an edit of its record."""
    data = document.read_bytes()
    read = read_pcbdoc(data, file=document.name)
    index = next(i for i, track in enumerate(read.tracks) if track.prefix.component is None)
    track = read.tracks[index]
    moved = rec.track_record(
        track.prefix.layer,
        (track.x1 + rec.UNITS_PER_MIL, track.y1),
        (track.x2 + rec.UNITS_PER_MIL, track.y2),
        track.width,
        net=track.prefix.net if track.prefix.net is not None else rec.NO_INDEX,
    )
    raws, trailing = read.parts["Tracks6"]
    stream = b"".join(moved if i == index else raws[i] for i in range(len(raws))) + trailing

    def replaced(entries: Any) -> tuple[Any, ...]:
        out: list[Any] = []
        for entry in entries:
            if isinstance(entry, Storage):
                inner = entry.entries
                if entry.name == "Tracks6":
                    inner = tuple((name, stream if name == "Data" else content) for name, content in inner)
                out.append(Storage(entry.name, replaced(inner) if entry.name != "Tracks6" else inner))
            else:
                out.append(entry)
        return tuple(out)

    document.write_bytes(write_compound(replaced(read_cfb.open_compound(data, file=document.name).tree())))


def test_moved_track_is_caught(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Copper compared" (change c0090): one track of the routed blink's PCB document is moved by
    a record edit, and the stage names a track."""
    code, folder, error = build_altium_example(monkeypatch, tmp_path, ROUTED)
    assert code == 0, error
    _judge(monkeypatch, folder, pcb=True)
    _move_first_track(folder / "blink_routed.PcbDoc")
    code, env = _check(monkeypatch, folder)
    assert code == 5
    failed = [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    assert failed and {i["where"].split("/")[1] for i in failed} == {"track"}
    assert all(i["where"].startswith("pcb:/track/") and i["severity"] == "error" for i in failed)
    assert env["result"]["stages"][0]["summary"]["holds"] is False


def test_model_without_the_board_is_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A stored model that predates change c0090 holds no footprint while the PCB document holds some:
    the stage is skipped with ``model-predates-board`` and reports nothing."""
    folder = built_blink(monkeypatch, tmp_path)
    model = load_dir(folder / ".fenolite")
    assert model.board is not None
    import dataclasses

    old = dataclasses.replace(model, board=dataclasses.replace(model.board, footprints=()))
    for name, text in dump_texts(old).items():
        (folder / ".fenolite" / name).write_text(text, encoding="utf-8", newline="\n")
    code, env = _check(monkeypatch, folder)
    (stage,) = env["result"]["stages"]
    assert code == 0 and (stage["status"], stage["reason"]) == ("skipped", "model-predates-board")


# --- footprint graphics (change c0126, capability altium-verification, "Footprint graphics in the Altium
# round trips") -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("script", sorted(WITH_PCB - {OFFICIAL}))
def test_every_example_compares_its_footprint_graphics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: str
) -> None:
    """Scenario "Every example compares its footprint graphics": the kind ``footprint_graphic`` is compared
    with 0 differences (``_judge``), and the stored board holds the graphics that the document draws for
    each footprint, and the corner ratio of each rounded pad."""
    code, folder, error = build_altium_example(monkeypatch, tmp_path, EXAMPLES / script)
    assert code == 0, error
    summary = _judge(monkeypatch, folder, pcb=True)
    assert "footprint_graphic" in summary["compared"]["pcb"]
    board = load_dir(folder / ".fenolite").board
    assert board is not None and board.footprints
    assert all(footprint.graphics for footprint in board.footprints)
    rounded = [pad for footprint in board.footprints for pad in footprint.pads if pad.shape == "roundrect"]
    assert all(pad.corner_ratio is not None and pad.corner_ratio % 5_000 == 0 for pad in rounded)


def _move_component_track(document: Path, designator: str) -> None:
    """Move the first track of the component ``designator`` by one mil in X, by an edit of its record."""
    data = document.read_bytes()
    read = read_pcbdoc(data, file=document.name)
    owner = next(i for i, item in enumerate(read.components) if item.source_designator == designator)
    index = next(i for i, track in enumerate(read.tracks) if track.prefix.component == owner)
    track = read.tracks[index]
    moved = rec.track_record(
        track.prefix.layer,
        (track.x1 + rec.UNITS_PER_MIL, track.y1),
        (track.x2 + rec.UNITS_PER_MIL, track.y2),
        track.width,
        component=owner,
    )
    raws, trailing = read.parts["Tracks6"]
    stream = b"".join(moved if i == index else raws[i] for i in range(len(raws))) + trailing

    def replaced(entries: Any) -> tuple[Any, ...]:
        out: list[Any] = []
        for entry in entries:
            if isinstance(entry, Storage):
                inner = entry.entries
                if entry.name == "Tracks6":
                    inner = tuple((name, stream if name == "Data" else content) for name, content in inner)
                out.append(Storage(entry.name, replaced(inner) if entry.name != "Tracks6" else inner))
            else:
                out.append(entry)
        return tuple(out)

    document.write_bytes(write_compound(replaced(read_cfb.open_compound(data, file=document.name).tree())))


def test_moved_silkscreen_line_is_caught(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A moved silkscreen line is caught": one overlay track of ``R1`` in the built blink is moved
    by a record edit, and every ``check.rta2-failed`` is under ``pcb:/footprint_graphic/``."""
    folder = built_blink(monkeypatch, tmp_path)
    _judge(monkeypatch, folder, pcb=True)
    _move_component_track(folder / "blink.PcbDoc", "R1")
    code, env = _check(monkeypatch, folder)
    assert code == 5
    failed = [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    assert failed and all(i["where"].startswith("pcb:/footprint_graphic/") for i in failed)
    assert env["result"]["stages"][0]["summary"]["holds"] is False


def test_model_without_graphics_is_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A stored model that predates change c0126 holds footprints without graphics while the PCB document
    draws some: the stage is skipped with ``model-predates-graphics`` and reports nothing."""
    import dataclasses

    folder = built_blink(monkeypatch, tmp_path)
    model = load_dir(folder / ".fenolite")
    assert model.board is not None
    footprints = tuple(dataclasses.replace(fp, graphics=()) for fp in model.board.footprints)
    old = dataclasses.replace(model, board=dataclasses.replace(model.board, footprints=footprints))
    for name, text in dump_texts(old).items():
        (folder / ".fenolite" / name).write_text(text, encoding="utf-8", newline="\n")
    code, env = _check(monkeypatch, folder)
    (stage,) = env["result"]["stages"]
    assert code == 0 and (stage["status"], stage["reason"]) == ("skipped", "model-predates-graphics")
    assert not [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
