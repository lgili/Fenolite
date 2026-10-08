# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The built-in catalog is deterministic, sourced and usable through existing writers."""

from __future__ import annotations

from itertools import combinations, pairwise
from pathlib import Path

import pytest
from _pintext import ALTIUM, body_box, body_end, findings, shown_texts

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
        "Fenolite:Chip_0201_Vishay_Draloric",
        "Fenolite:Chip_0402",
        "Fenolite:Chip_0603",
        "Fenolite:Chip_0805",
        "Fenolite:Chip_1206",
        "Fenolite:Chip_1210_Vishay_Draloric",
        "Fenolite:Chip_2010_Vishay_RCWP",
        "Fenolite:Chip_2512_Vishay_RCWP",
    }


def test_published_coverage_matrix_lists_every_builtin_entry() -> None:
    coverage = Path("docs/catalog/coverage.md").read_text(encoding="utf-8")
    assert all(f"`{entry.lib_id.removeprefix('Fenolite:')}`" in coverage for entry in ENTRIES)
    assert "Project-authored or separately specified geometry" in coverage
    assert "power module" in coverage


def test_final_inventory_has_100_exact_distinct_sourced_patterns() -> None:
    inventory = Path("docs/catalog/target-100-footprints.md").read_text(encoding="utf-8")
    rows = [
        line.split("|")
        for line in inventory.splitlines()
        if line.startswith("| ") and line.split("|")[1].strip().isdigit()
    ]
    assert [int(row[1]) for row in rows] == list(range(1, 101))
    names = {(row[4].split("`")[1] if "shipped as" in row[4] else row[2].split("`")[1]) for row in rows}
    entries = list_entries(kind="footprint")
    assert len(entries) == len(names) == 100
    assert {entry.lib_id for entry in entries} == {f"Fenolite:{name}" for name in names}
    source_map = Path("docs/catalog/sources.md").read_text(encoding="utf-8")
    patterns = set()
    for entry in entries:
        assert entry.evidence == "INFERRED" and entry.sources
        assert f"`{entry.lib_id}`" in source_map
        fp = get_footprint(entry.lib_id)
        # Ignore IDs, descriptions, pin labels and polarity decoration: aliases cannot inflate count.
        pads = tuple(
            sorted(
                (
                    p.position.x,
                    p.position.y,
                    p.size.w,
                    p.size.h,
                    p.kind,
                    p.shape,
                    p.rotation,
                    p.drill or 0,
                    p.layers,
                    (p.padstack.hole_shape, p.padstack.hole_length, p.padstack.hole_rotation)
                    if p.padstack
                    else (),
                )
                for p in fp.pads
            )
        )
        body = fp.graphics_on("F.Fab")[0]
        paste = tuple((g.kind, g.points, g.filled) for g in fp.graphics_on("F.Paste"))
        pattern = (pads, body.kind, body.points, paste)
        assert pattern not in patterns, entry.lib_id
        patterns.add(pattern)


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
        symbol = get_symbol(f"Fenolite:{name}")
        pins = {pin.name: pin for pin in symbol.pins}
        assert pins["+"].position.y > pins["-"].position.y
        assert pins["V+"].position.y > pins["V-"].position.y
        # The names are hidden (change c0134): a plus stroke lies on the row of the "+" input and a
        # minus stroke on the row of the "-" input, both just inside the triangle's left edge.
        triangle, _output, plus_bar, plus_stem, minus_bar = symbol.graphics
        edge = triangle.points[0].x
        for bar, pin in ((plus_bar, pins["+"]), (minus_bar, pins["-"])):
            assert bar.kind == "line" and bar.points[0].y == bar.points[1].y == pin.position.y
            assert edge < bar.points[0].x < bar.points[1].x < 0
        centre = (plus_bar.points[0].x + plus_bar.points[1].x) // 2
        assert plus_stem.points[0].x == plus_stem.points[1].x == centre
        assert plus_stem.points[0].y < pins["+"].position.y < plus_stem.points[1].y
        assert (minus_bar.points[0].x, minus_bar.points[1].x) == (plus_bar.points[0].x, plus_bar.points[1].x)
        assert symbol.pin_names_hidden


