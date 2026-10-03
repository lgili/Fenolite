# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``Board6`` record of the PCB document (change c0035, capability altium-pcb-writer, "PCB document
file"): each rule of ``docs/formats/altium/pcb-document.md``, "The ``Board6`` record"."""

from __future__ import annotations

import hashlib
import re

import pytest

from fenolite.backends.altium import libboard
from fenolite.backends.altium.docboard import (
    StackSpec,
    angle_text,
    board_fields,
    board_records,
    board_text,
    common_fields,
    format_line,
    name_codes,
    polygon_fields,
)

SQUARE = [
    (10_000_000, 10_000_000),
    (30_000_000, 10_000_000),
    (30_000_000, 20_000_000),
    (10_000_000, 20_000_000),
]
ORIGIN = (10_000_000, 10_000_000)
GUID = re.compile(r"\{[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}\}")
COMMON = ["SELECTION", "LAYER", "LOCKED", "POLYGONOUTLINE", "USERROUTED", "KEEPOUT", "UNIONINDEX"]


def lines(used: tuple[int, ...] = ()) -> list[list[tuple[str, str]]]:
    return board_records("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=used)


def fields(used: tuple[int, ...] = ()) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in board_fields("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=used):
        out.setdefault(key, value)
    return out


def test_twenty_seven_lines_each_later_one_a_board_record() -> None:
    record = lines()
    assert len(record) == 27
    assert all(line[0] == ("RECORD", "Board") for line in record[1:]) and record[0][0][0] == "SELECTION"
    assert all(key != "RECORD" for line in record for key, _ in line[1:])
    text = board_text("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH")
    assert text.count("\r") == 26 and "\n" not in text and text.isascii()
    assert all(part.startswith("|RECORD=Board|") for part in text.split("\r")[1:])
    assert 2200 <= sum(len(line) for line in record) <= 2500


def test_first_line_board_keys() -> None:
    first = lines()[0]
    keys = [key for key, _ in first]
    assert keys[:12] == [*COMMON, "FILENAME", "KIND", "VERSION", "DATE", "TIME"]
    assert first[1] == ("LAYER", "UNKNOWN") and first[7:10] == [
        ("FILENAME", "X.PcbDoc"),
        ("KIND", "Protel_Advanced_PCB"),
        ("VERSION", "5.01"),
    ]
    at = keys.index("ORIGINX")
    assert keys[at : at + 17] == [
        "ORIGINX",
        "ORIGINY",
        "BIGVISIBLEGRIDSIZE",
        "VISIBLEGRIDSIZE",
        "ELECTRICALGRIDRANGE",
        "ELECTRICALGRIDENABLED",
        "SNAPGRIDSIZE",
        "SNAPGRIDSIZEX",
        "SNAPGRIDSIZEY",
        "TRACKGRIDSIZE",
        "VIAGRIDSIZE",
        "COMPONENTGRIDSIZE",
        "COMPONENTGRIDSIZEX",
        "COMPONENTGRIDSIZEY",
        "DOTGRID",
        "DISPLAYUNIT",
        "DESIGNATORDISPLAYMODE",
    ]
    values = dict(first[7:])
    assert values["ORIGINX"] == values["ORIGINY"] == "1000mil"
    assert values["SNAPGRIDSIZE"] == values["COMPONENTGRIDSIZE"] == "50000.000000"
    assert values["TRACKGRIDSIZE"] == values["VIAGRIDSIZE"] == "200000.000000"
    assert keys[-22:-16] == ["SHEETX", "SHEETY", "SHEETWIDTH", "SHEETHEIGHT", "SHOWSHEET", "LOCKSHEET"]
    assert first[-16:] == [(f"PLANE{n}NETNAME", "(No Net)") for n in range(1, 17)]


def test_outline_is_a_closed_polygon_of_eight_keys_per_vertex() -> None:
    first = lines()[0]
    keys = [key for key, _ in first]
    start = keys.index("KIND0")
    assert keys[start - 16 : start - 9] == COMMON and first[start - 15] == ("LAYER", "TOP")
    assert keys[start - 9 : start] == [
        "PRIMITIVELOCK",
        "POLYGONTYPE",
        "POUROVER",
        "REMOVEDEAD",
        "GRIDSIZE",
        "TRACKWIDTH",
        "HATCHSTYLE",
        "USEOCTAGONS",
        "MINPRIMLENGTH",
    ]
    vertex = first[start : start + 40]
    for k in range(5):
        chunk = vertex[8 * k : 8 * k + 8]
        assert [key for key, _ in chunk] == [
            f"{name}{k}" for name in ("KIND", "VX", "VY", "CX", "CY", "SA", "EA", "R")
        ]
        assert chunk[0][1] == "0" and [value for _, value in chunk[3:]] == [
            "0mil",
            "0mil",
            " 0.00000000000000E+0000",
            " 0.00000000000000E+0000",
            "0mil",
        ]
    points = [(vertex[8 * k + 1][1], vertex[8 * k + 2][1]) for k in range(5)]
    assert points == [
        ("1000mil", "1000mil"),
        ("3000mil", "1000mil"),
        ("3000mil", "2000mil"),
        ("1000mil", "2000mil"),
        ("1000mil", "1000mil"),
    ]
    assert keys[start + 40 : start + 53] == [
        "SHELVED",
        "RESTORELAYER",
        "RESTORENET",
        "REMOVEISLANDSBYAREA",
        "REMOVENECKS",
        "AREATHRESHOLD",
        "ARCRESOLUTION",
        "NECKWIDTHTHRESHOLD",
        "POUROVERSTYLE",
        "NAME",
        "POURINDEX",
        "IGNOREVIOLATIONS",
        "SPLITLINECOUNT",
    ]
    with pytest.raises(ValueError, match="at least three points"):
        board_records("X.PcbDoc", SQUARE[:2], ORIGIN, unique_id="ABCDEFGH")


def test_sub_stack_keys() -> None:
    """The sub-stack after each master stack; two keys before the ``ID`` of the nine stack layers only."""
    record = lines((1, 33))
    second = record[1]
    keys = [key for key, _ in second]
    sub = dict(second)["V9_SUBSTACK0_ID"]
    assert GUID.fullmatch(sub) and sub == libboard.guid("substack") != dict(second)["V9_MASTERSTACK_ID"]
    names = [
        "ID",
        "NAME",
        "SHOWTOPDIELECTRIC",
        "SHOWBOTTOMDIELECTRIC",
        "ISFLEX",
        "SERVICE",
        "USEDBYPRIMS",
        "TYPE",
    ]
    assert keys[7:15] == [f"V9_SUBSTACK0_{name}" for name in names]
    at = keys.index("LAYERMASTERSTACK_V8ISFLEX") + 1
    assert keys[at : at + 8] == [f"LAYERSUBSTACK_V8_0{name}" for name in names]
    values = dict(second)
    assert values["V9_SUBSTACK0_NAME"] == "Board Layer Stack" and values["V9_SUBSTACK0_TYPE"] == "1"
    assert values["LAYERSUBSTACK_V8_0ID"] == sub and values["V9_SUBSTACK0_USEDBYPRIMS"] == "FALSE"
    context = [key for key in keys if key.endswith("CONTEXT")]
    wanted = [f"V9_STACK_LAYER{i}_{sub}CONTEXT" for i in range(9)]
    wanted += [f"V9_CACHE_LAYER{i}_{sub}CONTEXT" for i in range(12, 21)]
    wanted += [f"LAYER_V8_{i}_{sub}CONTEXT" for i in range(9)]
    assert context == wanted and all(values[key] == "0" for key in context)
    for key in context:
        at = keys.index(key)
        prefix = key.removesuffix(f"_{sub}CONTEXT")
        assert second[at + 1] == (f"{prefix}_{sub}USEDBYPRIMS", "FALSE")
        assert keys[at + 2] in (f"{prefix}_ID", f"{prefix}ID")
    assert values["V9_STACK_LAYER3_NAME"] == "Top Layer" and values["V9_STACK_LAYER3_USEDBYPRIMS"] == "TRUE"
    assert (
        values["V9_STACK_LAYER1_USEDBYPRIMS"] == "TRUE" and values["V9_STACK_LAYER5_USEDBYPRIMS"] == "FALSE"
    )


def test_stack_and_layers_are_the_library_ones() -> None:
    """Without the sub-stack keys and the drill pair, lines 2 to 18 are a library's first 17 lines after
    its five file keys."""
    record = lines((1, 74))
    sub = libboard.guid("substack")
    library = libboard.board_records("X.PcbLib", (1, 74))
    ours = [
        [item for item in line if sub not in item[0] and "SUBSTACK" not in item[0]] for line in record[1:18]
    ]
    ours[0] = ours[0][1:]
    ours[-1] = ours[-1][:-4]  # the drill pair; its sub-stack key is already filtered out
    assert ours == [library[0][5:], *library[1:17]]
    assert record[17][-5:] == [
        ("LAYERPAIR0LOW", "TOP"),
        ("LAYERPAIR0HIGH", "BOTTOM"),
        ("LAYERPAIR0DRILLGUIDE", "FALSE"),
        ("LAYERPAIR0DRILLDRAWING", "FALSE"),
        ("LAYERPAIR0SUBSTACK_0", sub),
    ]


def test_routing_line() -> None:
    routing = lines()[18]
    keys = [key for key, _ in routing]
    values = dict(routing)
    assert keys[1] == "TOGGLELAYERS" and values["TOGGLELAYERS"] == "1" * 82
    assert keys[2:22] == [f"PLACEMARKER{axis}{i}" for i in range(1, 11) for axis in "XY"]
    assert {values[key] for key in keys[2:22]} == {"-0.0001mil"}
    assert routing[22:30] == [(f"SELECTIONMEMORYLOCK{i}", "FALSE") for i in range(1, 9)]
    assert keys[30:36] == [
        "SURFACEMICROSTRIP_I",
        "SURFACEMICROSTRIP_W",
        "SYMMETRICSTRIPLINE_I",
        "SYMMETRICSTRIPLINE_W",
        "ELECTRICALGRIDSNAPTOBO",
        "ELECTRICALGRIDUSEALLLAYERS",
    ]
    for key in keys[30:34]:
        assert values[key].count("(") == values[key].count(")") and "TraceToPlaneDistance" in values[key]
    directions = ["TOP LAYER", *(f"MID LAYER {i}" for i in range(1, 31)), "BOTTOM LAYER"]
    assert routing[36:68] == [(f"ROUTINGDIRECTION{name}", "Automatic") for name in directions]
    widths = ["TOPLAYER", *(f"MIDLAYER{i}" for i in range(1, 31)), "BOTTOMLAYER"]
    assert routing[68:100] == [(f"{name}_MRLASTWIDTH", "10mil") for name in widths]
    assert routing[100:104] == [
        ("MRLASTVIASIZE", "50mil"),
        ("MRLASTVIAHOLE", "28mil"),
        ("LASTTARGETLENGTH", "99999mil"),
        ("SHOWDEFAULTSETS", "TRUE"),
    ]
    assert routing[104:-1] == libboard.layer_sets() and routing[-1] == (
        "BOARDINSIGHTVIEWCONFIGURATIONNAME",
        "",
    )
    assert len(routing) == 136


def test_view_lines_and_window() -> None:
    record = lines()
    assert record[19] == [
        ("RECORD", "Board"),
        ("VISIBLEGRIDMULTFACTOR", "1.000"),
        ("BIGVISIBLEGRIDMULTFACTOR", "5.000"),
        ("ELECTRICALGRIDMULTFACT", "0.000"),
        ("OUTLINEMODELCRC", "0"),
        ("OUTLINEMODELNAME", ""),
    ]
    assert record[20] == [("RECORD", "Board"), ("CURRENT2D3DVIEWSTATE", "2D")]
    assert record[21][1:] == [
        ("VP.LX", "9000000"),
        ("VP.HX", "31000000"),
        ("VP.LY", "9000000"),
        ("VP.HY", "21000000"),
    ]
    assert record[22:26] == libboard.view_configurations() == libboard.board_records("X.PcbLib")[20:24]
    values = dict(record[26])
    assert (values["LOOKAT.X"], values["LOOKAT.Y"]) == ("20000000.000000", "15000000.000000")
    assert (values["VIEWSIZE.X"], values["VIEWSIZE.Y"]) == ("22000000", "12000000")
    assert values["ZOOMMULT"] == "0.000054"


def test_last_line_grid_and_closing_keys() -> None:
    tail = lines()[26]
    keys = [key for key, _ in tail]
    values = dict(tail)
    grid = keys.index("GR0_TYPE")
    assert grid == 10 and keys[grid : grid + 20] == [
        f"GR0_{name}"
        for name in (
            "TYPE",
            "NAME",
            "COLOR",
            "COLORLGE",
            "PRIO",
            "OX",
            "OY",
            "DRAWMODE",
            "DRAWMODELARGE",
            "ENABLED",
            "MULT",
            "MULTLARGE",
            "DISPLAYUNIT",
            "COMP",
            "GSX",
            "GSY",
            "QSX",
            "QSY",
            "ROT",
            "FLAGS",
        )
    ]
    assert values["GR0_TYPE"] == "CartesianGrid" and values["GR0_NAME"] == "Global Board Snap Grid"
    assert values["GR0_OX"] == values["GR0_OY"] == "1000mil" and values["GR0_GSX"] == "50000.000000"
    assert keys[30:45] == [
        "EGRANGE",
        "EGMULT",
        "EGENABLED",
        "EGSNAPTOBOARDOUTLINE",
        "EGSNAPTOARCCENTERS",
        "EGUSEALLLAYERS",
        "OGSNAPENABLED",
        "MGSNAPENABLED",
        "POINTGUIDEENABLED",
        "GRIDSNAPENABLED",
        "NEAROBJECTSENABLED",
        "FAROBJECTSENABLED",
        "NEAROBJECTSET",
        "FAROBJECTSET",
        "NEARDISTANCE",
    ]
    assert len(values["NEAROBJECTSET"]) == len(values["FAROBJECTSET"]) == 27
    assert tail[45:51] == [
        ("DRILLSYMBOLASENUM", "0"),
        ("DRILLSYMBOLSIZE", "200000"),
        ("HOLESHAPEHASHSIZE", "0"),
        ("VIEWPORTSAREVISIBLE", "TRUE"),
        ("UNIQUEID", "ABCDEFGH"),
        ("PINPAIRCOUNT", "0"),
    ]
    assert [key for key in keys if key.startswith("TEARDROPPARAM_")] == keys[51:60] and len(keys) == 61
    assert tail[-2:] == [("TEARDROPPARAM_FLAGSEX", "1002"), ("SPLITLINECOUNT", "0")]
    assert not {"BOARDVERSION", "VAULTGUID", "FOLDERGUID"} & set(fields())


def test_angle_text() -> None:
    assert [angle_text(u) for u in (0, 90_000_000, 270_000_000, -90_000_000, 12_500_000, 1, 360_000_000)] == [
        " 0.00000000000000E+0000",
        " 9.00000000000000E+0001",
        " 2.70000000000000E+0002",
        " 2.70000000000000E+0002",
        " 1.25000000000000E+0001",
        " 1.00000000000000E-0006",
        " 0.00000000000000E+0000",
    ]


def test_common_fields_and_line_format() -> None:
    assert [key for key, _ in common_fields("TOP")] == COMMON and common_fields("TOP")[1] == ("LAYER", "TOP")
    assert format_line([("ROUTINGDIRECTIONTOP LAYER", "Automatic"), ("NAME", "")]) == (
        "|ROUTINGDIRECTIONTOP LAYER=Automatic|NAME="
    )
    for bad in (("A=B", "1"), ("A", "x|y"), ("", "1"), ("A", "café"), ("A", "x\ry")):
        with pytest.raises(ValueError, match="cannot be written in a board record"):
            format_line([bad])


def test_deterministic_and_printable() -> None:
    one = board_text("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=(1, 32))
    assert one == board_text("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=(32, 1))
    assert one != board_text("Y.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=(1, 32))
    assert all(ch == "\r" or 0x20 <= ord(ch) <= 0x7E for ch in one)


# --- copper stack (change c0038, "Four-layer stack") -----------------------------------------------

TWO_LAYER_TEXT = "892a675da67316eaf7bd749bafb85b2c5d10cdeae41a429c67bcc412b513a621"
"""SHA-256 of the two-layer record of ``SQUARE`` as change c0035 wrote it."""


def stack_board(stack: StackSpec | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in board_fields("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", stack=stack):
        out.setdefault(key, value)
    return out


def chain_of(board: dict[str, str]) -> list[int]:
    layer, walk = 1, []
    while layer:
        walk.append(layer)
        layer = int(board[f"LAYER{layer}NEXT"])
    return walk


def test_stack_of_two_layers_keeps_its_bytes() -> None:
    """Scenario "Two layers keep their bytes"."""
    plain = board_text("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=(1, 32))
    default = StackSpec.default((1, 32))
    assert plain == board_text(
        "X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=(1, 32), stack=default
    )
    assert hashlib.sha256(plain.encode("ascii")).hexdigest() == TWO_LAYER_TEXT


def test_stack_chain_of_four_signal_layers() -> None:
    """Scenario "Chain of four signal layers" on the board record alone."""
    stack = StackSpec.default((1, 2, 3, 32))
    board = stack_board(stack)
    assert chain_of(board) == [1, 2, 3, 32] and board["LAYER32PREV"] == "3"
    assert board["V9_STACK_LAYER4_NAME"] == "Dielectric 1" and board["V9_STACK_LAYER5_LAYERID"] == "16777218"
    assert board["V9_STACK_LAYER5_COMPONENTPLACEMENT"] == "1"
    records = board_records("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", stack=stack)
    assert len(records) == 27 and all(line[0] == ("RECORD", "Board") for line in records[1:])
    assert board["LAYERSET2LAYERS"] == "MultiLayer,TopLayer,MidLayer1,MidLayer2,BottomLayer"
    assert all(board[f"PLANE{k}NETNAME"] == "(No Net)" for k in range(1, 17))
    assert board["LAYERPAIR0LOW"] == "TOP" and board["LAYERPAIR0HIGH"] == "BOTTOM"
    sub = libboard.guid("substack")
    assert board[f"V9_STACK_LAYER5_{sub}CONTEXT"] == "0" and board[f"LAYER_V8_12_{sub}USEDBYPRIMS"] == "FALSE"


def test_stack_used_layers_mark_the_mid_layers() -> None:
    stack = StackSpec.default((1, 2, 3, 32))
    fields_of = dict(
        board_fields("X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", used_layers=(2,), stack=stack)
    )
    assert (
        fields_of["V9_STACK_LAYER5_USEDBYPRIMS"] == "TRUE"
        and fields_of["V9_STACK_LAYER7_USEDBYPRIMS"] == "FALSE"
    )
    assert (
        fields_of["LAYER_V8_5USEDBYPRIMS"] == "TRUE" and fields_of["V9_CACHE_LAYER21_USEDBYPRIMS"] == "TRUE"
    )


# --- polygon pours (change c0038, "Polygon pour records") -------------------------------------------

POUR_KEYS_BEFORE = [
    *COMMON,
    "PRIMITIVELOCK",
    "POLYGONTYPE",
    "POUROVER",
    "REMOVEDEAD",
    "GRIDSIZE",
    "TRACKWIDTH",
    "HATCHSTYLE",
    "USEOCTAGONS",
    "MINPRIMLENGTH",
]
POUR_KEYS_AFTER = [
    "SHELVED",
    "RESTORELAYER",
    "RESTORENET",
    "REMOVEISLANDSBYAREA",
    "REMOVENECKS",
    "AREATHRESHOLD",
    "ARCRESOLUTION",
    "NECKWIDTHTHRESHOLD",
    "POUROVERSTYLE",
    "NAME",
    "POURINDEX",
    "IGNOREVIOLATIONS",
]


def test_polygon_fields_of_a_named_pour() -> None:
    found = polygon_fields("MID1", SQUARE, name="GND", pour_index=3, net=0)
    keys = [key for key, _ in found]
    vertex = [f"{key}{k}" for k in range(5) for key in ("KIND", "VX", "VY", "CX", "CY", "SA", "EA", "R")]
    assert keys == [*POUR_KEYS_BEFORE, *vertex, *POUR_KEYS_AFTER, "OPTIMALVOIDROTATION", "NET"]
    values = dict(found)
    assert (
        values["LAYER"] == "MID1" and values["POLYGONTYPE"] == "Polygon" and values["PRIMITIVELOCK"] == "TRUE"
    )
    assert (values["POUROVER"], values["REMOVEDEAD"], values["HATCHSTYLE"]) == ("TRUE", "TRUE", "Solid")
    assert (values["GRIDSIZE"], values["TRACKWIDTH"], values["MINPRIMLENGTH"]) == ("20mil", "8mil", "3mil")
    assert values["USEOCTAGONS"] == "FALSE" and values["SHELVED"] == "FALSE" and values["RESTORENET"] == ""
    assert values["RESTORELAYER"] == "UNKNOWN" and values["AREATHRESHOLD"] == "250000000000.000000"
    assert (values["REMOVEISLANDSBYAREA"], values["REMOVENECKS"]) == ("TRUE", "TRUE")
    assert (values["ARCRESOLUTION"], values["NECKWIDTHTHRESHOLD"], values["POUROVERSTYLE"]) == (
        "0.5mil",
        "5mil",
        "1",
    )
    assert values["NAME"] == "71,78,68" and values["POURINDEX"] == "3" and values["NET"] == "0"
    assert values["IGNOREVIOLATIONS"] == "FALSE" and values["OPTIMALVOIDROTATION"] == "TRUE"
    assert (values["VX0"], values["VY0"]) == (values["VX4"], values["VY4"]) == ("1000mil", "1000mil")
    assert values["KIND2"] == "0" and values["SA2"] == " 0.00000000000000E+0000" and values["R2"] == "0mil"


def test_polygon_fields_generated_name_and_no_net() -> None:
    keys = [
        key
        for key, _ in polygon_fields("TOP", SQUARE[:3], name="NONET_L01_P000", pour_index=0, auto_name=True)
    ]
    assert keys[-3:] == ["IGNOREVIOLATIONS", "AUTONAME", "OPTIMALVOIDROTATION"] and "NET" not in keys
    assert "SPLITLINECOUNT" not in keys and "VX3" in keys and "VX4" not in keys
    assert name_codes("") == "" and name_codes("A_1") == "65,95,49"
    with pytest.raises(ValueError, match="at least three points"):
        polygon_fields("TOP", SQUARE[:2], name="X", pour_index=0)


def test_polygon_keys_are_the_outline_keys_with_a_net_a_name_and_an_index() -> None:
    """The outline of the board record keeps its own values (c0035's text is pinned above)."""
    first = lines()[0]
    start = [key for key, _ in first].index("PRIMITIVELOCK")
    outline = dict(first[start - 7 :])
    pour = dict(polygon_fields("TOP", SQUARE, name="X", pour_index=0))
    shared = [key for key in pour if key in outline and key not in ("NAME", "POURINDEX")]
    assert len(shared) == 7 + 9 + 40 + 9 + 1
    differing = sorted(key for key in shared if pour[key] != outline[key])
    assert differing == ["GRIDSIZE", "HATCHSTYLE", "POUROVER", "POUROVERSTYLE", "REMOVEDEAD", "TRACKWIDTH"]
    assert outline["POURINDEX"] == "-1" and outline["NAME"] == "" and outline["HATCHSTYLE"] == "None"


# --- internal planes (change c0038, "Four-layer stack") --------------------------------------------


def test_ground_plane_under_the_top_layer() -> None:
    """Scenario "Ground plane under the top layer"."""
    board = stack_board(StackSpec.default((1, 39, 3, 32), plane_nets=("GND",)))
    assert chain_of(board) == [1, 39, 3, 32]
    assert board["PLANE1NETNAME"] == "GND" and board["PLANE2NETNAME"] == "(No Net)"
    assert (
        board["V9_STACK_LAYER5_NAME"] == "Internal Plane 1" and board["V9_STACK_LAYER5_LAYERID"] == "16842753"
    )
    assert board["V9_STACK_LAYER5_PULLBACKDISTANCE"] == "20mil"
    assert "V9_STACK_LAYER5_COMPONENTPLACEMENT" not in board
    assert board["V9_STACK_LAYER7_NAME"] == "Mid-Layer 2" and board["LAYERSET3LAYERS"] == "InternalPlane1"
    assert board["LAYERSET2LAYERS"] == "MultiLayer,TopLayer,MidLayer2,BottomLayer"
    assert board["LAYERPAIR0LOW"] == "TOP" and board["LAYERPAIR0HIGH"] == "BOTTOM"


def test_two_planes_in_the_stack() -> None:
    """Scenario "Two planes"."""
    board = stack_board(StackSpec.default((1, 39, 40, 32), plane_nets=("GND", "VIN")))
    assert chain_of(board) == [1, 39, 40, 32]
    assert board["PLANE1NETNAME"] == "GND" and board["PLANE2NETNAME"] == "VIN"
    assert board["LAYERSET2LAYERS"] == "MultiLayer,TopLayer,BottomLayer"
    assert board["LAYERSET3LAYERS"] == "InternalPlane1,InternalPlane2"
    cache = [value for key, value in board.items() if re.fullmatch(r"V9_CACHE_LAYER\d+_NAME", key)]
    assert cache.count("Internal Plane 1") == 1 and cache.count("Internal Plane 2") == 1
    for index in (51, 52):
        assert board[f"V9_CACHE_LAYER{index}_PULLBACKDISTANCE"] == "20mil"
    assert (
        board["V9_STACK_LAYER7_NAME"] == "Internal Plane 2" and board["V9_STACK_LAYER7_LAYERID"] == "16842754"
    )


def test_plane_lines_of_the_record() -> None:
    records = board_records(
        "X.PcbDoc", SQUARE, ORIGIN, unique_id="ABCDEFGH", stack=StackSpec.default((1, 2, 39, 32), ("GND",))
    )
    assert len(records) == 27
    first = dict(records[0])
    assert first["PLANE1NETNAME"] == "GND" and sum(key.endswith("NETNAME") for key in first) == 16
