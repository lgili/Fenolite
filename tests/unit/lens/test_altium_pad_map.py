# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium build applies ``pad_map``: to the nets of the PCB document, and as map records of the footprint
model in the schematic and its library (capability altium-build, "PCB document output").

The releases 0.1.0 and 0.2.0 keyed the nets of a component by pin number and the PCB document looked them
up by pad number, so a ``pad_map`` that renames a pad put each net on the pad of the pin's own number, and
the schematic said nothing of the map. The KiCad build of the same script applied the map.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _altium_built import build_altium_example
from _altium_padmap import D1, SWAPPED, pad_nets
from _buildhelp import blink as kicad_blink
from _buildhelp import blink_variant, build

from fenolite.backends.altium.read.sch import MapDefiner, read_schematic
from fenolite.backends.altium.read.schlib import read_schlib

BOARD = "design.board(mm(50), mm(30))\n"
FORMS = {"binary": (), "ascii": ("--altium-format", "ascii")}


def built(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, old: str, new: str, *flags: str, board: bool = True
) -> Path:
    script = blink_variant(tmp_path / "script", old, new)
    if not board:
        text = script.read_text(encoding="utf-8")
        assert BOARD in text
        script.write_text(text.replace(BOARD, ""), encoding="utf-8")
    code, folder, error = build_altium_example(monkeypatch, tmp_path, script, *flags)
    assert code == 0, error
    return folder


def sheet_maps(folder: Path) -> dict[str, tuple[str, ...]]:
    """Pin designator → pads of every map record (record 47) of the written sheet, as the reader of
    schematic documents gives them."""
    (file,) = folder.glob("*.SchDoc")
    document = read_schematic(file.read_bytes(), file=file.name)
    return {r.interface: r.implementations for r in document.records if isinstance(r, MapDefiner)}


def library_maps(folder: Path) -> dict[str, dict[str, tuple[str, ...]]]:
    """Library component → pin designator → pads of its map records, as the reader of schematic libraries
    gives them; a component without a record is left out."""
    found: dict[str, dict[str, tuple[str, ...]]] = {}
    for file in sorted(folder.glob("*.SchLib")):
        for component in read_schlib(file.read_bytes(), file=file.name).components:
            records = component.of_type(MapDefiner)
            if records:
                found[component.name] = {r.interface: r.implementations for r in records}
    return found


def test_pad_nets_follow_a_renaming_map(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With ``pad_map={"1": "2", "2": "1"}`` the net of pin 1 belongs on pad 2, and that of pin 2 on pad 1."""
    nets = pad_nets(built(monkeypatch, tmp_path, D1, SWAPPED))
    assert nets[("D1", "2")] == "GND" and nets[("D1", "1")] == "LED_A"
    # a part without a map is as it was
    assert nets[("R1", "1")] == "LED_DRV" and nets[("R1", "2")] == "LED_A"


def test_both_targets_agree_on_a_renaming_map(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The KiCad build of the same script puts the same nets on the pads of ``D1``."""
    design = kicad_blink()
    design.parts["D1"].pad_map = {"1": "2", "2": "1"}
    model = build(design).design
    board = model.board
    assert board is not None
    names = {net.id: net.name for net in model.circuit.nets}
    d1 = next(c for c in model.circuit.components if c.ref == "D1")
    (footprint,) = [f for f in board.footprints if f.component_id == d1.id]
    kicad = {pad.number: names.get(pad.net_id or "", "") for pad in footprint.pads if pad.number}
    altium = pad_nets(built(monkeypatch, tmp_path, D1, SWAPPED))
    assert kicad == {"1": "LED_A", "2": "GND"}
    assert {number: altium[("D1", number)] for number in kicad} == kicad


def test_a_script_without_a_map_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    nets = pad_nets(built(monkeypatch, tmp_path, "", ""))
    assert nets[("D1", "1")] == "GND" and nets[("D1", "2")] == "LED_A"


@pytest.mark.parametrize("form", sorted(FORMS))
def test_the_schematic_and_its_library_hold_the_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str
) -> None:
    """A renaming map is written as map records of the footprint model, one for each pin whose pad is not
    the pad of its own number, in the sheet and in the library, in both schematic forms; Fenolite's
    readers give the records back as written."""
    folder = built(monkeypatch, tmp_path, D1, SWAPPED, *FORMS[form])
    assert sheet_maps(folder) == {"1": ("2",), "2": ("1",)}
    assert library_maps(folder) == {"Mini_LED": {"1": ("2",), "2": ("1",)}}


