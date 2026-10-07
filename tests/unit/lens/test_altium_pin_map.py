# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pin-to-pad map in an Altium build (capabilities altium-build, "Pin maps in an Altium build";
altium-schematic-writer, "Pin map records of a footprint model"; altium-verification, "Pin maps in the
Altium round trips"; change c0123): pins of several pads, the two forms of the map records, RT-A2.

The defect of the releases 0.1.0 and 0.2.0 (a ``pad_map`` that renames a pad put the net of the pin on the
pad of the pin's own number) was fixed in 0.2.1 by change c0135, and its tests are in
``test_altium_pad_map.py``: a renaming map on the board, the refusals, the order of the records, the users
of one symbol that differ, a part of an Altium link, and ``check`` on a renaming map.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from _altium_built import build_altium_example
from _buildhelp import blink_variant

import fenolite.cli.main as cli_main
from fenolite.backends.altium.adapter.board import read_board
from fenolite.backends.altium.adapter.evidence import EVIDENCE
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.sch import MapDefiner, read_schematic
from fenolite.backends.altium.read.schlib import read_schlib

D1 = 'd1 = Part("D1", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")'
R1 = 'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")'
SWAPPED = D1.replace(")", ', pad_map={"1": "2", "2": "1"})')
"""The blink's LED with its pins on the other pads: pin 1 (on ``GND``) on pad 2."""
QFP = "Mini:Mini_QFP-32_7x7mm_P0.8mm"
BONDED = (
    f'r1 = Part("R1", "Mini:Mini_R", footprint="{QFP}", value="330", '
    'pad_map={"1": ("1", "5"), "2": ("7", "6")})'
)
"""The blink's resistor on a 32-pad footprint, each pin bonded to two pads."""
FORMS = {"binary": (), "ascii": ("--altium-format", "ascii")}


def built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, old: str, new: str, *flags: str) -> Path:
    script = blink_variant(tmp_path / "script", old, new)
    code, folder, error = build_altium_example(monkeypatch, tmp_path, script, *flags)
    assert code == 0, error
    return folder


def pad_nets(folder: Path) -> dict[tuple[str, str], str]:
    """(reference, pad number) → the name of the pad's net in the written PCB document, ``""`` for none."""
    (file,) = folder.glob("*.PcbDoc")
    parts = read_board(
        read_pcbdoc(file.read_bytes(), file=file.name),
        file=file.name,
        sha256="0" * 64,
        ids=Ids("altium_pcbdoc", EVIDENCE),
    )
    refs = {component.id: component.ref for component in parts.components}
    names = {net.id: net.name for net in parts.nets}
    return {
        (refs[footprint.component_id], pad.number): names.get(pad.net_id or "", "")
        for footprint in parts.board.footprints
        for pad in footprint.pads
    }


def map_records(folder: Path) -> dict[str, tuple[str, ...]]:
    """Pin designator → pads of every map record (record 47) of the written sheet."""
    (file,) = folder.glob("*.SchDoc")
    document = read_schematic(file.read_bytes(), file=file.name)
    return {r.interface: r.implementations for r in document.records if isinstance(r, MapDefiner)}


def library_maps(folder: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    """Library component → pin designator → pads of its map records; a component without a record is
    left out."""
    found: dict[str, dict[str, tuple[str, ...]]] = {}
    for file in sorted(folder.glob("*.SchLib")):
        for component in read_schlib(file.read_bytes(), file=file.name).components:
            records = component.of_type(MapDefiner)
            if records:
                found[component.name] = {r.interface: r.implementations for r in records}
    return found


def check_rta2(monkeypatch: pytest.MonkeyPatch, folder: Path) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", str(folder), "--stages", "roundtrip.rta2", "--json"])
    return code, json.loads(out.getvalue())


def test_pad_nets_of_a_pin_with_several_pads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Net on the mapped pads"."""
    nets = pad_nets(built(monkeypatch, tmp_path, R1, BONDED))
    assert nets[("R1", "1")] == nets[("R1", "5")] == "LED_DRV"
    assert nets[("R1", "7")] == nets[("R1", "6")] == "LED_A"
    assert nets[("R1", "2")] == "" and nets[("R1", "8")] == ""


@pytest.mark.parametrize("form", sorted(FORMS))
def test_map_records_read_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str) -> None:
    """Scenario "Map written and read back": one record 47 per pin whose pads are not its own alone, its
    pads in map order; a component without a map holds none."""
    folder = built(monkeypatch, tmp_path, R1, BONDED, *FORMS[form])
    assert map_records(folder) == {"1": ("1", "5"), "2": ("7", "6")}
    swapped = built(monkeypatch, tmp_path / "b", D1, SWAPPED, *FORMS[form])
    assert map_records(swapped) == {"1": ("2",), "2": ("1",)}
    # a design without a map writes no record 47
    assert map_records(built(monkeypatch, tmp_path / "c", "", "", *FORMS[form])) == {}