def test_bridge_rectifier_marks_its_terminals_with_strokes() -> None:
    """The names ``~``, ``~``, ``+`` and ``-`` are hidden (change c0134): a plus below the positive
    corner, a minus above the negative one and a wave of three strokes beside each AC corner say the
    same in both tools, upright."""
    bridge = get_symbol("Fenolite:Bridge_Rectifier")
    assert [pin.name for pin in bridge.pins] == ["~", "~", "+", "-"] and bridge.pin_names_hidden
    marks = bridge.graphics[16:]  # after the four diode branches of four graphics each
    assert len(marks) == 9 and all(mark.kind == "line" and mark.width == 254_000 for mark in marks)
    plus_bar, plus_stem, minus_bar, *waves = marks
    left_ac, right_ac, positive, negative = bridge.pins
    assert plus_bar.points[0].y == plus_bar.points[1].y == plus_stem.points[0].y + 400_000
    assert plus_stem.points[0].x == plus_stem.points[1].x == positive.position.x == 0
    assert 0 < plus_stem.points[0].y < plus_stem.points[1].y < positive.position.y - positive.length
    assert minus_bar.points[0].y == minus_bar.points[1].y == -plus_bar.points[0].y
    assert negative.position.y + negative.length < minus_bar.points[0].y < 0
    for wave, pin in ((waves[:3], left_ac), (waves[3:], right_ac)):
        assert all(first.points[1] == second.points[0] for first, second in pairwise(wave))
        xs = [point.x for stroke in wave for point in stroke.points]
        inner = pin.position.x + (pin.length if pin.rotation == 0 else -pin.length)
        assert all(0 < abs(x) < abs(inner) and (x < 0) == (inner < 0) for x in xs)
        assert {point.y for stroke in wave for point in stroke.points} == {-150_000, 150_000}


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
    # The names are hidden (change c0134): an open arrowhead of two strokes at the outer end of the
    # detector's lower leg marks the emitter, and the collector's leg carries none.
    assert opto.pin_names_hidden
    collector, emitter = opto.pins[2], opto.pins[3]
    barbs = {
        row: [
            graphic.points[1]
            for graphic in opto.graphics
            if graphic.kind == "line"
            and (graphic.points[0].x, graphic.points[0].y) == (3_200_000, row)
            and graphic.points[1].y != row
        ]
        for row in (collector.position.y, emitter.position.y)
    }
    assert barbs[collector.position.y] == [] and len(barbs[emitter.position.y]) == 2
    assert all(tip.x < 3_200_000 and tip.y > emitter.position.y for tip in barbs[emitter.position.y])


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


def test_ic_blocks_are_plain_rectangles_and_amplifiers_carry_only_their_input_signs() -> None:
    for name in ("Linear_Regulator", "Offline_Power_Controller", "Microcontroller", "Power_Module"):
        symbol = get_symbol(f"Fenolite:{name}")
        assert len(symbol.graphics) == 1
        assert symbol.graphics[0].kind == "rect"
        assert not symbol.pin_names_hidden
    for name in ("Operational_Amplifier", "Comparator"):
        symbol = get_symbol(f"Fenolite:{name}")
        # The triangle, its output stub, and the plus and the minus of the two inputs (change c0134);
        # ``test_polarity_and_amplifier_signs_match_pin_roles`` places the three sign strokes.
        triangle, output, *signs = symbol.graphics
        assert triangle.kind == "polygon" and output.kind == "line"
        assert [sign.kind for sign in signs] == ["line", "line", "line"]
        assert output.points[0] == triangle.points[-1]
        for supply in symbol.pins[-2:]:
            signed_length = supply.length if supply.rotation == 90_000_000 else -supply.length
            assert supply.position.y + signed_length in (-2_540_000, 2_540_000)


def test_linear_regulator_is_a_square_that_holds_its_three_names() -> None:
    """Scenario "Linear regulator" of "Legible pin texts" (change c0134): one pin on each side and one
    below, and room for ``IN``, ``OUT`` and ``GND`` at the larger of the two text sizes."""
    symbol = get_symbol("Fenolite:Linear_Regulator")
    assert not symbol.pin_names_hidden and not symbol.pin_numbers_hidden
    assert body_box(symbol) == (-7_620_000, -7_620_000, 7_620_000, 7_620_000)
    assert {pin.name: body_end(pin) for pin in symbol.pins} == {
        "IN": (-7_620_000, 5_080_000),
        "GND": (0, -7_620_000),
        "OUT": (7_620_000, 5_080_000),
    }
    names = {text.text: text.box for text in shown_texts(symbol, 1, ALTIUM) if text.kind == "name"}
    assert names["IN"][1::2] == names["OUT"][1::2]  # one row
    assert names["IN"][2] <= names["OUT"][0]  # IN ends where OUT begins
    assert names["IN"][1] - names["GND"][3] == 2_667_000  # GND ends below that row
    assert findings(symbol) == []


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
    assert readback.kind == footprint.kind
    assert readback.flags == footprint.flags
    for original, restored in zip(footprint.pads, readback.pads, strict=True):
        assert (restored.kind, restored.layers, restored.drill, restored.rotation) == (
            original.kind,
            original.layers,
            original.drill,
            original.rotation,
        )
        if original.padstack:
            assert restored.padstack is not None
            assert (
                restored.padstack.hole_shape,
                restored.padstack.hole_length,
                restored.padstack.hole_rotation,
            ) == (
                original.padstack.hole_shape,
                original.padstack.hole_length,
                original.padstack.hole_rotation,
            )
    for original, restored in zip(footprint.graphics, readback.graphics, strict=True):
        assert (restored.kind, restored.points, restored.width, restored.filled) == (
            original.kind,
            original.points,
            original.width,
            original.filled,
        )
    assert "INFERRED" in footprint.description