def test_only_a_renamed_pin_gets_a_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A pin that the map leaves on the pad of its own number has no record, and neither has a pin outside
    the map: on the 32-pad footprint the resistor's pin 2 goes to pad 3 alone. The part links another
    footprint than its symbol's own (``Mini_R_0603``, which the library's footprint model names), so the
    library holds no map: a map is a map onto one footprint."""
    r1 = 'r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330")'
    mapped = r1.replace('"Mini:Mini_R_0603"', '"Mini:Mini_QFP-32_7x7mm_P0.8mm"').replace(
        ")", ', pad_map={"1": "1", "2": "3"})'
    )
    folder = built(monkeypatch, tmp_path, r1, mapped, "--altium-format", "ascii")
    assert sheet_maps(folder) == {"2": ("3",)}
    assert library_maps(folder) == {}
    nets = pad_nets(folder)
    assert nets[("R1", "1")] == "LED_DRV" and nets[("R1", "3")] == "LED_A" and nets[("R1", "2")] == ""


@pytest.mark.parametrize("form", sorted(FORMS))
def test_a_script_without_a_map_writes_no_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str
) -> None:
    folder = built(monkeypatch, tmp_path, "", "", *FORMS[form])
    assert sheet_maps(folder) == {} and library_maps(folder) == {}


@pytest.mark.parametrize("form", sorted(FORMS))
def test_a_design_without_a_board_keeps_the_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str
) -> None:
    """Without a board no PCB document is written: the map records of the schematic are then the only
    place of the map, where the releases 0.1.0 and 0.2.0 wrote none."""
    folder = built(monkeypatch, tmp_path, D1, SWAPPED, *FORMS[form], board=False)
    assert not list(folder.glob("*.PcbDoc"))
    assert sheet_maps(folder) == {"1": ("2",), "2": ("1",)}
    assert library_maps(folder) == {"Mini_LED": {"1": ("2",), "2": ("1",)}}


@pytest.mark.parametrize(
    ("pad_map", "named"),
    [('{"1": "TAB"}', "the pad TAB"), ('{"9": "1"}', "the pin 9")],
)
def test_a_map_that_names_a_missing_pin_or_pad_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, pad_map: str, named: str
) -> None:
    """``altium.pin-pad-map-invalid``: exit 5, the component's path as ``where``, and no file."""
    import io
    import json
    import sys

    import fenolite.cli.main as cli_main

    script = blink_variant(tmp_path / "script", D1, D1.replace(")", f", pad_map={pad_map})"))
    folder = tmp_path / "built"
    out = io.StringIO()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", io.StringIO())
        args = ["build", str(script), "--out", str(folder), "--target", "altium", "--confirm", "--json"]
        assert cli_main.main(args) == 5
    found = [i for i in json.loads(out.getvalue())["issues"] if i["code"] == "altium.pin-pad-map-invalid"]
    assert [i["severity"] for i in found] == ["error"] and named in found[0]["message"]
    assert found[0]["where"] == "D1" and not folder.exists()


SAME_NET = (
    "connect(gnd, u1[10], d1[1])\nconnect(led_drv, u1[1], r1[1])\nconnect(led_a, r1[2], d1[2])",
    "connect(gnd, u1[10], d1[1], d1[2])\nconnect(led_drv, u1[1], r1[1])\nconnect(led_a, r1[2])",
)
"""The blink's connections, and the same with both pins of ``D1`` on ``GND``."""


@pytest.mark.parametrize("pad_map", ['{"1": "2"}', '{"2": "1"}'], ids=["pin-1-on-pad-2", "pin-2-on-pad-1"])
@pytest.mark.parametrize("same_net", [False, True], ids=["two-nets", "one-net"])
def test_a_pad_that_two_pins_stand_for_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, same_net: bool, pad_map: str
) -> None:
    """``pad_map={"1": "2"}`` on the two-pin LED leaves pad 2 to the pins 1 and 2: one issue names the pad
    and both pins, on two nets and on one net alike, and nothing is written. The KiCad build refuses the
    same script, so the two targets stay alike; the map that lists one pad for two pins is refused by
    ``Part`` before any build."""
    import io
    import json
    import sys

    import fenolite.cli.main as cli_main
    from fenolite.dsl import DslError, Part

    script = blink_variant(tmp_path / "script", D1, D1.replace(")", f", pad_map={pad_map})"))
    pad = "2" if pad_map == '{"1": "2"}' else "1"
    if same_net:
        text = script.read_text(encoding="utf-8")
        assert SAME_NET[0] in text
        script.write_text(text.replace(*SAME_NET), encoding="utf-8")
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    codes: dict[str, list[dict[str, str]]] = {}
    for target, flags in (("altium", ("--target", "altium")), ("kicad", ("--kicad-version", "10"))):
        folder = tmp_path / target
        out = io.StringIO()
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", out)
            patch.setattr(sys, "stderr", io.StringIO())
            args = ["build", str(script), "--out", str(folder), *flags, "--confirm", "--json"]
            assert cli_main.main(args) == 5, target
        assert not folder.exists(), target
        codes[target] = [i for i in json.loads(out.getvalue())["issues"] if "pin-pad-map" in i["code"]]
    (found,) = codes["altium"]
    assert (found["code"], found["severity"], found["where"]) == ("altium.pin-pad-map-invalid", "error", "D1")
    assert "the pins 1 and 2" in found["message"] and f"the pad {pad}" in found["message"]
    assert [i["code"] for i in codes["kicad"]] == ["build.pin-pad-map-invalid"]
    with pytest.raises(DslError, match="more than one pin"):
        Part("X1", "Lib:S", pad_map={"1": "3", "2": "3"})


