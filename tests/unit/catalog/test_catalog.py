# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The built-in catalog is deterministic, sourced and usable through existing writers."""

from __future__ import annotations

from itertools import combinations, pairwise
from pathlib import Path

import pytest

from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.sym import read_symbol_library, write_symbol_library
from fenolite.catalog import ENTRIES, CatalogEntry, get_footprint, get_symbol, list_entries


def test_catalog_entries_have_registered_evidence_and_stable_search() -> None:
    source_ids = {
        line.split("|")[1].strip()
        for line in Path("docs/evidence/sources.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("| S-")
    }
    entries = list_entries()
    assert [entry.lib_id for entry in entries] == sorted(entry.lib_id for entry in entries)
    assert len(entries) == len(ENTRIES)
    assert all(entry.evidence and entry.sources and set(entry.sources) <= source_ids for entry in entries)
    assert {entry.lib_id for entry in list_entries(query="chip passive")} == {
        "Fenolite:Chip_0402",
        "Fenolite:Chip_0603",
        "Fenolite:Chip_0805",
        "Fenolite:Chip_1206",
    }


def test_published_coverage_matrix_lists_every_builtin_entry() -> None:
    coverage = Path("docs/catalog/coverage.md").read_text(encoding="utf-8")
    assert all(f"`{entry.lib_id.removeprefix('Fenolite:')}`" in coverage for entry in ENTRIES)
    assert "Project-authored or separately specified geometry" in coverage
    assert "power module" in coverage


@pytest.mark.parametrize(
    "entry", [entry for entry in ENTRIES if entry.kind == "symbol"], ids=lambda entry: entry.lib_id
)
def test_builtin_symbol_round_trips_with_ordered_body_graphics(entry: CatalogEntry) -> None:
    lib_id = entry.lib_id
    symbol = get_symbol(lib_id)
    text = write_symbol_library((symbol,))
    readback = read_symbol_library(text, library="Fenolite")[0]
    assert [pin.number for pin in readback.pins] == [pin.number for pin in symbol.pins]
    assert [pin.name for pin in readback.pins] == [pin.name for pin in symbol.pins]
    assert [pin.rotation for pin in readback.pins] == [pin.rotation for pin in symbol.pins]
    assert [pin.length for pin in readback.pins] == [pin.length for pin in symbol.pins]
    assert readback.pin_names_hidden == symbol.pin_names_hidden
    assert readback.graphics == symbol.graphics
    assert readback.properties["Description"] == symbol.properties["Description"]


def _on_segment(point: tuple[int, int], start: tuple[int, int], end: tuple[int, int]) -> bool:
    x, y = point
    x1, y1 = start
    x2, y2 = end
    return (
        (x - x1) * (y2 - y1) == (y - y1) * (x2 - x1)
        and min(x1, x2) <= x <= max(x1, x2)
        and min(y1, y2) <= y <= max(y1, y2)
    )


@pytest.mark.parametrize(
    "entry", [entry for entry in ENTRIES if entry.kind == "symbol"], ids=lambda entry: entry.lib_id
)
def test_every_symbol_pin_stem_faces_and_touches_a_visible_graphic(entry: CatalogEntry) -> None:
    symbol = get_symbol(entry.lib_id)
    xs = [point.x for graphic in symbol.graphics for point in graphic.points]
    ys = [point.y for graphic in symbol.graphics for point in graphic.points]
    for pin in symbol.pins:
        assert not (min(xs) <= pin.position.x <= max(xs) and min(ys) <= pin.position.y <= max(ys))
        dx, dy = {
            0: (pin.length, 0),
            90_000_000: (0, pin.length),
            180_000_000: (-pin.length, 0),
            270_000_000: (0, -pin.length),
        }[pin.rotation]
        end = (pin.position.x + dx, pin.position.y + dy)
        touching = False
        for graphic in symbol.graphics:
            points = [(point.x, point.y) for point in graphic.points]
            if graphic.kind == "line":
                touching |= _on_segment(end, points[0], points[1])
            elif graphic.kind == "rect":
                x1, y1 = points[0]
                x2, y2 = points[1]
                corners = ((x1, y1), (x1, y2), (x2, y2), (x2, y1))
                touching |= any(
                    _on_segment(end, a, b) for a, b in zip(corners, corners[1:] + corners[:1], strict=True)
                )
            elif graphic.kind == "polygon":
                touching |= any(
                    _on_segment(end, a, b) for a, b in zip(points, points[1:] + points[:1], strict=True)
                )
            elif graphic.kind == "circle":
                cx, cy = points[0]
                radius = abs(points[1][0] - cx)
                touching |= (end[0] - cx) ** 2 + (end[1] - cy) ** 2 == radius**2
        assert touching, (entry.lib_id, pin.number, end)


def test_polarity_and_amplifier_signs_match_pin_roles() -> None:
    for name in ("Diode", "Zener_Diode", "LED"):
        assert [pin.name for pin in get_symbol(f"Fenolite:{name}").pins] == ["A", "K"]
    for name in ("Capacitor_Polarized", "Capacitor_Electrolytic"):
        assert [pin.name for pin in get_symbol(f"Fenolite:{name}").pins] == ["+", "-"]
    for name in ("Operational_Amplifier", "Comparator"):
        pins = {pin.name: pin for pin in get_symbol(f"Fenolite:{name}").pins}
        assert pins["+"].position.y > pins["-"].position.y
        assert pins["V+"].position.y > pins["V-"].position.y


def test_resistor_zigzag_and_zener_bent_cathode_have_no_extra_contours() -> None:
    resistor = get_symbol("Fenolite:Resistor")
    assert len(resistor.graphics) == 8
    assert all(graphic.kind == "line" for graphic in resistor.graphics)
    assert all(first.points[-1] == second.points[0] for first, second in pairwise(resistor.graphics))
    assert resistor.graphics[0].points[0].x == resistor.pins[0].position.x + resistor.pins[0].length
    assert resistor.graphics[-1].points[-1].x == resistor.pins[1].position.x - resistor.pins[1].length
    assert min(point.y for graphic in resistor.graphics for point in graphic.points) < 0
    assert max(point.y for graphic in resistor.graphics for point in graphic.points) > 0

    zener = get_symbol("Fenolite:Zener_Diode")
    cathode = zener.graphics[1:]
    assert len(cathode) == 3
    assert all(graphic.kind == "line" for graphic in cathode)
    assert all(first.points[-1] == second.points[0] for first, second in pairwise(cathode))
    center = cathode[1]
    assert center.points[0].x == center.points[1].x == zener.pins[1].position.x - zener.pins[1].length
    assert (center.points[0].y, center.points[1].y) == (-1_400_000, 1_400_000)
    assert cathode[0].points[0].y == -1_900_000
    assert cathode[-1].points[-1].y == 1_900_000


def test_opto_has_clear_led_and_two_light_arrows() -> None:
    opto = get_symbol("Fenolite:Optocoupler")
    assert [pin.name for pin in opto.pins] == ["A", "K", "C", "E"]
    led = [graphic for graphic in opto.graphics if graphic.kind == "polygon"]
    assert len(led) == 1
    base_bottom, tip, base_top = led[0].points
    assert base_bottom.x == base_top.x < tip.x
    assert base_bottom.y < tip.y < base_top.y
    assert any(
        graphic.kind == "line"
        and graphic.points[0].x == graphic.points[1].x == tip.x
        and graphic.points[0].y < 0 < graphic.points[1].y
        for graphic in opto.graphics
    )
    shafts = [
        graphic
        for graphic in opto.graphics
        if graphic.kind == "line" and graphic.points[0].x == -900_000 and graphic.points[1].x == 1_000_000
    ]
    assert len(shafts) == 2
    assert all(graphic.points[0].y == graphic.points[1].y for graphic in shafts)
    assert not any(
        graphic.kind == "line" and graphic.points[0].x == graphic.points[1].x == 0
        for graphic in opto.graphics
    )


@pytest.mark.parametrize("count", (2, 3, 4))
def test_header_symbols_have_one_square_contact_per_pin(count: int) -> None:
    connector = get_symbol(f"Fenolite:Connector_{count}")
    assert len(connector.pins) == count
    assert len(connector.graphics) == count + 1
    housing, *contacts = connector.graphics
    assert housing.kind == "rect" and housing.filled
    assert housing.points[0].y == -housing.points[1].y
    assert sum(pin.position.y for pin in connector.pins) == 0
    for pin, contact in zip(connector.pins, contacts, strict=True):
        assert contact.kind == "rect"
        left, bottom = contact.points[0].x, contact.points[0].y
        right, top = contact.points[1].x, contact.points[1].y
        assert right - left == top - bottom == 1_270_000
        assert pin.position.x + pin.length == left
        assert 2 * pin.position.y == bottom + top
        assert left == housing.points[0].x
        assert right < housing.points[1].x
    terminal = get_symbol("Fenolite:Terminal_1Pin")
    assert terminal.graphics[0].kind == "rect"
    assert terminal.pins[0].position.x + terminal.pins[0].length == terminal.graphics[0].points[0].x


def test_coil_and_fuse_have_continuous_smooth_contours() -> None:
    for name in ("Inductor", "Fuse"):
        symbol = get_symbol(f"Fenolite:{name}")
        assert all(graphic.kind == "line" for graphic in symbol.graphics)
        assert all(first.points[-1] == second.points[0] for first, second in pairwise(symbol.graphics))
        assert symbol.graphics[0].points[0].x == -2_540_000
        assert symbol.graphics[-1].points[-1].x == 2_540_000
        assert max(point.y for graphic in symbol.graphics for point in graphic.points) > 0
    assert len(get_symbol("Fenolite:Inductor").graphics) == 64
    assert min(point.y for graphic in get_symbol("Fenolite:Fuse").graphics for point in graphic.points) < 0


def test_conceptual_ic_blocks_have_no_decorative_internal_strokes() -> None:
    for name in ("Linear_Regulator", "Offline_Power_Controller", "Microcontroller", "Power_Module"):
        symbol = get_symbol(f"Fenolite:{name}")
        assert len(symbol.graphics) == 1
        assert symbol.graphics[0].kind == "rect"
    for name in ("Operational_Amplifier", "Comparator"):
        symbol = get_symbol(f"Fenolite:{name}")
        triangle, output = symbol.graphics
        assert triangle.kind == "polygon" and output.kind == "line"
        assert output.points[0] == triangle.points[-1]
        for supply in symbol.pins[-2:]:
            signed_length = supply.length if supply.rotation == 90_000_000 else -supply.length
            assert supply.position.y + signed_length in (-2_540_000, 2_540_000)


def test_new_coupled_protection_and_dual_led_roles_remain_distinct() -> None:
    choke = get_symbol("Fenolite:Common_Mode_Choke")
    assert len(choke.pins) == 4
    assert [pin.position.y for pin in choke.pins] == [5_080_000, -5_080_000] * 2
    core = choke.graphics[-2:]
    assert all(graphic.kind == "line" for graphic in core)
    assert {graphic.points[0].y for graphic in core} == {-750_000, 750_000}
    assert all(graphic.points[0].y == graphic.points[1].y for graphic in core)

    tube = get_symbol("Fenolite:Gas_Discharge_Tube")
    assert len(tube.pins) == 2
    assert tube.graphics[0].kind == "circle"
    left_electrode = tube.graphics[1:4]
    right_electrode = tube.graphics[4:]
    assert all(point.x < 0 for graphic in left_electrode for point in graphic.points)
    assert all(point.x > 0 for graphic in right_electrode for point in graphic.points)

    led = get_symbol("Fenolite:Dual_LED_Common_Cathode")
    assert [pin.name for pin in led.pins] == ["A1", "A2", "K"]
    assert len([graphic for graphic in led.graphics if graphic.kind == "polygon"]) == 2
    assert "common cathode" in led.properties["Description"]
    assert led.footprint == ""


def test_only_polarized_capacitors_have_heavier_negative_plate() -> None:
    for name in ("Capacitor", "Capacitor_Ceramic", "Capacitor_Film"):
        capacitor = get_symbol(f"Fenolite:{name}")
        assert len(capacitor.graphics) == 2
        assert [graphic.width for graphic in capacitor.graphics] == [254_000, 254_000]
    for name in ("Capacitor_Polarized", "Capacitor_Electrolytic"):
        capacitor = get_symbol(f"Fenolite:{name}")
        assert [graphic.width for graphic in capacitor.graphics[:2]] == [254_000, 635_000]
        assert capacitor.graphics[0].points[0].x < capacitor.graphics[1].points[0].x
        assert [pin.name for pin in capacitor.pins] == ["+", "-"]


@pytest.mark.parametrize(
    "entry", [entry for entry in ENTRIES if entry.kind == "footprint"], ids=lambda entry: entry.lib_id
)
def test_builtin_footprint_round_trips_and_stays_inferred(entry: CatalogEntry) -> None:
    lib_id = entry.lib_id
    footprint = get_footprint(lib_id)
    text = write_footprint(footprint)
    readback = read_footprint(text, library="Fenolite")
    assert [pad.number for pad in readback.pads] == [pad.number for pad in footprint.pads]
    assert [pad.shape for pad in readback.pads] == [pad.shape for pad in footprint.pads]
    assert [pad.size for pad in readback.pads] == [pad.size for pad in footprint.pads]
    assert [pad.position for pad in readback.pads] == [pad.position for pad in footprint.pads]
    assert [graphic.layer for graphic in readback.graphics] == [
        graphic.layer for graphic in footprint.graphics
    ]
    assert "INFERRED" in footprint.description


@pytest.mark.parametrize(
    "entry", [entry for entry in ENTRIES if entry.kind == "footprint"], ids=lambda e: e.lib_id
)
def test_builtin_footprint_has_clearance_and_enclosing_courtyard(entry: CatalogEntry) -> None:
    footprint = get_footprint(entry.lib_id)
    assert all(pad.shape == ("rect" if pad.kind == "smd" else "circle") for pad in footprint.pads)
    assert {graphic.layer for graphic in footprint.graphics} == {"F.Fab", "F.CrtYd"}
    courtyard = footprint.graphics_on("F.CrtYd")[0]
    fab = footprint.graphics_on("F.Fab")[0]
    assert courtyard.kind == fab.kind == "rect"
    half_x = courtyard.points[1].x
    half_y = courtyard.points[1].y
    assert half_x > fab.points[1].x and half_y > fab.points[1].y
    for pad in footprint.pads:
        assert 2 * abs(pad.position.x) + pad.size.w < 2 * half_x
        assert 2 * abs(pad.position.y) + pad.size.h < 2 * half_y
    for first, second in combinations(footprint.pads, 2):
        if first.number == second.number:
            continue
        gap_x_2 = 2 * abs(first.position.x - second.position.x) - first.size.w - second.size.w
        gap_y_2 = 2 * abs(first.position.y - second.position.y) - first.size.h - second.size.h
        assert gap_x_2 > 0 or gap_y_2 > 0, (footprint.lib_id, first.number, second.number)


@pytest.mark.parametrize(
    ("name", "gap", "length", "width"),
    [
        ("0402", 400, 550, 600),
        ("0603", 700, 900, 1000),
        ("0805", 1000, 900, 1450),
        ("1206", 1750, 1150, 1800),
    ],
)
def test_chip_reflow_rectangles_follow_vishay_example(name: str, gap: int, length: int, width: int) -> None:
    pads = get_footprint(f"Fenolite:Chip_{name}").pads
    assert [pad.position.x for pad in pads] == [-(gap + length) * 500, (gap + length) * 500]
    assert [(pad.size.w, pad.size.h) for pad in pads] == [(length * 1000, width * 1000)] * 2


def test_sot_pad_numbering_and_pitch_follow_top_view_drawings() -> None:
    expected = {
        "SOT23_3": ((1, -1050, 950), (2, -1050, -950), (3, 1050, 0)),
        "SOT23_5": ((1, -1300, 950), (2, -1300, 0), (3, -1300, -950), (4, 1300, -950), (5, 1300, 950)),
        "SC70_5": ((1, -1100, 650), (2, -1100, 0), (3, -1100, -650), (4, 1100, -650), (5, 1100, 650)),
    }
    for name, positions in expected.items():
        pads = get_footprint(f"Fenolite:{name}").pads
        assert [(int(p.number), p.position.x // 1000, p.position.y // 1000) for p in pads] == list(positions)
        assert all(p.size.w > p.size.h for p in pads)


def test_lqfp32_pads_rotate_around_four_sides() -> None:
    pads = get_footprint("Fenolite:LQFP32_P0.8").pads
    assert len(pads) == 32
    corners = {
        1: (-4200, 2800),
        8: (-4200, -2800),
        9: (-2800, -4200),
        16: (2800, -4200),
        17: (4200, -2800),
        24: (4200, 2800),
        25: (2800, 4200),
        32: (-2800, 4200),
    }
    for number, (x, y) in corners.items():
        pad = pads[number - 1]
        assert pad.number == str(number)
        assert (pad.position.x, pad.position.y) == (x * 1000, y * 1000)
    for pad in pads:
        assert (pad.size.w, pad.size.h) == (
            (1_500_000, 550_000) if abs(pad.position.x) == 4_200_000 else (550_000, 1_500_000)
        )


def test_sot89_split_tab_and_header_rows_are_consistent() -> None:
    sot = get_footprint("Fenolite:SOT89_3")
    stem, tab = [pad for pad in sot.pads if pad.number == "2"]
    assert stem.position.y + stem.size.h // 2 > tab.position.y - tab.size.h // 2
    for count in (2, 3, 4):
        header = get_footprint(f"Fenolite:Header_1x{count}_P2.5")
        assert sum(pad.position.y for pad in header.pads) == 0
        assert [pad.position.y for pad in header.pads] == [
            ((count - 1 - 2 * i) * 2_500_000) // 2 for i in range(count)
        ]


def test_unknown_id_does_not_fall_back_to_external_lookup() -> None:
    with pytest.raises(KeyError, match="Fenolite:Unknown"):
        get_symbol("Fenolite:Unknown")
    with pytest.raises(KeyError, match="Fenolite:Unknown"):
        get_footprint("Fenolite:Unknown")
