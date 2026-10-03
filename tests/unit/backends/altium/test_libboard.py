# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board record of a PCB library (change c0035, capability altium-pcb-writer, "PCB library file"):
every rule of ``docs/formats/altium/pcb-library.md``, "The board record of ``Library/Data``", checked on
``libboard.board_fields``. No Altium-saved file is used: the rules are stated here as the page states them.
"""

from __future__ import annotations

import re

import pytest

from fenolite.backends.altium.libboard import board_fields, board_records, board_text, guid, long_id

GUID = re.compile(r"\{[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}\}")
STACK = [
    "Top Paste",
    "Top Overlay",
    "Top Solder",
    "Top Layer",
    "Dielectric 1",
    "Bottom Layer",
    "Bottom Solder",
    "Bottom Overlay",
    "Bottom Paste",
]
MARKERS = ["Connections", "Background", "DRC Error Markers"]
VIEW = ["Selections", "Visible Grid 1", "Visible Grid 2", "Pad Holes", "Via Holes"]
MASTERS = ["Top Pad Master", "Bottom Pad Master"]
MECH_1_16 = [f"Mechanical {n}" for n in range(1, 17)]
MECH_17_32 = [f"Mechanical {n}" for n in range(17, 33)]


def fields(used: tuple[int, ...] = ()) -> list[tuple[str, str]]:
    return board_fields("X.PcbLib", used)


def first(key: str, used: tuple[int, ...] = ()) -> str:
    return next(value for k, value in fields(used) if k == key)


def names(prefix: str, sep: str, count: int) -> list[str]:
    values = dict(f for f in fields() if f[0] != "RECORD")
    return [values[f"{prefix}{i}{sep}NAME"] for i in range(count)]


def test_the_record_starts_with_the_file_keys() -> None:
    assert fields()[:5] == [
        ("FILENAME", "X.PcbLib"),
        ("KIND", "Protel_Advanced_PCB_Library"),
        ("VERSION", "3.00"),
        ("DATE", "2000-01-01"),
        ("TIME", "00:00:00"),
    ]


def test_no_header_or_weight_key_and_only_record_repeats() -> None:
    keys = [key for key, _value in fields()]
    assert "HEADER" not in keys and "WEIGHT" not in keys
    repeated = {key for key in keys if keys.count(key) > 1}
    assert repeated == {"RECORD"} and keys.count("RECORD") == 25
    assert all(value == "Board" for key, value in fields() if key == "RECORD")


def test_master_stack_in_both_generations() -> None:
    values = dict(fields())
    for prefix in ("V9_MASTERSTACK_", "LAYERMASTERSTACK_V8"):
        assert values[f"{prefix}STYLE"] == "0" and values[f"{prefix}NAME"] == "Master layer stack"
        assert GUID.fullmatch(values[f"{prefix}ID"])
        assert values[f"{prefix}ISFLEX"] == values[f"{prefix}SHOWTOPDIELECTRIC"] == "FALSE"
    assert values["V9_MASTERSTACK_ID"] == values["LAYERMASTERSTACK_V8ID"]
    keys = [key for key, _value in fields()]
    assert keys[5:11] == [
        f"V9_MASTERSTACK_{k}"
        for k in ("STYLE", "ID", "NAME", "SHOWTOPDIELECTRIC", "SHOWBOTTOMDIELECTRIC", "ISFLEX")
    ]


def test_layer_lists() -> None:
    assert names("V9_STACK_LAYER", "_", 9) == STACK
    mids = [f"Mid-Layer {n}" for n in range(1, 31)]
    planes = [f"Internal Plane {n}" for n in range(1, 17)]
    head = ["Multi-Layer", *MARKERS, "DRC Detail Markers", *VIEW, *MASTERS]
    tail = ["Drill Guide", "Keep-Out Layer", *MECH_1_16, "Drill Drawing", *MECH_17_32]
    assert names("V9_CACHE_LAYER", "_", 102) == [*head, *STACK, *mids, *planes, *tail]
    v8_tail = ["Drill Drawing", "Multi-Layer", *MARKERS, *VIEW, *MASTERS, "DRC Detail Markers", *MECH_17_32]
    assert names("LAYER_V8_", "", 56) == [*STACK, "Drill Guide", "Keep-Out Layer", *MECH_1_16, *v8_tail]
    keys = {key for key, _value in fields()}
    assert "V9_STACK_LAYER9_NAME" not in keys and "V9_CACHE_LAYER102_NAME" not in keys
    assert "LAYER_V8_56NAME" not in keys and "LAYER83NAME" not in keys and "LAYERV7_16NAME" not in keys


def test_keys_of_each_layer_kind() -> None:
    values = dict(fields())

    def keys_of(prefix: str) -> list[str]:
        return [key[len(prefix) :] for key, _value in fields() if key.startswith(prefix)]

    common = ["ID", "NAME", "LAYERID", "USEDBYPRIMS"]
    dielectric = ["DIELTYPE", "DIELCONST", "DIELHEIGHT", "DIELMATERIAL"]
    assert keys_of("V9_STACK_LAYER0_") == common  # paste
    assert keys_of("V9_STACK_LAYER2_") == [*common, *dielectric, "COVERLAY_EXPANSION"]  # solder mask
    assert keys_of("V9_STACK_LAYER3_") == [*common, "COPTHICK", "COMPONENTPLACEMENT"]  # copper
    assert keys_of("V9_STACK_LAYER4_") == [*common, *dielectric]
    assert keys_of("V9_CACHE_LAYER51_") == [*common, "COPTHICK", "PULLBACKDISTANCE"]  # internal plane
    assert keys_of("V9_CACHE_LAYER69_") == [*common, "MECHENABLED"]
    assert values["V9_STACK_LAYER2_DIELMATERIAL"] == "Solder Resist"
    assert values["V9_STACK_LAYER2_DIELTYPE"] == "3" and values["V9_STACK_LAYER2_DIELHEIGHT"] == "0.4mil"
    assert values["V9_STACK_LAYER4_DIELMATERIAL"] == "FR-4" and values["V9_STACK_LAYER4_DIELCONST"] == "4.800"
    placements = [
        values[f"V9_{k}_COMPONENTPLACEMENT"] for k in ("STACK_LAYER3", "STACK_LAYER5", "CACHE_LAYER21")
    ]
    assert placements == ["1", "2", "0"]
    assert values["V9_CACHE_LAYER51_PULLBACKDISTANCE"] == "20mil"


def test_long_layer_ids() -> None:
    assert long_id(1) == 0x01000001 and long_id(31) == 0x0100001F and long_id(32) == 0x0100FFFF
    assert long_id(39) == 0x01010001 and long_id(57) == 0x01020001 and long_id(72) == 0x01020010
    expected = {33: 6, 34: 7, 35: 8, 36: 9, 37: 10, 38: 11, 55: 12, 56: 13, 73: 14, 74: 15, 82: 23}
    assert {n: long_id(n) - 0x01030000 for n in expected} == expected
    values = dict(fields())
    assert values["V9_STACK_LAYER4_LAYERID"] == str(0x01040001)
    assert values["V9_CACHE_LAYER4_LAYERID"] == str(0x01030000 + 26)
    with pytest.raises(ValueError, match="layer 83 has no long id"):
        long_id(83)


def test_a_layer_has_one_guid_in_every_list() -> None:
    found: dict[str, set[str]] = {}
    rows = fields()
    for (key, value), (_k, _v), (id_key, long) in zip(rows, rows[1:], rows[2:], strict=False):
        if key.endswith("ID") and id_key.endswith("LAYERID") and GUID.fullmatch(value):
            found.setdefault(long, set()).add(value)
    assert len(found) == 102 and all(len(ids) == 1 for ids in found.values())
    assert len({next(iter(ids)) for ids in found.values()}) == 102
    assert guid("layer:1") == guid("layer:1") != guid("layer:2")


def test_numbered_layers_come_five_at_a_time() -> None:
    rows = fields()
    start = rows.index(("SHOWBOTTOMDIELECTRIC", "FALSE")) + 1
    end = rows.index(("LAYERV7_0LAYERID", str(0x01020011)))
    block = rows[start:end]
    assert len(block) == 82 * 9 + 16
    records = [i for i, row in enumerate(block) if row == ("RECORD", "Board")]
    assert records == [45 + 46 * i for i in range(16)]
    values = dict(row for row in block if row[0] != "RECORD")
    links = {n: (values[f"LAYER{n}PREV"], values[f"LAYER{n}NEXT"]) for n in range(1, 83)}
    wanted = {1: ("0", "32"), 32: ("1", "0")}
    wanted.update({n: ("0", "1") for n in (33, 35, 37)})
    wanted.update({n: ("32", "0") for n in (34, 36, 38)})
    assert links == {n: wanted.get(n, ("0", "0")) for n in range(1, 83)}
    assert values["LAYER74NAME"] == "Multi-Layer" and values["LAYER82NAME"] == "Via Holes"
    assert [key[len("LAYER1") :] for key, _v in block[:9]] == [
        "NAME",
        "PREV",
        "NEXT",
        "MECHENABLED",
        "COPTHICK",
        "DIELTYPE",
        "DIELCONST",
        "DIELHEIGHT",
        "DIELMATERIAL",
    ]


def test_later_mechanical_layers() -> None:
    values = dict(fields())
    for i in range(16):
        assert values[f"LAYERV7_{i}NAME"] == f"Mechanical {17 + i}"
        assert values[f"LAYERV7_{i}LAYERID"] == str(0x01020011 + i)
        assert values[f"LAYERV7_{i}PREV"] == values[f"LAYERV7_{i}NEXT"] == "16973824"


def test_mechanical_13_to_16_are_enabled_in_every_list() -> None:
    enabled = sorted(key for key, value in fields() if key.endswith("MECHENABLED") and value == "TRUE")
    assert enabled == sorted(
        [f"V9_CACHE_LAYER{i}_MECHENABLED" for i in (81, 82, 83, 84)]
        + [f"LAYER_V8_{i}MECHENABLED" for i in (23, 24, 25, 26)]
        + [f"LAYER{i}MECHENABLED" for i in (69, 70, 71, 72)]
    )
    values = dict(fields())
    assert values["LAYERSET5LAYERS"] == "Mechanical13,Mechanical14,Mechanical15,Mechanical16"
    assert values["LAYERSET5ACTIVELAYER.7"] == "MECHANICAL13"
    assert values["LAYERSET1LAYERS"].endswith(
        "KeepOutLayer,Mechanical13,Mechanical14,Mechanical15,Mechanical16,DrillDrawing"
    )


def test_used_layers_set_usedbyprims() -> None:
    def used(layers: tuple[int, ...]) -> list[str]:
        return [key for key, value in fields(layers) if key.endswith("USEDBYPRIMS") and value == "TRUE"]

    assert used(()) == []
    assert used((1,)) == [
        "V9_STACK_LAYER3_USEDBYPRIMS",
        "V9_CACHE_LAYER15_USEDBYPRIMS",
        "LAYER_V8_3USEDBYPRIMS",
    ]
    assert used((74, 69)) == [
        "V9_CACHE_LAYER0_USEDBYPRIMS",
        "V9_CACHE_LAYER81_USEDBYPRIMS",
        "LAYER_V8_23USEDBYPRIMS",
        "LAYER_V8_28USEDBYPRIMS",
    ]


def test_grid_and_layer_sets() -> None:
    values = dict(fields())
    assert values["SNAPGRIDSIZE"] == values["SNAPGRIDSIZEX"] == values["SNAPGRIDSIZEY"] == "50000.000000"
    assert values["TOGGLELAYERS"] == "1" * 82 and values["LAYERSETSCOUNT"] == "5"
    assert [values[f"LAYERSET{n}NAME"] for n in range(1, 6)] == [
        "&All Layers",
        "&Signal Layers",
        "&Plane Layers",
        "&NonSignal Layers",
        "&Mechanical Layers",
    ]
    assert values["LAYERSET2LAYERS"] == "MultiLayer,TopLayer,BottomLayer" and values["LAYERSET3LAYERS"] == ""
    assert [values[f"LAYERSET{n}ACTIVELAYER.7"] for n in range(1, 5)] == [
        "TOP",
        "TOP",
        "UNKNOWN",
        "MULTILAYER",
    ]


def test_view_keys() -> None:
    rows = fields()
    values = dict(rows)
    opacity = [key for key, _value in rows if key.startswith("CFG2D.LAYEROPACITY.")]
    assert len(opacity) == 82 and opacity[0].endswith(".TOPLAYER") and opacity[-1].endswith(".VIAHOLELAYER")
    assert values[opacity[0]] == "1.00;" * 16 + "0.40;" + "1.00;" * 6
    toggle = values["CFG2D.TOGGLELAYERS.SET"]
    assert toggle.startswith(
        "Signal.All~0_Signal.Include~SerializeLayerHash.Version=2,ClassName=TLayerHash,16777217=1,"
    )
    assert toggle.endswith(",16973847=1_Dielectric.All~0") and toggle.count("=1") == 32 + 16 + 16 + 19
    assert (
        "_Standard.All~0_Standard.Include~SerializeLayerHash.Version=2,ClassName=TLayerHash,16973850=1,16973830=1,"
        in toggle
    )
    alphas = [key for key, _value in rows if key.startswith("CFG2D.WORKSPACECOLALPHA")]
    assert [int(key[len("CFG2D.WORKSPACECOLALPHA") :]) for key in alphas] == [*range(12), 13, 14]
    two = values["2DCONFIGURATION"]
    start, end = (
        rows.index(("CFGALL.CONFIGURATIONKIND", "1")),
        rows.index(("BOARDINSIGHTVIEWCONFIGURATIONNAME", "")),
    )
    assert two == "`RECORD=Board" + "".join(f"`{k}={v.replace(';', '?')}" for k, v in rows[start:end])
    assert rows[start - 1] == ("RECORD", "Board") and ";" not in two
    assert two.startswith(
        "`RECORD=Board`CFGALL.CONFIGURATIONKIND=1`CFGALL.CONFIGURATIONDESC=Altium%20Standard%202D`CFG2D."
    )
    three = values["3DCONFIGURATION"]
    assert three.startswith("`RECORD=Board`CFGALL.CONFIGURATIONKIND=3`") and three.count("`CFG3D.") == 37
    assert values["2DCONFIGFULLFILENAME"] == values["3DCONFIGFULLFILENAME"] == "(Not Saved)"
    assert values["CURRENT2D3DVIEWSTATE"] == "2D" and int(values["VP.LX"]) < 500_000_000 < int(
        values["VP.HX"]
    )


def test_the_record_ends_with_the_version_and_empty_guids() -> None:
    assert fields()[-5:] == [
        ("BOARDVERSION", "5.01"),
        ("VAULTGUID", ""),
        ("FOLDERGUID", ""),
        ("LIFECYCLEDEFINITIONGUID", ""),
        ("REVISIONNAMINGSCHEMEGUID", ""),
    ]
    assert len(fields()) == 2044


def test_lines_start_with_record_and_join_with_one_cr() -> None:
    lines = board_records("X.PcbLib")
    assert len(lines) == 25 and lines[0][0] == ("FILENAME", "X.PcbLib")
    assert all(line[0] == ("RECORD", "Board") for line in lines[1:])
    inline = [line for line in lines if line.count(("RECORD", "Board")) == 2]
    assert (
        len(inline) == 1
        and ("LAYERSETSCOUNT", "5") in inline[0]
        and ("CFG2D.CURRENTLAYER", "TOP") in inline[0]
    )
    assert [key for key, _v in lines[1][1:10:9]] == ["LAYER6NAME"] and lines[16][1][0] == "LAYER81NAME"
    assert lines[16][-1][0] == "LAYERV7_15DIELMATERIAL" and lines[-1][-1] == ("REVISIONNAMINGSCHEMEGUID", "")
    text = board_text("X.PcbLib")
    assert text.count("\r") == 24 and "\n" not in text and text.count("\r|RECORD=Board|") == 24
    assert text.count("|RECORD=Board|") == 25 and text.startswith("|FILENAME=X.PcbLib|KIND=")
    assert [f for line in lines for f in line] == board_fields("X.PcbLib")


def test_every_field_is_printable_ascii_without_a_pipe() -> None:
    for key, value in fields((1, 32, 33, 34, 69, 70, 71, 72, 74)):
        assert key and all(0x20 <= ord(ch) <= 0x7E and ch != "|" for ch in key + value), key
