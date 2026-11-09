# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A KiCad bus group that crosses a sheet is written as an Altium harness block placed in free space
(``backends.altium.drawn_harness``, change c0470, task 5.4)."""

from __future__ import annotations

from fenolite.backends.altium import drawn_harness as dh

_HEIGHT = 8_000 * dh.MIL  # an 11 000 x 8 000 mil sheet, in file units
_SIZE = (11_000, 8_000)


def _end(start: tuple[int, int] = (2_000, 2_000)) -> dh.GroupEnd:
    return dh.GroupEnd((start,), (), ("UART",), ("RX", "TX"), dh.harness_type(("RX", "TX")), "root")


def _wire(*points: tuple[int, int]) -> list[tuple[str, str]]:
    """A wire record through ``points`` in mil from the top-left."""
    fields = [("RECORD", "27"), ("LOCATIONCOUNT", str(len(points)))]
    for i, (x, y) in enumerate(points, start=1):
        fields += [(f"X{i}", str(x // 10)), (f"Y{i}", str((_HEIGHT // dh.MIL - y) // 10))]
    return fields


def test_harness_type_names_the_entries_in_order() -> None:
    assert dh.harness_type(("RX", "TX")) == dh.harness_type(("RX", "TX"))
    assert dh.harness_type(("RX", "TX")) != dh.harness_type(("TX", "RX"))
    assert dh.harness_type(("A",)).startswith("KiCadBus_")


def test_occupancy_reads_wires_ports_and_areas_and_keeps_buses_inert() -> None:
    records = [
        _wire((1_000, 1_000), (1_000, 2_000)),
        [("RECORD", "26"), ("LOCATIONCOUNT", "2"), ("X1", "0"), ("Y1", "0"), ("X2", "100"), ("Y2", "0")],
        [("RECORD", "18"), ("LOCATION.X", "300"), ("LOCATION.Y", "300"), ("WIDTH", "50"), ("STYLE", "5")],
        [("RECORD", "15"), ("LOCATION.X", "400"), ("LOCATION.Y", "400"), ("XSIZE", "60"), ("YSIZE", "40")],
        [("RECORD", "25"), ("LOCATION.X", "500"), ("LOCATION.Y", "500")],
    ]
    found = dh.occupancy(records, _HEIGHT)
    mil = dh.MIL
    assert ((1_000 * mil, 1_000 * mil), (1_000 * mil, 2_000 * mil)) in found.segments
    assert len(found.buses) == 1 and found.buses[0][0] not in found.points  # a bus joins nothing
    port = (3_000 * mil, _HEIGHT - 3_000 * mil)
    assert (port, (port[0], port[1] - 500 * mil)) in found.segments  # a standing port reaches upwards
    left, top = 4_000 * mil, _HEIGHT - 4_000 * mil
    assert found.rects == [(left, top, left + 600 * mil, top + 400 * mil)]
    assert (5_000 * mil, _HEIGHT - 5_000 * mil) in found.points


def test_a_block_on_an_empty_sheet_starts_at_its_end_and_holds_nothing() -> None:
    placed = dh.place_all([_end()], [], _HEIGHT, _SIZE)
    assert isinstance(placed, list) and len(placed) == 1
    block = placed[0].block
    assert block.entries == (("RX", None), ("TX", None))
    lines = [*placed[0].lines, block.line]
    assert lines[0][0] == (2_000, 2_000)  # the harness line leaves from the group's end
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in lines)  # orthogonal runs
    assert [text for _, _, text in placed[0].stubs] == ["RX", "TX"]
    assert not (block.x <= 2_000 <= block.x + block.width and block.y <= 2_000 <= block.y + block.height)


def test_a_block_line_never_touches_a_wire_of_the_sheet() -> None:
    wall = _wire((1_500, 500), (1_500, 7_500))
    placed = dh.place_all([_end()], [wall], _HEIGHT, _SIZE)
    assert isinstance(placed, list)
    lines = [*placed[0].lines, placed[0].block.line]
    assert not any(min(a[0], b[0]) <= 1_500 <= max(a[0], b[0]) and a[0] != b[0] for a, b in lines)


def test_no_free_space_names_the_end() -> None:
    end = _end((100, 100))
    found = dh.place_all([end], [], 400 * dh.MIL, (400, 400))
    assert found is end


def test_two_ends_get_two_blocks_that_do_not_overlap() -> None:
    one, two = _end((2_000, 2_000)), _end((6_000, 5_000))
    placed = dh.place_all([one, two], [], _HEIGHT, _SIZE)
    assert isinstance(placed, list) and len(placed) == 2
    a, b = (p.block for p in placed)
    assert a.x + a.width < b.x or b.x + b.width < a.x or a.y + a.height < b.y or b.y + b.height < a.y


def test_an_end_off_kicads_grid_is_placed_on_altiums_grid() -> None:
    """An Altium sheet entry may lie on 10 mil but not on 50: the block is found on ``FINE_GRID``
    (change c0470)."""
    placed = dh.place_all([_end((2_010, 2_010))], [], _HEIGHT, _SIZE)
    assert isinstance(placed, list) and len(placed) == 1
    lines = [*placed[0].lines, placed[0].block.line]
    assert lines[0][0] == (2_010, 2_010)
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in lines)


def test_a_full_sheet_has_room_once_it_is_wider() -> None:
    """A sheet without free space places the block when it grows to the right (``drawn._Sheet``, change
    c0470): the height, and so every written point, stays."""
    height = 1_000 * dh.MIL
    end = _end((600, 500))
    assert dh.place_all([end], [], height, (900, 1_000)) is end
    placed = dh.place_all([end], [], height, (900 + 2 * 2_000, 1_000))  # two growths of drawn.HARNESS_GROWTH
    assert isinstance(placed, list) and placed[0].block.x + placed[0].block.width < 4_900