@pytest.mark.parametrize(
    "entry", [entry for entry in ENTRIES if entry.kind == "footprint"], ids=lambda e: e.lib_id
)
def test_builtin_footprint_has_clearance_and_enclosing_courtyard(entry: CatalogEntry) -> None:
    footprint = get_footprint(entry.lib_id)
    assert all(
        pad.shape
        == (
            "circle"
            if footprint.name == "TestPoint_SMD_D1.0"
            else "rect"
            if pad.kind == "smd"
            else "oval"
            if pad.padstack
            else "circle"
        )
        for pad in footprint.pads
    )
    assert (
        {"F.Fab", "F.CrtYd"}
        <= {graphic.layer for graphic in footprint.graphics}
        <= {"F.Fab", "F.CrtYd", "F.Paste"}
    )
    courtyard = footprint.graphics_on("F.CrtYd")[0]
    fab = footprint.graphics_on("F.Fab")[0]
    assert courtyard.kind == "rect" and fab.kind in ("rect", "circle")
    lower, upper = courtyard.points
    if fab.kind == "circle":
        center, edge = fab.points
        radius = abs(edge.x - center.x)
        assert edge.y == center.y
        body_bounds = (center.x - radius, center.y - radius, center.x + radius, center.y + radius)
    else:
        body_bounds = (fab.points[0].x, fab.points[0].y, fab.points[1].x, fab.points[1].y)
    assert lower.x < body_bounds[0] < body_bounds[2] < upper.x
    assert lower.y < body_bounds[1] < body_bounds[3] < upper.y
    for pad in footprint.pads:
        assert 2 * lower.x < 2 * pad.position.x - pad.size.w
        assert 2 * upper.x > 2 * pad.position.x + pad.size.w
        assert 2 * lower.y < 2 * pad.position.y - pad.size.h
        assert 2 * upper.y > 2 * pad.position.y + pad.size.h
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


@pytest.mark.parametrize(
    ("name", "gap", "length", "width"),
    [
        ("Chip_0201_Vishay_Draloric", 270, 430, 420),
        ("Chip_1210_Vishay_Draloric", 1750, 1150, 2650),
        ("Chip_2010_Vishay_RCWP", 4060, 1020, 2540),
        ("Chip_2512_Vishay_RCWP", 5330, 1020, 3180),
        ("MELF_0102_Vishay_MMU", 950, 1050, 1250),
    ],
)
def test_new_vishay_lands_match_recommended_dimensions(name: str, gap: int, length: int, width: int) -> None:
    pads = get_footprint(f"Fenolite:{name}").pads
    assert [pad.number for pad in pads] == ["1", "2"]
    assert [pad.position.x for pad in pads] == [-(gap + length) * 500, (gap + length) * 500]
    assert [(pad.size.w, pad.size.h) for pad in pads] == [(length * 1000, width * 1000)] * 2


@pytest.mark.parametrize(
    ("name", "gap", "length", "width"),
    [
        ("Chip_1812_TDK_CGA8", 3400, 1300, 2800),
        ("DO214AA_Diodes_SMB", 1800, 2500, 2300),
        ("DO214AB_Diodes_SMC", 4400, 2500, 3300),
        ("SOD123_Diodes", 2250, 900, 950),
        ("SOD123F_Diodes_Standard", 1900, 1000, 1500),
        ("SOD323_Diodes", 1520, 590, 450),
        ("SOD523_Diodes", 800, 600, 700),
    ],
)
def test_new_chip_and_diode_lands_match_source_dimensions(
    name: str, gap: int, length: int, width: int
) -> None:
    footprint = get_footprint(f"Fenolite:{name}")
    left, right = footprint.pads
    assert (left.number, right.number) == ("1", "2")
    assert right.position.x - left.position.x == (gap + length) * 1000
    assert (left.size.w, left.size.h) == (length * 1000, width * 1000)
    if name.startswith(("DO214", "SOD")):
        mark = [graphic for graphic in footprint.graphics if graphic.kind == "line"]
        assert len(mark) == 1
        assert mark[0].layer == "F.Fab"
        assert mark[0].points[0].x == mark[0].points[1].x > 0
        assert left.position.x < mark[0].points[0].x < right.position.x
        assert get_symbol("Fenolite:Diode").pins[0].name == "A"
        assert get_symbol("Fenolite:Diode").pins[1].name == "K"


