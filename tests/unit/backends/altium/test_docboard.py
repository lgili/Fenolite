# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``Board6`` record of the PCB document (change c0035, capability altium-pcb-writer, "PCB document
file"): each rule of ``docs/formats/altium/pcb-document.md``, "The ``Board6`` record"."""

from __future__ import annotations

import re

import pytest

from fenolite.backends.altium import libboard
from fenolite.backends.altium.docboard import (
    angle_text,
    board_fields,
    board_records,
    board_text,
    common_fields,
    format_line,
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
