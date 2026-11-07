# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Device records (change c0248; capability fenolite-component-catalog, "Device records" to "Device
provenance and edits"). The records of ``tests/data/devices`` are authored for Fenolite and illustrative."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.catalog import get_footprint, get_symbol
from fenolite.catalog.devices import (
    DeviceFormatError,
    DeviceFormatTooNewError,
    check_device,
    device_digest,
    device_text,
    is_edited,
    load_devices,
    parse_device,
    shipped_device,
    shipped_devices,
    stamped,
)
from fenolite.core.errors import FormatError
from fenolite.model import canonical
from fenolite.model.library import (
    DeviceDef,
    FootprintDef,
    Pad,
    PinPairLimit,
    Rating,
    SymbolDef,
    SymbolPin,
    Threshold,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "devices"
BUCK = DATA / "example_buck.toml"
AUTHORED = "# Authored for Fenolite"

MINIMAL = """\
schema = "fenolite.device.v0"
id = "Proj:X"
summary = "Two-pin test device"
symbol = "Fenolite:Resistor"
footprint = "Fenolite:Chip_0603"
evidence = "UNVERIFIED"
{extra}
[pins]
{pins}
"""


def _record(extra: str = "", pins: str = 'A = "1"\nB = "2"') -> str:
    return MINIMAL.format(extra=extra, pins=pins)


def _refused(text: str, code: str = "FEN-3004") -> FormatError:
    with pytest.raises(FormatError) as caught:
        parse_device(text, file="devices/x.toml")
    assert getattr(caught.value, "code", None) == code, caught.value
    return caught.value


def _floats(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_floats(item) for item in value.values())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, list):
        return any(_floats(item) for item in value)  # pyright: ignore[reportUnknownVariableType]
    return False


def _all_records() -> list[tuple[str, DeviceDef]]:
    found = [
        (path.name, parse_device(path.read_text(encoding="utf-8"), file=path.name))
        for path in sorted(DATA.glob("*.toml"))
    ]
    return found + [(device.id, device) for device in shipped_devices()]


# -- reading


def test_read_a_device_record() -> None:
    device = parse_device(BUCK.read_text(encoding="utf-8"), file="example_buck.toml")
    assert (device.id, device.symbol, device.footprint) == (
        "Example:BUCK_6V_2A",
        "Example:Buck_6pin",
        "Fenolite:SOT23_6_TI_DBV0006A",
    )
    assert device.value == "EXB6202" and device.ref_prefix == "U" and device.ground == "GND"
    assert not _floats(json.loads(canonical.dumps(device)))


def test_every_test_record_opens_with_the_authored_line() -> None:
    for path in sorted(DATA.glob("*.toml")):
        assert AUTHORED in path.read_text(encoding="utf-8").splitlines()[1], path


def test_unknown_key() -> None:
    error = _refused(_record('colour = "red"\n'))
    assert "colour" in str(error) and "devices/x.toml" in str(error)


def test_shipped_namespace_needs_sources() -> None:
    error = _refused(_record().replace('"Proj:X"', '"Fenolite:X"'))
    assert "sources" in str(error)
    assert parse_device(_record('sources = ["S-0314"]\n').replace('"Proj:X"', '"Fenolite:X"')).sources == (
        "S-0314",
    )


def test_options_table_form_is_malformed() -> None:
    """``options`` is defined by change c0257 as ``[[options]]``; a plain table is a malformed record."""
    error = _refused(_record('[options]\nI2C = "x"\n'))
    assert "options" in str(error) and not isinstance(error, DeviceFormatTooNewError)


def test_newer_schema() -> None:
    _refused(_record().replace("fenolite.device.v0", "fenolite.device.v1"), "FEN-3002")
    _refused(_record().replace("fenolite.device.v0", "other.v0"))