PARTLY = D1.replace(")", ', pad_map={"2": ("2", "5")})').replace('"Mini:Mini_LED_THT_3mm"', f'"{QFP}"')
"""The blink's LED on a 32-pad footprint: pin 2 bonded to two pads, pin 1 on the pad of its own number."""


@pytest.mark.parametrize("every_pin", [False, True])
def test_both_forms_of_the_map_records_read_back_alike(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, every_pin: bool
) -> None:
    """``altsym.MAP_RECORDS_FOR_EVERY_PIN``: the partial form (the default, what Altium saves) holds a
    record for the bonded pin alone, the full form one for each pin; both are imported to the same map and
    hold RT-A2."""
    from fenolite.backends.altium import altsym
    from fenolite.backends.altium.backend import AltiumBackend

    monkeypatch.setattr(altsym, "MAP_RECORDS_FOR_EVERY_PIN", every_pin)
    folder = built(monkeypatch, tmp_path, D1, PARTLY, "--altium-format", "ascii")
    expected = {"1": ("1",), "2": ("2", "5")} if every_pin else {"2": ("2", "5")}
    assert map_records(folder) == expected
    (sheet,) = folder.glob("*.SchDoc")
    d1 = next(c for c in AltiumBackend().read(sheet).design.circuit.components if c.ref == "D1")
    assert d1.pin_pad_map == (("2", "2"), ("2", "5"))
    code, env = check_rta2(monkeypatch, folder)
    assert code == 0, env["issues"]


@pytest.mark.parametrize("form", sorted(FORMS))
def test_rta2_compares_the_map(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str) -> None:
    """Scenario "Map inside RT-A2": the built project holds the level, with the map in the scope."""
    for index, (old, new) in enumerate(((R1, BONDED), (D1, SWAPPED))):
        folder = built(monkeypatch, tmp_path / str(index), old, new, *FORMS[form])
        code, env = check_rta2(monkeypatch, folder)
        assert code == 0, env["issues"]
        (stage,) = env["result"]["stages"]
        assert stage["summary"]["holds"] is True and stage["summary"]["differences"] == 0


def test_rta2_finds_a_lost_pad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The same scenario, second half: a sheet that lost one pad of a pin differs in ``pin_pad_map``."""
    folder = built(monkeypatch, tmp_path, R1, BONDED, "--altium-format", "ascii")
    (sheet,) = folder.glob("*.SchDoc")
    text = sheet.read_bytes()
    assert text.count(b"|DESIMPCOUNT=2|DESIMP0=1|DESIMP1=5") == 1
    sheet.write_bytes(text.replace(b"|DESIMPCOUNT=2|DESIMP0=1|DESIMP1=5", b"|DESIMPCOUNT=1|DESIMP0=1"))
    code, env = check_rta2(monkeypatch, folder)
    failed = [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    assert code == 5 and len(failed) == 1
    assert failed[0]["where"].startswith("schematic:") and failed[0]["where"].endswith("pin_pad_map")
    assert '["1","5"]' in failed[0]["message"]


def test_the_library_holds_the_map_onto_its_own_footprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A map is a map onto one footprint. The LED links the footprint its symbol names, which the library's
    footprint model (record 45) names too: the library holds its map. The resistor on the 32-pad footprint
    links another footprint than its symbol's own (``Mini_R_0603``): its map is on the sheet alone."""
    own = built(monkeypatch, tmp_path / "own", D1, SWAPPED, "--altium-format", "ascii")
    assert library_maps(own) == {"Mini_LED": {"1": ("2",), "2": ("1",)}}
    other = built(monkeypatch, tmp_path / "other", R1, BONDED, "--altium-format", "ascii")
    assert library_maps(other) == {}
    assert map_records(other) == {"1": ("1", "5"), "2": ("7", "6")}


@pytest.mark.parametrize("case", ["bonded"])
def test_check_knows_the_map(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: str) -> None:
    """``fenolite check`` of a project built from a script with a map compares the schematic and the board
    through the map: no ``netlist.assignment-differs``, exit 0, as for the project without a map. (The
    releases 0.2.x compare the schematic by pin number and the board by pad number, and report it.)"""
    old, new = {"bonded": (R1, BONDED)}[case]
    folder = built(monkeypatch, tmp_path, old, new)
    out = io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", io.StringIO())
        code = cli_main.main(["check", str(folder), "--json"])
    issues = json.loads(out.getvalue())["issues"]
    assert [i["message"] for i in issues if i["code"] == "netlist.assignment-differs"] == []
    assert code == 0, [i for i in issues if i["severity"] == "error"]