def test_the_records_follow_the_pins_of_the_symbol(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The records are written in the order of the symbol's pins, whatever the order of the script's map,
    in the sheet and in the library."""
    backwards = D1.replace(")", ', pad_map={"2": "1", "1": "2"})')
    folder = built(monkeypatch, tmp_path, D1, backwards, "--altium-format", "ascii")
    (sheet,) = folder.glob("*.SchDoc")
    document = read_schematic(sheet.read_bytes(), file=sheet.name)
    assert [r.interface for r in document.records if isinstance(r, MapDefiner)] == ["1", "2"]
    (library,) = folder.glob("*.SchLib")
    (led,) = [
        c for c in read_schlib(library.read_bytes(), file=library.name).components if c.name == "Mini_LED"
    ]
    assert [r.interface for r in led.of_type(MapDefiner)] == ["1", "2"]


def test_no_library_map_when_the_users_of_a_symbol_differ(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two LEDs of one symbol, one with a map and one without: the library component is one for both, so it
    holds no map; the sheet holds the map of the part that has one."""
    second = (
        SWAPPED
        + '\nd2 = Part("D2", "Mini:Mini_LED", footprint="Mini:Mini_LED_THT_3mm", value="LED")'
        + "\ndesign.add(d2)"
    )
    folder = built(monkeypatch, tmp_path, D1, second, "--altium-format", "ascii")
    assert library_maps(folder) == {}
    assert sheet_maps(folder) == {"1": ("2",), "2": ("1",)}


def test_a_repeated_pin_number_and_a_generic_pin_are_no_findings() -> None:
    """``pin_map_issues`` on models a script cannot make but an API caller can: a pin number that the
    component lists twice is one pin, not two pins on one pad; and for a part of an Altium link, whose
    pins are the designators its nets use, a mapped pin that no net uses is not a pin the symbol lacks."""
    from fenolite.lens.altium import pin_map_issues
    from fenolite.model.circuit import Circuit, Component, Pin
    from fenolite.model.design import Design

    def pins(*numbers: str) -> tuple[Pin, ...]:
        return tuple(
            Pin(id=f"pin_00000000-0000-4000-8000-{index:012d}", number=number)
            for index, number in enumerate(numbers)
        )

    def issues_of(component: Component) -> list[str]:
        design = dataclasses.replace(Design.new("d", seed=1), circuit=Circuit(components=(component,)))
        return [found.message for found in pin_map_issues(design, {})]

    base = {"id": "cmp_00000000-0000-4000-8000-000000000001", "ref": "U1", "lib_footprint_ref": "L:F"}
    twice = Component(lib_symbol_ref="Mini:X", pins=pins("1", "2", "2"), pin_pad_map=(("1", "3"),), **base)
    assert issues_of(twice) == []
    shared = Component(lib_symbol_ref="Mini:X", pins=pins("1", "2"), pin_pad_map=(("1", "2"),), **base)
    assert issues_of(shared) == ["U1: the pins 1 and 2 both stand for the pad 2"]
    missing = Component(lib_symbol_ref="Mini:X", pins=pins("1"), pin_pad_map=(("9", "3"),), **base)
    assert issues_of(missing) == ["U1: the pin-to-pad map names the pin 9, which the symbol lacks"]
    generic = Component(lib_symbol_ref="My.SchLib:X", pins=pins("1"), pin_pad_map=(("9", "3"),), **base)
    assert issues_of(generic) == []


def test_check_compares_a_built_project_through_the_map(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``fenolite check`` of a project built from a script with a renaming ``pad_map`` exits 0 and reports
    no ``netlist.assignment-differs``, as for a project without a map: the import reads the map records of
    the schematic into ``Component.pin_pad_map`` (change c0083) and the comparison names a pin by its pad.

    On the 0.2.x line this test was ``test_check_still_compares_the_schematic_by_pin`` and pinned the
    opposite, a stated limit of 0.2.1: there the import leaves the records out of the model, so the
    schematic is compared by pin number and the board by pad number, and a correct project is reported
    (exit 5). The development line never had that limit once the build wrote the records."""
    import io
    import json
    import sys

    import fenolite.cli.main as cli_main

    def check(folder: Path) -> tuple[int, list[str]]:
        out = io.StringIO()
        with monkeypatch.context() as patch:
            patch.setattr(sys, "stdout", out)
            patch.setattr(sys, "stderr", io.StringIO())
            code = cli_main.main(["check", str(folder), "--json"])
        issues = json.loads(out.getvalue())["issues"]
        return code, [i["message"] for i in issues if i["code"] == "netlist.assignment-differs"]

    code, differs = check(built(monkeypatch, tmp_path / "map", D1, SWAPPED))
    assert code == 0 and differs == []
    code, differs = check(built(monkeypatch, tmp_path / "plain", "", ""))
    assert code == 0 and differs == []