def test_missing_key_and_wrong_type() -> None:
    assert "summary" in str(_refused(_record().replace('summary = "Two-pin test device"\n', "")))
    assert "summary" in str(_refused(_record().replace('"Two-pin test device"', "2")))
    assert "datasheet" in str(_refused(_record('datasheet = "http://example.invalid/x.pdf"\n')))
    assert "ref_prefix" in str(_refused(_record('ref_prefix = "r1"\n')))
    assert "evidence" in str(_refused(_record().replace('"UNVERIFIED"', '"MAYBE"')))
    assert "id" in str(_refused(_record().replace('"Proj:X"', '"no namespace"')))


def test_three_spellings() -> None:
    pins = 'BST = "1"\nGND = { map = { "2" = ["2", "EP"] } }\nVIN = { pins = ["5"] }'
    device = parse_device(_record('ref_prefix = "U"\n', pins))
    assert device.pin("BST").pin_pads == (("1", "1"),)
    assert device.pin("GND").pin_pads == (("2", "2"), ("2", "EP"))
    assert device.pin("VIN").pin_pads == (("5", "5"),)


def test_pins_in_code_point_order() -> None:
    device = parse_device(_record(pins='VIN = "5"\nBST = "1"\nGND = "2"'))
    assert [pin.function for pin in device.pins] == ["BST", "GND", "VIN"]


@pytest.mark.parametrize(
    ("pins", "named"),
    [
        ('VIN = "1"\nEN = "1"', "EN"),
        ('vin = "1"\nVIN = "2"', "VIN"),
        ('1V8 = "1"', "1V8"),
        ('GND = { pins = ["2"], map = { "2" = "2" } }', "GND"),
        ('A = "1"\nB = { map = { "2" = "1" } }', "B"),
        ('A = { pins = ["1"], colour = "red" }', "colour"),
    ],
)
def test_refused_pin_tables(pins: str, named: str) -> None:
    assert named in str(_refused(_record(pins=pins)))


def test_ratings_read_exactly() -> None:
    device = parse_device(BUCK.read_text(encoding="utf-8"))
    vin = device.pin("VIN")
    assert vin.ratings == (
        Rating("voltage", "uV", None, 6_500_000, "abs_max"),
        Rating("voltage", "uV", 2_700_000, 6_000_000, "operating"),
    )
    assert device.rating("temperature", "operating") == Rating(
        "temperature", "mK", 233_150, 398_150, "operating"
    )
    assert device.rating("temperature") == Rating("temperature", "mK", 218_150, 423_150)
    assert device.pin("EN").must_connect and not device.pin("FB").must_connect


@pytest.mark.parametrize(
    "ratings",
    [
        'voltage = { abs_max = "6.0000005V" }',
        'current = { abs_max = "6V" }',
        'power = { abs_max = { min = "2W", max = "1W" } }',
        "power = { abs_max = { max = 2 } }",
        "power = { abs_max = 2.5 }",
        'colour = { abs_max = "1V" }',
        'voltage = { abs_max = { typ = "1V" } }',
        'voltage = { typical = "1V" }',
        "voltage = { }",
        'voltage = "6V"',
    ],
)
def test_refused_ratings(ratings: str) -> None:
    _refused(_record() + f"\n[ratings]\n{ratings}\n")


# -- limits, thresholds and class (change c0274, tasks 2.1 and 2.2)

LIMITED = 'VIN = { pins = ["5"], voltage = { operating = { min = "2.7V", max = "6V" }, abs_max = "6.5V" } }'


def test_limits_both_kinds_on_one_pin() -> None:
    device = parse_device(_record('ref_prefix = "U"\n', LIMITED))
    vin = device.pin("VIN")
    assert vin.rating("voltage") == Rating("voltage", "uV", None, 6_500_000, "abs_max")
    assert vin.rating("voltage", "operating") == Rating("voltage", "uV", 2_700_000, 6_000_000, "operating")


def test_limits_ambiguous_form_is_refused() -> None:
    error = _refused(_record(pins='VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }'))
    assert "VIN" in str(error) and "abs_max" in str(error) and "operating" in str(error)
    assert "abs_max" in getattr(error, "hint", "") and "operating" in getattr(error, "hint", "")
    error = _refused(_record(pins='VIN = { pins = ["5"], voltage = { operating = "7V", abs_max = "6.5V" } }'))
    assert "VIN" in str(error) and "outside" in str(error)
    _refused(_record() + '\n[ratings]\ncurrent = { min = "1A" }\n')