def test_sot_pad_numbering_and_pitch_follow_top_view_drawings() -> None:
    expected = {
        "SOT23_3": ((1, -1050, 950), (2, -1050, -950), (3, 1050, 0)),
        "SOT23_5": ((1, -1300, 950), (2, -1300, 0), (3, -1300, -950), (4, 1300, -950), (5, 1300, 950)),
        "SC70_5": ((1, -1100, 650), (2, -1100, 0), (3, -1100, -650), (4, 1100, -650), (5, 1100, 650)),
        "SOT23_6_TI_DBV0006A": (
            (1, -1300, 950),
            (2, -1300, 0),
            (3, -1300, -950),
            (4, 1300, -950),
            (5, 1300, 0),
            (6, 1300, 950),
        ),
        "SC70_6_TI_DCK0006A": (
            (1, -1100, 650),
            (2, -1100, 0),
            (3, -1100, -650),
            (4, 1100, -650),
            (5, 1100, 0),
            (6, 1100, 650),
        ),
    }
    for name, positions in expected.items():
        pads = get_footprint(f"Fenolite:{name}").pads
        assert [(int(p.number), p.position.x // 1000, p.position.y // 1000) for p in pads] == list(positions)
        assert all(p.size.w > p.size.h for p in pads)


@pytest.mark.parametrize(
    ("name", "centers", "size"),
    [
        ("SOT323_3_Diodes_Standard", ((-950, 325), (-950, -325), (950, 0)), (600, 470)),
        ("SOT523_3_Diodes", ((-645, 350), (-645, -350), (645, 0)), (510, 400)),
        (
            "SOT563_6_Diodes",
            ((-635, 500), (-635, 0), (-635, -500), (635, -500), (635, 0), (635, 500)),
            (670, 300),
        ),
    ],
)
def test_compact_sot_lands_follow_package_pitch(
    name: str, centers: tuple[tuple[int, int], ...], size: tuple[int, int]
) -> None:
    pads = get_footprint(f"Fenolite:{name}").pads
    assert [(pad.position.x // 1000, pad.position.y // 1000) for pad in pads] == list(centers)
    assert [(pad.size.w // 1000, pad.size.h // 1000) for pad in pads] == [size] * len(pads)
    assert [pad.number for pad in pads] == [str(i) for i in range(1, len(pads) + 1)]


@pytest.mark.parametrize(
    ("name", "centers", "sizes"),
    [
        (
            "SOT143_4_Diodes",
            ((-760, -1000), (960, -1000), (960, 1000), (-960, 1000)),
            ((1000, 700), (600, 700), (600, 700), (600, 700)),
        ),
        (
            "SOT223_3_Diodes",
            ((-2300, -3100), (0, 3100), (2300, -3100)),
            ((1200, 1400), (3500, 1400), (1200, 1400)),
        ),
        (
            "TO252_3_Diodes_Standard",
            ((-2286, -4050), (0, 2500), (2286, -4050)),
            ((1060, 2600), (5632, 5700), (1060, 2600)),
        ),
        (
            "TO263_3_Diodes_Standard",
            ((-2540, -6245), (0, 4490), (2540, -6245)),
            ((1100, 3500), (10410, 7010), (1100, 3500)),
        ),
    ],
)
def test_asymmetric_discrete_lands_follow_source_layout(
    name: str, centers: tuple[tuple[int, int], ...], sizes: tuple[tuple[int, int], ...]
) -> None:
    pads = get_footprint(f"Fenolite:{name}").pads
    assert [pad.number for pad in pads] == [str(i) for i in range(1, len(pads) + 1)]
    assert [(pad.position.x // 1000, pad.position.y // 1000) for pad in pads] == list(centers)
    assert [(pad.size.w // 1000, pad.size.h // 1000) for pad in pads] == list(sizes)


@pytest.mark.parametrize(
    ("name", "land", "drill"),
    [("DO35_P10.16_Diodes", 1600, 800), ("DO41_P10.16_Diodes", 2200, 1100)],
)
def test_axial_diode_bend_pitch_and_inferred_hole_are_explicit(name: str, land: int, drill: int) -> None:
    footprint = get_footprint(f"Fenolite:{name}")
    assert [pad.position.x for pad in footprint.pads] == [-5_080_000, 5_080_000]
    assert [pad.number for pad in footprint.pads] == ["1", "2"]
    assert all(pad.kind == "thru_hole" and pad.size.w == land * 1000 for pad in footprint.pads)
    assert all(pad.drill == drill * 1000 for pad in footprint.pads)
    assert any(graphic.kind == "line" and graphic.layer == "F.Fab" for graphic in footprint.graphics)


def test_sod128_keeps_manufacturer_cathode_numbering() -> None:
    footprint = get_footprint("Fenolite:SOD128_Nexperia_CFP5")
    assert [(pad.number, pad.position.x, pad.size.w, pad.size.h) for pad in footprint.pads] == [
        ("1", -2_200_000, 1_400_000, 2_100_000),
        ("2", 2_200_000, 1_400_000, 2_100_000),
    ]
    mark = next(graphic for graphic in footprint.graphics if graphic.kind == "line")
    assert mark.points[0].x == mark.points[1].x < 0
    assert get_symbol("Fenolite:Diode").pins[0].name == "A"


def test_sot883_and_to220_distinct_pads_and_body_projection() -> None:
    sot = get_footprint("Fenolite:SOT883_3_Nexperia_DFN1006")
    assert [(pad.number, pad.position.x, pad.position.y, pad.size.w, pad.size.h) for pad in sot.pads] == [
        ("1", -350_000, 225_000, 400_000, 250_000),
        ("2", -350_000, -225_000, 400_000, 250_000),
        ("3", 350_000, 0, 400_000, 700_000),
    ]
    to220 = get_footprint("Fenolite:TO220_3_Diodes_Vertical")
    assert [pad.position.x for pad in to220.pads] == [-2_540_000, 0, 2_540_000]
    assert all(pad.kind == "thru_hole" and pad.drill == 1_500_000 for pad in to220.pads)
    assert all(pad.size.w == pad.size.h == 2_200_000 for pad in to220.pads)
    fab = to220.graphics_on("F.Fab")[0]
    assert (fab.points[0].y, fab.points[1].y) == (1_075_000, 5_925_000)
    court = to220.graphics_on("F.CrtYd")[0]
    assert (court.points[0].y, court.points[1].y) == (-1_600_000, 6_425_000)


@pytest.mark.parametrize(
    ("name", "count", "row", "length", "width"),
    [
        ("SOIC14_TI_D0014A", 14, 5400, 1550, 600),
        ("SOIC16_TI_D0016A", 16, 5400, 1550, 600),
        ("SOIC20_TI_DW0020A", 20, 9300, 2000, 600),
        ("SOIC24_Microchip_K3X", 24, 9400, 2000, 600),
        ("SOIC28_MPS_Wide", 28, 9400, 2000, 610),
    ],
)
def test_soic_variants_follow_named_manufacturer_lands(
    name: str, count: int, row: int, length: int, width: int
) -> None:
    pads = get_footprint(f"Fenolite:{name}").pads
    assert len(pads) == count
    assert [pad.number for pad in pads] == [str(i) for i in range(1, count + 1)]
    assert (pads[0].position.x, pads[-1].position.x) == (-row * 500, row * 500)
    assert pads[0].position.y == pads[-1].position.y == (count // 2 - 1) * 635_000
    assert pads[count // 2 - 1].position.y == pads[count // 2].position.y == -(count // 2 - 1) * 635_000
    assert all((pad.size.w, pad.size.h) == (length * 1000, width * 1000) for pad in pads)


@pytest.mark.parametrize(
    ("name", "count", "pitch", "row", "length", "width"),
    [
        ("TSSOP8_Diodes", 8, 650, 5940, 1780, 450),
        ("TSSOP14_Diodes", 14, 650, 5900, 1450, 450),
        ("TSSOP16_Diodes_A1", 16, 650, 5400, 1400, 350),
        ("TSSOP20_Diodes", 20, 650, 5940, 1780, 420),
        ("TSSOP24_TI_PW0024A", 24, 650, 5800, 1500, 450),
        ("TSSOP28_Microchip_NRB", 28, 650, 5900, 1500, 450),
        ("MSOP8_Diodes", 8, 650, 3950, 1350, 450),
        ("MSOP10_Diodes", 10, 500, 3950, 1350, 300),
        ("SSOP16_Diodes_CJ", 16, 635, 5040, 1500, 410),
    ],
)
def test_fine_pitch_small_outline_source_spacing(
    name: str, count: int, pitch: int, row: int, length: int, width: int
) -> None:
    pads = get_footprint(f"Fenolite:{name}").pads
    assert len(pads) == count
    left, right = pads[: count // 2], pads[count // 2 :]
    assert [pad.number for pad in left] == [str(i) for i in range(1, count // 2 + 1)]
    assert [pad.number for pad in right] == [str(i) for i in range(count // 2 + 1, count + 1)]
    assert all(b.position.y - a.position.y == -pitch * 1000 for a, b in pairwise(left))
    assert all(b.position.y - a.position.y == pitch * 1000 for a, b in pairwise(right))
    assert all(pad.position.x == -row * 500 for pad in left)
    assert all(pad.position.x == row * 500 for pad in right)
    assert all((pad.size.w, pad.size.h) == (length * 1000, width * 1000) for pad in pads)


@pytest.mark.parametrize(
    ("name", "count", "row", "length", "width", "exposed"),
    [
        ("QFN16_Diodes_W3030_A1", 16, 3000, 700, 300, 1700),
        ("QFN20_Diodes_U4040", 20, 3700, 600, 350, 2500),
        ("QFN24_Diodes_W4040_SWP_A1", 24, 3850, 750, 300, 2500),
        ("QFN28_Diodes_W5050_A1", 28, 4700, 900, 300, 3250),
        ("QFN32_Diodes_W5050", 32, 4700, 600, 350, 3800),
    ],
)
def test_qfn_source_copper_and_independent_stencil_windows(
    name: str, count: int, row: int, length: int, width: int, exposed: int
) -> None:
    footprint = get_footprint(f"Fenolite:{name}")
    peripheral, ep = footprint.pads[:-1], footprint.pads[-1]
    assert [pad.number for pad in peripheral] == [str(i) for i in range(1, count + 1)]
    assert ep.number == "EP" and ep.position.x == ep.position.y == 0
    assert ep.size.w == ep.size.h == exposed * 1000
    assert ep.layers == ("F.Cu", "F.Mask")
    for side in range(4):
        pads = peripheral[side * count // 4 : (side + 1) * count // 4]
        assert all(
            (pad.size.w, pad.size.h)
            == ((length * 1000, width * 1000) if side in (0, 2) else (width * 1000, length * 1000))
            for pad in pads
        )
        assert all(abs(pad.position.x if side in (0, 2) else pad.position.y) == row * 500 for pad in pads)
    windows = footprint.graphics_on("F.Paste")
    assert len(windows) == 4
    area = 0
    for window in windows:
        a, b = window.points
        assert window.filled and window.width == 0
        assert -ep.size.w // 2 < a.x < b.x < ep.size.w // 2
        assert -ep.size.h // 2 < a.y < b.y < ep.size.h // 2
        area += (b.x - a.x) * (b.y - a.y)
    assert area * 100 == ep.size.w * ep.size.h * 64
    for first, second in combinations(windows, 2):
        a, b = first.points
        c, d = second.points
        assert b.x < c.x or d.x < a.x or b.y < c.y or d.y < a.y
    readback = read_footprint(write_footprint(footprint), library="Fenolite")
    assert [pad.layers for pad in readback.pads] == [pad.layers for pad in footprint.pads]
    assert [(g.points, g.width, g.filled) for g in readback.graphics_on("F.Paste")] == [
        (g.points, g.width, g.filled) for g in windows
    ]


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


@pytest.mark.parametrize(
    ("name", "count", "pitch", "row", "length", "width"),
    [
        ("QFN48_TI_RGZ0048A", 48, 500, 6800, 600, 240),
        ("TQFP44_Microchip_PT", 44, 800, 11400, 1500, 550),
        ("LQFP48_TI_PT0048A", 48, 500, 8200, 1600, 300),
        ("LQFP64_TI_PM0064A", 64, 500, 11400, 1500, 300),
        ("LQFP100_TI_PZ0100A", 100, 500, 15400, 1500, 300),
    ],
)
def test_quad_package_source_pitch_numbering_and_axes(
    name: str, count: int, pitch: int, row: int, length: int, width: int
) -> None:
    footprint = get_footprint(f"Fenolite:{name}")
    pads = footprint.pads[:count]
    assert [pad.number for pad in pads] == [str(i) for i in range(1, count + 1)]
    per_side = count // 4
    half_run = (per_side - 1) * pitch * 500
    assert (pads[0].position.x, pads[0].position.y) == (-row * 500, half_run)
    for side in range(4):
        members = pads[side * per_side : (side + 1) * per_side]
        assert all(
            (pad.size.w, pad.size.h)
            == ((length * 1000, width * 1000) if side in (0, 2) else (width * 1000, length * 1000))
            for pad in members
        )
        for first, second in pairwise(members):
            assert (
                abs(first.position.x - second.position.x) + abs(first.position.y - second.position.y)
                == pitch * 1000
            )
    assert footprint.graphics_on("F.Fab")[-1].points[0].x < 0


@pytest.mark.parametrize(
    ("name", "count", "row", "length", "width", "ep_width", "ep_height"),
    [
        ("DFN6_Diodes_W2020_US", 6, 1805, 545, 350, 850, 1550),
        ("DFN8_Diodes_W3030_UXF", 8, 2650, 550, 400, 1750, 2350),
    ],
)
def test_dfn_distinct_exposed_copper_and_stencil(
    name: str, count: int, row: int, length: int, width: int, ep_width: int, ep_height: int
) -> None:
    footprint = get_footprint(f"Fenolite:{name}")
    ep = footprint.pads[-1]
    assert len(footprint.pads) == count + 1 and ep.number == "EP"
    assert (ep.size.w, ep.size.h) == (ep_width * 1000, ep_height * 1000)
    assert ep.layers == ("F.Cu", "F.Mask")
    assert (footprint.pads[0].position.x, footprint.pads[0].position.y) == (
        -row * 500,
        (count // 2 - 1) * 325_000,
    )
    assert all((pad.size.w, pad.size.h) == (length * 1000, width * 1000) for pad in footprint.pads[:-1])
    windows = footprint.graphics_on("F.Paste")
    assert len(windows) == 4
    assert (
        sum((g.points[1].x - g.points[0].x) * (g.points[1].y - g.points[0].y) for g in windows) * 100
        == ep.size.w * ep.size.h * 64
    )
    readback = read_footprint(write_footprint(footprint), library="Fenolite")
    assert [(g.points, g.filled, g.width) for g in readback.graphics_on("F.Paste")] == [
        (g.points, g.filled, g.width) for g in windows
    ]


def test_qfn48_manufacturer_sixteen_window_stencil() -> None:
    footprint = get_footprint("Fenolite:QFN48_TI_RGZ0048A")
    ep = footprint.pads[-1]
    assert ep.size.w == ep.size.h == 5_150_000 and ep.layers == ("F.Cu", "F.Mask")
    windows = footprint.graphics_on("F.Paste")
    assert len(windows) == 16
    for g in windows:
        a, b = g.points
        assert b.x - a.x == b.y - a.y == 1_060_000
        assert g.filled and g.width == 0
        assert -2_575_000 < a.x < b.x < 2_575_000
        assert -2_575_000 < a.y < b.y < 2_575_000
    assert {(g.points[0].x + g.points[1].x) // 2 for g in windows} == {
        -1_890_000,
        -630_000,
        630_000,
        1_890_000,
    }
    readback = read_footprint(write_footprint(footprint), library="Fenolite")
    assert [(g.points, g.filled, g.width) for g in readback.graphics_on("F.Paste")] == [
        (g.points, g.filled, g.width) for g in windows
    ]


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


@pytest.mark.parametrize(
    "name,count",
    [
        ("DIP4_Vishay_VO617A", 4),
        ("DIP6_Vishay_CNY17", 6),
        ("DIP8_Microchip_P", 8),
        ("DIP14_Microchip_P", 14),
        ("DIP16_Microchip_P", 16),
        ("DIP20_Microchip_P", 20),
        ("DIP28_Microchip_SP", 28),
    ],
)
def test_dip_body_variant_and_authored_through_hole_pattern(name: str, count: int) -> None:
    footprint = get_footprint(f"Fenolite:{name}")
    assert footprint.kind == "through_hole"
    assert len(footprint.pads) == count
    assert [p.number for p in footprint.pads] == [str(i) for i in range(1, count + 1)]
    assert all(
        p.drill == 900_000 and p.kind == "thru_hole" and p.size.w == p.size.h == 1_800_000
        for p in footprint.pads
    )
    assert all(p.layers == ("*.Cu", "*.Mask") for p in footprint.pads)
    assert [p.position.x for p in footprint.pads] == [-3_810_000] * (count // 2) + [3_810_000] * (count // 2)
    assert all(b.position.y - a.position.y == -2_540_000 for a, b in pairwise(footprint.pads[: count // 2]))
    assert sum(p.position.y for p in footprint.pads) == 0
    readback = read_footprint(write_footprint(footprint), library="Fenolite")
    assert [p.drill for p in readback.pads] == [p.drill for p in footprint.pads]


def test_unknown_id_does_not_fall_back_to_external_lookup() -> None:
    with pytest.raises(KeyError, match="Fenolite:Unknown"):
        get_symbol("Fenolite:Unknown")
    with pytest.raises(KeyError, match="Fenolite:Unknown"):
        get_footprint("Fenolite:Unknown")


@pytest.mark.parametrize("columns,rows", [(1, n) for n in (1, 2, 3, 4, 6, 8, 10)] + [(2, 3), (2, 5)])
def test_standard_headers_pitch_drill_and_row_numbering(columns: int, rows: int) -> None:
    fp = get_footprint(f"Fenolite:Header_{columns}x{rows}_P2.54")
    assert len(fp.pads) == columns * rows
    assert [(p.number, p.position.x, p.position.y) for p in fp.pads] == [
        (str(row * columns + col + 1), (2 * col - columns + 1) * 1_270_000, (rows - 1 - 2 * row) * 1_270_000)
        for row in range(rows)
        for col in range(columns)
    ]
    assert all(p.drill == 1_100_000 and p.size.w == p.size.h == 1_800_000 for p in fp.pads)


@pytest.mark.parametrize("count,drill", [(2, 1_000_000), (4, 900_000)])
def test_jst_xh_bossless_top_view_has_pin_one_at_right(count: int, drill: int) -> None:
    fp = get_footprint(f"Fenolite:JST_XH_B{count}B_XH_A")
    assert len(fp.pads) == count
    assert [p.position.x for p in fp.pads] == [(count - 1 - 2 * i) * 1_250_000 for i in range(count)]
    assert all(p.position.y == 0 and p.drill == drill for p in fp.pads)
    fab = fp.graphics_on("F.Fab")[0]
    assert (fab.points[0].y, fab.points[1].y) == (-2_350_000, 3_400_000)
    assert fp.graphics_on("F.Fab")[-1].points[0].x > 0


def test_micro_usb_has_mixed_mount_pegs_shell_slots_and_top_view_contacts() -> None:
    fp = get_footprint("Fenolite:MicroUSB_B_Wurth_629105150521")
    assert len(fp.pads) == 11
    assert len({p.id for p in fp.pads}) == 11
    signals, shell, pegs = fp.pads[:5], fp.pads[5:9], fp.pads[9:]
    assert [(p.number, p.position.x, p.position.y) for p in signals] == [
        (str(i + 1), (i - 2) * 650_000, 5_500_000) for i in range(5)
    ]
    assert all(p.size.w == 450_000 and p.size.h == 1_300_000 for p in signals)
    assert all(p.number == "SH" and p.layers == ("*.Cu", "*.Mask") for p in shell)
    assert all(p.kind == "np_thru_hole" and p.number == "" and p.drill == 800_000 for p in pegs)
    assert [(p.position.x, p.position.y) for p in pegs] == [(-2_500_000, 4_550_000), (2_500_000, 4_550_000)]
    for p, length in zip(shell, (1_400_000, 1_400_000, 1_300_000, 1_300_000), strict=True):
        assert p.padstack and p.padstack.hole_shape == "slot"
        assert p.padstack.hole_length == length and p.padstack.hole_rotation == 90_000_000
    text = write_footprint(fp)
    assert "(drill oval 0.85 1.4)" in text and "(drill oval 0.55 1.3)" in text
    readback = read_footprint(text, library="Fenolite")
    assert [(p.kind, p.drill, p.layers) for p in readback.pads] == [
        (p.kind, p.drill, p.layers) for p in fp.pads
    ]
    for before, after in zip(shell, readback.pads[5:9], strict=True):
        assert before.padstack and after.padstack
        assert (after.padstack.hole_shape, after.padstack.hole_length, after.padstack.hole_rotation) == (
            before.padstack.hole_shape,
            before.padstack.hole_length,
            before.padstack.hole_rotation,
        )


@pytest.mark.parametrize(
    "name,center,width,height",
    [
        ("LED0603_Kingbright_APT1608SURCK", 825_000, 800_000, 800_000),
        ("LED0805_Kingbright_APT2012SURCK", 1_175_000, 1_250_000, 1_100_000),
    ],
)
def test_led_recommended_lands_have_distinct_chip_geometry_and_cathode_mark(
    name: str, center: int, width: int, height: int
) -> None:
    fp = get_footprint(f"Fenolite:{name}")
    assert [p.position.x for p in fp.pads] == [-center, center]
    assert [(p.size.w, p.size.h) for p in fp.pads] == [(width, height)] * 2
    assert fp.graphics_on("F.Fab")[-1].points[0].x < 0


@pytest.mark.parametrize(
    "name,pitch,drill,copper",
    [
        ("R_Axial_Vishay_MRS16_P7.62", 7_620_000, 800_000, 1_600_000),
        ("R_Axial_Vishay_MRS25_P10.16", 10_160_000, 900_000, 1_800_000),
        ("C_Film_Wima_MKS02_L4.6_W2.5_P2.5", 2_500_000, 700_000, 1_400_000),
        ("C_Film_Wima_MKS2_L7.2_W2.5_P5", 5_000_000, 800_000, 1_600_000),
    ],
)
def test_leaded_passives_have_explicit_pitch_and_inferred_drills(
    name: str, pitch: int, drill: int, copper: int
) -> None:
    fp = get_footprint(f"Fenolite:{name}")
    assert [p.position.x for p in fp.pads] == [-pitch // 2, pitch // 2]
    assert all(p.drill == drill and p.size.w == p.size.h == copper for p in fp.pads)
    assert fp.kind == "through_hole"


def test_abm8_sourced_inner_gaps_and_top_view_pin_order() -> None:
    fp = get_footprint("Fenolite:Crystal_3225_Abracon_ABM8")
    assert [(p.number, p.position.x, p.position.y) for p in fp.pads] == [
        ("1", -1_150_000, -875_000),
        ("2", 1_150_000, -875_000),
        ("3", 1_150_000, 875_000),
        ("4", -1_150_000, 875_000),
    ]
    assert all(p.size.w == 1_300_000 and p.size.h == 1_050_000 for p in fp.pads)
    assert fp.pads[1].position.x - fp.pads[0].position.x - fp.pads[0].size.w == 1_000_000
    assert fp.pads[3].position.y - fp.pads[0].position.y - fp.pads[0].size.h == 700_000


@pytest.mark.parametrize(
    "name,positions,drill",
    [
        (
            "SW_Tact_Wurth_430181038816",
            [
                (-3_500_000, 1_500_000),
                (3_500_000, 1_500_000),
                (-3_500_000, -1_500_000),
                (3_500_000, -1_500_000),
            ],
            None,
        ),
        (
            "SW_Tact_Wurth_430186043716",
            [
                (-3_250_000, 2_250_000),
                (-3_250_000, -2_250_000),
                (3_250_000, 2_250_000),
                (3_250_000, -2_250_000),
            ],
            1_000_000,
        ),
    ],
)
def test_tact_switches_preserve_variant_pin_order(
    name: str, positions: list[tuple[int, int]], drill: int | None
) -> None:
    fp = get_footprint(f"Fenolite:{name}")
    assert [p.number for p in fp.pads] == ["1", "2", "3", "4"]
    assert [(p.position.x, p.position.y) for p in fp.pads] == positions
    assert all(p.drill == drill for p in fp.pads)
    assert fp.graphics_on("F.Fab")[-1].kind == "circle"


@pytest.mark.parametrize(
    "name,diameter,pitch",
    [
        ("C_Electrolytic_Panasonic_FR_D5_P2", 5_000_000, 2_000_000),
        ("C_Electrolytic_Panasonic_FR_D6.3_P2.5", 6_300_000, 2_500_000),
    ],
)
def test_radial_electrolytic_circle_pitch_and_positive_left(name: str, diameter: int, pitch: int) -> None:
    fp = get_footprint(f"Fenolite:{name}")
    assert [p.position.x for p in fp.pads] == [-pitch // 2, pitch // 2]
    assert all(p.drill == 800_000 and p.size.w == 1_600_000 for p in fp.pads)
    fab = fp.graphics_on("F.Fab")
    assert fab[0].kind == "circle" and fab[0].points[1].x == diameter // 2
    assert all(g.points[0].x < 0 for g in fab[1:3])
    assert fab[3].points[0].x > 0
    assert fp.graphics_on("F.CrtYd")[0].points[1].x >= diameter // 2 + 750_000


@pytest.mark.parametrize(
    "name,drill", [("MountingHole_M2_D2.4", 2_400_000), ("MountingHole_M3_D3.4", 3_400_000)]
)
def test_mounting_holes_are_npth_without_electrical_number_or_bom(name: str, drill: int) -> None:
    fp = get_footprint(f"Fenolite:{name}")
    assert fp.kind == "unspecified" and "exclude_from_bom" in fp.flags
    assert len(fp.pads) == 1 and fp.pads[0].number == ""
    assert fp.pads[0].kind == "np_thru_hole" and fp.pads[0].drill == drill
    readback = read_footprint(write_footprint(fp), library="Fenolite")
    assert readback.flags == fp.flags and readback.pads[0].kind == "np_thru_hole"


def test_testpoint_is_round_copper_with_mask_and_no_stencil_or_bom() -> None:
    fp = get_footprint("Fenolite:TestPoint_SMD_D1.0")
    pad = fp.pads[0]
    assert pad.shape == "circle" and pad.size.w == pad.size.h == 1_000_000
    assert pad.layers == ("F.Cu", "F.Mask") and pad.drill is None
    assert "exclude_from_bom" in fp.flags and not fp.graphics_on("F.Paste")
    readback = read_footprint(write_footprint(fp), library="Fenolite")
    assert readback.pads[0].layers == pad.layers and readback.flags == fp.flags


def test_ws2812b_v6_sourced_gaps_numbering_and_pin_three_corner() -> None:
    fp = get_footprint("Fenolite:LED5050_Worldsemi_WS2812B_V6")
    assert [(p.number, p.position.x, p.position.y) for p in fp.pads] == [
        ("1", -2_450_000, 1_650_000),
        ("2", -2_450_000, -1_650_000),
        ("3", 2_450_000, -1_650_000),
        ("4", 2_450_000, 1_650_000),
    ]
    assert all(p.size.w == 1_500_000 and p.size.h == 1_000_000 for p in fp.pads)
    assert fp.pads[3].position.x - fp.pads[0].position.x - fp.pads[0].size.w == 3_400_000
    assert fp.pads[0].position.y - fp.pads[1].position.y + fp.pads[0].size.h == 4_300_000
    corner = fp.graphics_on("F.Fab")[1]
    assert all(p.x > 0 and p.y < 0 for p in corner.points)