def test_limits_celsius_and_kelvin_agree() -> None:
    celsius = parse_device(
        _record() + '\n[ratings]\ntemperature = { operating = { min = "-40degC", max = "125degC" } }\n'
    )
    kelvin = parse_device(
        _record() + '\n[ratings]\ntemperature = { operating = { min = "233.15K", max = "398.15K" } }\n'
    )
    assert celsius == kelvin
    assert celsius.ratings == (Rating("temperature", "mK", 233_150, 398_150, "operating"),)
    _refused(_record() + '\n[ratings]\ntemperature = { operating = { min = "-40.0001degC" } }\n')
    assert 'min = "-40degC", max = "125degC"' in device_text(kelvin)


def test_limits_bootstrap_to_switch_node() -> None:
    pins = 'BST = "1"\nSW = "6"\nGND = "2"'
    limit = '\n[[limits]]\nbetween = ["BST", "SW"]\nvoltage = { abs_max = "6V" }\n'
    device = parse_device(_record('ref_prefix = "U"\n', pins) + limit)
    assert device.limits == (PinPairLimit(("BST", "SW"), (Rating("voltage", "uV", None, 6_000_000),)),)
    text = device_text(device)
    assert parse_device(text) == device and "[[limits]]" in text
    error = _refused(_record('ref_prefix = "U"\n', pins) + limit.replace('"SW"]', '"XX"]'))
    assert "XX" in str(error)


@pytest.mark.parametrize(
    "limits",
    [
        '[[limits]]\nbetween = ["BST", "BST"]\nvoltage = { abs_max = "6V" }',
        '[[limits]]\nbetween = ["BST"]\nvoltage = { abs_max = "6V" }',
        '[[limits]]\nbetween = ["BST", "SW"]\nvoltage = { max = "6V" }',
        '[[limits]]\nbetween = ["BST", "SW"]\nvoltage = { abs_max = "6V" }\ncurrent = { abs_max = "1A" }',
        '[[limits]]\nbetween = ["BST", "SW"]',
        '[[limits]]\nbetween = ["BST", "SW"]\nvoltage = { abs_max = "6V" }\n'
        '[[limits]]\nbetween = ["SW", "BST"]\nvoltage = { abs_max = "6V" }',
        '[limits]\nbetween = ["BST", "SW"]\nvoltage = { abs_max = "6V" }',
    ],
)
def test_limits_refused(limits: str) -> None:
    _refused(_record('ref_prefix = "U"\n', 'BST = "1"\nSW = "6"') + "\n" + limits + "\n")


def test_thresholds_on_a_pin() -> None:
    pins = (
        'EN = { pins = ["4"], input_high_min = "1.2V", input_low_max = "0.4V", output_current_max = "4mA" }'
    )
    device = parse_device(_record('ref_prefix = "U"\n', pins))
    en = device.pin("EN")
    assert en.thresholds == (
        Threshold("input_high_min", "uV", 1_200_000),
        Threshold("input_low_max", "uV", 400_000),
        Threshold("output_current_max", "uA", 4_000),
    )
    assert en.threshold("input_low_max") == Threshold("input_low_max", "uV", 400_000)
    assert parse_device(device_text(device)) == device
    _refused(_record(pins='EN = { pins = ["4"], input_high_min = "4mA" }'))
    _refused(_record(pins='EN = { pins = ["4"], input_high = "1V" }'))


def test_class_key() -> None:
    device = parse_device(_record('class = "controller"\n'))
    assert device.cls == "controller" and 'class = "controller"' in device_text(device)
    assert parse_device(device_text(device)) == device
    error = _refused(_record('class = "bead"\n'))
    assert "bead" in str(error) and "controller" in str(error) and "ferrite" in str(error)
    assert parse_device(_record('class = "ferrite"\n')).cls == "ferrite"  # phase B of change c0274


def test_canonical_text_round_trip() -> None:
    for name, device in _all_records():
        text = device_text(device)
        assert parse_device(text, file=name) == device, name
        assert device_text(parse_device(text)) == text, name
        assert text.endswith("\n") and not text.endswith("\n\n") and "\r" not in text


def test_no_float_in_a_device() -> None:
    for name, device in _all_records():
        text = canonical.dumps(device)
        assert not _floats(json.loads(text)), name


# -- provenance (task 2.2)


def test_provenance_reformatting_keeps_the_digest() -> None:
    text = BUCK.read_text(encoding="utf-8")
    lines = text.splitlines()
    head, pins = lines[:13], lines[13:]
    shuffled = "\n\n".join([*reversed(head[2:]), *pins]) + "\n"
    assert device_digest(parse_device(shuffled)) == device_digest(parse_device(text))


def test_provenance_digest_ignores_the_stamp() -> None:
    device = parse_device(BUCK.read_text(encoding="utf-8"))
    stamp = stamped(
        device, tool="fenolite catalog import", source="Example:Buck_6pin Fenolite:X", date="2026-10-29"
    )
    assert device_digest(stamp) == device_digest(device) and len(device_digest(device)) == 64
    assert stamp.provenance is not None and stamp.provenance.sha256 == device_digest(device)
    assert not is_edited(stamp) and not is_edited(device)


def test_provenance_reformatting_is_not_an_edit() -> None:
    text = (DATA / "stamped.toml").read_text(encoding="utf-8")
    assert not is_edited(parse_device(text))
    reordered = text.replace('symbol = "Fenolite:Resistor"\n', "").replace(
        "[pins]", 'symbol = "Fenolite:Resistor"\n\n[pins]'
    )
    reordered = reordered.replace('symbol = "Fenolite:Resistor"\n\n[pins]', "[pins]").replace(
        'summary = "Resistor template (illustrative)"\n',
        'summary = "Resistor template (illustrative)"\n\nsymbol = "Fenolite:Resistor"\n',
    )
    assert not is_edited(parse_device(reordered))


def test_provenance_a_hand_edit_is_detected() -> None:
    text = (DATA / "stamped.toml").read_text(encoding="utf-8")
    edited = parse_device(text.replace('evidence = "UNVERIFIED"', 'evidence = "UNVERIFIED"\nmpn = "X-2"'))
    assert is_edited(edited) and edited.evidence == "UNVERIFIED"


def test_provenance_refused_stamps() -> None:
    text = (DATA / "stamped.toml").read_text(encoding="utf-8")
    assert "source" in str(
        _refused(text.replace('"Fenolite:Resistor Fenolite:Chip_0603"', '"/tmp/x.kicad_sym"'))
    )
    assert "date" in str(_refused(text.replace('"2026-10-29"', '"29/10/2026"')))
    assert "sha256" in str(_refused(re.sub(r'sha256 = "[0-9a-f]+"', 'sha256 = "abc"', text)))


# -- loading and checking


def test_load_devices_in_file_name_order(tmp_path: Path) -> None:
    folder = tmp_path / "devices"
    folder.mkdir()
    (folder / "b.toml").write_text(_record().replace("Proj:X", "Proj:B"), encoding="utf-8")
    (folder / "a.toml").write_text(_record().replace("Proj:X", "Proj:A"), encoding="utf-8")
    devices, issues = load_devices(folder)
    assert [device.id for device in devices] == ["Proj:A", "Proj:B"] and issues == ()
    assert load_devices(tmp_path / "missing") == ((), ())


def test_one_id_in_two_files(tmp_path: Path) -> None:
    folder = tmp_path / "devices"
    folder.mkdir()
    for name in ("a.toml", "b.toml"):
        (folder / name).write_text(_record(), encoding="utf-8")
    with pytest.raises(DeviceFormatError) as caught:
        load_devices(folder)
    assert "devices/a.toml" in str(caught.value) and "devices/b.toml" in str(caught.value)
    assert caught.value.code == "FEN-3004"


def test_edited_file_gives_an_issue(tmp_path: Path) -> None:
    folder = tmp_path / "devices"
    folder.mkdir()
    text = (DATA / "stamped.toml").read_text(encoding="utf-8")
    (folder / "r.toml").write_text(text.replace('"Resistor template', '"Edited template'), encoding="utf-8")
    _, issues = load_devices(folder)
    assert [(issue.code, issue.severity) for issue in issues] == [("device.edited", "info")]


def _symbol(*numbers: str) -> SymbolDef:
    from fenolite.core.coords import Point

    return SymbolDef(
        id="sym_test",
        name="S",
        library="T",
        pins=tuple(SymbolPin(number, "", "passive", Point(0, 0)) for number in numbers),
    )


def _footprint(*numbers: str) -> FootprintDef:
    from fenolite.core.coords import Point, Size

    return FootprintDef(
        id="fpd_test",
        name="F",
        library="T",
        pads=tuple(
            Pad(id=f"pad_{index}", number=number, shape="rect", size=Size(1, 1), position=Point(0, 0))
            for index, number in enumerate(numbers)
        ),
    )


def test_check_device() -> None:
    device = parse_device(BUCK.read_text(encoding="utf-8"))
    assert (
        check_device(
            device, _symbol("1", "2", "3", "4", "5", "6"), _footprint("1", "2", "3", "4", "5", "6", "EP")
        )
        == ()
    )
    found = check_device(
        device, _symbol("1", "2", "3", "4", "5", "6", "7"), _footprint("1", "2", "3", "4", "5", "6")
    )
    messages = [issue.message for issue in found]
    assert all(issue.code == "build.device-mismatch" and issue.severity == "error" for issue in found)
    assert any("symbol pin 7" in m for m in messages) and any("pad EP" in m and "GND" in m for m in messages)
    short = check_device(
        device, _symbol("1", "2", "3", "4", "5"), _footprint("1", "2", "3", "4", "5", "6", "EP")
    )
    assert any("function SW lists pin 6" in issue.message for issue in short)


# -- shipped devices (task 2.3)

SHIPPED = (
    "Fenolite:C_0402",
    "Fenolite:C_0603",
    "Fenolite:C_0805",
    "Fenolite:C_1206",
    "Fenolite:Conn_1x2_P2.54",
    "Fenolite:LED_0603",
    "Fenolite:R_0402",
    "Fenolite:R_0603",
    "Fenolite:R_0805",
    "Fenolite:R_1206",
)


def test_shipped_devices_agree_with_the_catalog() -> None:
    from fenolite.catalog import ENTRIES

    sources = {entry.lib_id: entry.sources for entry in ENTRIES}
    assert tuple(device.id for device in shipped_devices()) == SHIPPED
    for device in shipped_devices():
        assert check_device(device, get_symbol(device.symbol), get_footprint(device.footprint)) == (), (
            device.id
        )
        assert device.sources == tuple(sorted({*sources[device.symbol], *sources[device.footprint]}))
        assert not device.manufacturer and not device.mpn and not device.ratings
        assert device.evidence == "INFERRED" and len(device.ends) == 2
        assert {pin.function for pin in device.pins} == set(device.ends)


def test_shipped_led_keeps_the_cathode_first_map() -> None:
    from fenolite.catalog import default_pad_map

    led = shipped_device("Fenolite:LED_0603")
    assert led.pin("A").pin_pads == (("1", "2"),) and led.pin("K").pin_pads == (("2", "1"),)
    assert led.pad_map == default_pad_map(led.symbol, led.footprint)
    assert led.ends == ("A", "K")


def test_shipped_files_carry_their_licence() -> None:
    """The shipped devices are ``fenolite.device.v1`` records under ``catalog/data/devices/`` since change
    c0259: their header names the licence (CC0-1.0, authored for Fenolite) in place of a comment line."""
    from fenolite.catalog.records import DeviceRecord, shipped_tree

    folder = ROOT / "src" / "fenolite" / "catalog" / "data" / "devices"
    assert sorted(path.stem for path in folder.glob("*.toml"))
    records = [r for r in shipped_tree().records if isinstance(r, DeviceRecord)]
    assert len(records) == len(SHIPPED) and all(r.header.licence == "CC0-1.0" for r in records)


def test_shipped_sources_are_registered() -> None:
    text = (ROOT / "docs" / "evidence" / "sources.md").read_text(encoding="utf-8")
    for device in shipped_devices():
        for source in device.sources:
            assert f"| {source} |" in text, (device.id, source)


def test_value_and_reference_defaults() -> None:
    resistor = shipped_device("Fenolite:R_0603")
    assert (resistor.ref_prefix, resistor.value) == ("R", "R_0603")
    assert replace(resistor, value="x") != resistor


# Authored for Fenolite: integration of c0259 records and the c0261 pin-table generator.
def test_device_pins_tables_keep_package_properties_and_source_records(tmp_path: Path) -> None:
    from fenolite.catalog.records import DeviceRecord, LibraryTree, PinsRecord, parse_record, record_text
    from fenolite.cli._script import run_design_script
    from fenolite.cli.cmd_build import project_definitions
    from fenolite.dsl import to_model

    data = ROOT / "tests" / "data" / "library"
    pins_text = (ROOT / "tests" / "data" / "pins" / "example_buck.toml").read_text(encoding="utf-8")
    pins = parse_record(pins_text)
    assert isinstance(pins, PinsRecord) and pins.table is not None
    assert parse_record(record_text(pins)) == pins
    device_text = (data / "devices" / "example_reg.toml").read_text(encoding="utf-8")
    device_text = device_text.replace("Proj:Two_Pin", pins.header.id)
    first = parse_record(device_text)
    second = parse_record(
        device_text.replace("Example:REG_TWO", "Example:OTHER").replace("Proj:Two_Pad", "Other:Land")
    )
    assert isinstance(first, DeviceRecord) and isinstance(second, DeviceRecord)
    first = replace(
        first, device=stamped(first.device, tool="authored-test", source="pins.toml", date="2026-11-01")
    )
    before = (record_text(pins), record_text(first), record_text(second))
    tree = LibraryTree((pins, first, second))
    definitions, issues = tree.device_symbols()
    assert set(definitions) == {"Example:REG_TWO", "Example:OTHER"} and not issues
    for key, footprint in (("Example:REG_TWO", "Proj:Two_Pad"), ("Example:OTHER", "Other:Land")):
        drawing = definitions[key]
        assert drawing.properties["Footprint"] == footprint
        assert drawing.properties["ki_fp_filters"] == footprint.split(":")[1]
        assert {pin.number for pin in drawing.pins} == {"1", "2", "3", "4", "5", "6", "7"}
        assert next(pin for pin in drawing.pins if pin.number == "7").hidden
    assert (record_text(pins), record_text(first), record_text(second)) == before
    assert not is_edited(first.device) and tree.devices()[0] == first.device

    for name, text in (
        ("pins/buck.toml", pins_text),
        ("devices/a.toml", record_text(first)),
        ("devices/b.toml", record_text(second)),
    ):
        path = tmp_path / "devices" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    script = tmp_path / "design.py"
    script.write_text(
        'from fenolite.dsl import Design\ndesign = Design("generated")\n'
        'design.part("U1", device="Example:REG_TWO@EXR100DR")\n'
        'design.part("U2", device="Example:OTHER")\n',
        encoding="utf-8",
    )
    run = run_design_script(script)
    model = to_model(run.design)
    assert {part.lib_symbol_ref for part in model.circuit.components} == set(definitions)
    assert run.design.parts["U1"].device is not None
    assert not is_edited(run.devices.devices[0])
    assert run.design.parts["U1"].device.symbol == first.device.symbol
    _, drawings, findings = project_definitions(run, model)
    assert not [issue for issue in findings if issue.severity == "error"]
    for key, expected in definitions.items():
        assert drawings[key] == expected
    assert run.library.get("pins", pins.header.id).header.evidence == "UNVERIFIED"  # type: ignore[union-attr]


def test_device_pins_explicit_and_imported_drawing_precedence() -> None:
    from fenolite.catalog.records import DeviceRecord, LibraryTree, PinsRecord, parse_record

    data = ROOT / "tests" / "data" / "library"
    pins = parse_record((data / "pins" / "two_pin.toml").read_text(encoding="utf-8"))
    device = parse_record((data / "devices" / "example_reg.toml").read_text(encoding="utf-8"))
    assert isinstance(pins, PinsRecord) and isinstance(device, DeviceRecord)
    for source in (pins, replace(pins, symbol=None, symbol_file="two_pin.kicad_sym")):
        tree = LibraryTree((source, device))
        assert tree.device_symbols() == ({}, ())
        assert tree.devices()[0] == device.device


def test_pins_generator_record_preserves_header_and_rich_rows() -> None:
    from fenolite.catalog.records import PinsRecord, parse_record, record_text

    text = (ROOT / "tests" / "data" / "pins" / "example_buck.toml").read_text(encoding="utf-8")
    # Attribute-specific source maps belong to the record envelope, not the drawing generator.
    text = (
        text.replace("sources = []", 'sources = { pins = ["S-0339"] }')
        if "sources = []" in text
        else text.replace(
            'evidence = "UNVERIFIED"', 'evidence = "UNVERIFIED"\nsources = { pins = ["S-0339"] }'
        )
    )
    record = parse_record(text)
    assert isinstance(record, PinsRecord) and record.table is not None
    assert record.header.sources_by == {"pins": ("S-0339",)}
    assert parse_record(record_text(record)) == record
    assert record.table.rows[1].stacked == ("7",)
    revised = replace(record, header=replace(record.header, summary="Revised description", version="1.0.1"))
    assert parse_record(record_text(revised)) == revised


@pytest.mark.parametrize("target", ["9", "10", "altium"])
def test_device_pins_generated_symbols_build(
    target: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import io

    import fenolite.cli.main as cli_main
    from fenolite.backends.kicad.sym import read_symbol_library

    data = ROOT / "tests" / "data" / "library"
    for name in ("pins/two_pin.toml", "packages/two_pad.toml", "devices/example_reg.toml"):
        text = (data / name).read_text(encoding="utf-8")
        if name.startswith("pins/"):
            text = text[: text.index("[symbol]")]
        path = tmp_path / "project" / "devices" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    script = tmp_path / "project" / "design.py"
    script.write_text(
        "from fenolite.dsl import Design, Net, connect, mm\n"
        'design = Design("pins")\ndesign.board(mm(20), mm(10))\n'
        'u = design.part("U1", device="Example:REG_TWO")\n'
        'connect(Net("A"), u.IN)\nconnect(Net("B"), u.OUT)\n'
        "u.place(mm(10), mm(5))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    for key in ("KICAD9_SYMBOL_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD10_FOOTPRINT_DIR"):
        monkeypatch.delenv(key, raising=False)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    destination = tmp_path / "build"
    target_args = ["--target", "altium"] if target == "altium" else ["--kicad-version", target]
    code = cli_main.main(
        ["build", str(script), "--out", str(destination), *target_args, "--confirm", "--json"]
    )
    assert code == 0, err.getvalue() or out.getvalue()
    result = json.loads(out.getvalue())
    assert not [issue for issue in result["issues"] if issue["severity"] == "error"]
    if target != "altium":
        symbols = read_symbol_library(
            (destination / "lib" / "Example.kicad_sym").read_text(encoding="utf-8"), library="Example"
        )
        symbol = next(item for item in symbols if item.name == "REG_TWO")
        assert symbol.properties["Footprint"] == "Proj:Two_Pad"
        assert symbol.properties["ki_fp_filters"] == "Two_Pad"
        assert {pin.number for pin in symbol.pins} == {"1", "2"}
    else:
        assert list(destination.rglob("*.SchLib")) and list(destination.rglob("*.SchDoc"))
