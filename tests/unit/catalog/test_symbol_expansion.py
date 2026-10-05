# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Publicly sourced conceptual roles and independently drawn polarity/topology."""

from pathlib import Path

import pytest

from fenolite.catalog import get_symbol

SEMICONDUCTOR_ROLES = {
    "BJT_NPN": ("B", "C", "E"),
    "BJT_PNP": ("B", "C", "E"),
    "MOSFET_N_Channel": ("G", "D", "S"),
    "MOSFET_P_Channel": ("G", "D", "S"),
    "IGBT": ("G", "C", "E"),
    "SCR": ("A", "K", "G"),
    "TRIAC": ("MT2", "MT1", "G"),
    "Schottky_Diode": ("A", "K"),
    "TVS_Bidirectional": ("A", "B"),
}


def test_exact_planned_inventory_and_source_registration() -> None:
    inventory = Path("docs/catalog/target-20-symbols.md").read_text()
    rows = [
        line.split("|")
        for line in inventory.splitlines()
        if line.startswith("| ") and line.split("|")[1].strip().isdigit()
    ]
    assert [int(row[1]) for row in rows] == list(range(1, 21))
    assert len({row[2] for row in rows}) == 20
    sources = Path("docs/evidence/sources.md").read_text()
    for row in rows:
        assert row[3].strip() and row[4].strip()
        for source in row[5].strip().split(", "):
            assert f"| {source} | https://" in sources


@pytest.mark.parametrize("name,roles", SEMICONDUCTOR_ROLES.items())
def test_new_semiconductors_use_conceptual_roles_without_footprint(name: str, roles: tuple[str, ...]) -> None:
    symbol = get_symbol(f"Fenolite:{name}")
    assert tuple(p.name for p in symbol.pins) == roles
    assert tuple(p.number for p in symbol.pins) == tuple(str(i + 1) for i in range(len(roles)))
    assert "Footprint" not in symbol.properties
    assert "not a device pinout" in symbol.properties["Description"]
    assert len({g for g in symbol.graphics}) == len(symbol.graphics)


def _polygons(name: str) -> list[tuple[tuple[int, int], ...]]:
    return [
        tuple((p.x // 1000, p.y // 1000) for p in g.points)
        for g in get_symbol(f"Fenolite:{name}").graphics
        if g.kind == "polygon"
    ]


def _lines(name: str) -> set[tuple[tuple[int, int], ...]]:
    return {
        tuple((p.x // 1000, p.y // 1000) for p in g.points)
        for g in get_symbol(f"Fenolite:{name}").graphics
        if g.kind == "line"
    }


def test_bipolar_arrows_distinguish_npn_and_pnp() -> None:
    outgoing = _polygons("BJT_NPN")[0]
    incoming = _polygons("BJT_PNP")[0]
    assert outgoing[0][0] > max(p[0] for p in outgoing[1:])
    assert outgoing[0][1] < sum(p[1] for p in outgoing[1:]) / 2
    assert incoming[0][0] < min(p[0] for p in incoming[1:])
    assert incoming[0][1] > sum(p[1] for p in incoming[1:]) / 2
    assert _lines("BJT_NPN") == _lines("BJT_PNP")


@pytest.mark.parametrize("name,direction", [("MOSFET_N_Channel", 1), ("MOSFET_P_Channel", -1)])
def test_enhancement_mosfet_gate_channel_body_arrow_and_diode(name: str, direction: int) -> None:
    lines = _lines(name)
    channel = sorted((a[1], b[1]) for a, b in lines if a[0] == b[0] == 0)
    assert channel == [(-1905, -1016), (-508, 508), (1016, 1905)]
    assert ((-1270, -1905), (-1270, 1905)) in lines
    # No gate conductor bridges the isolated gate to the channel.
    assert not any(min(a[0], b[0]) < 0 <= max(a[0], b[0]) for a, b in lines)
    arrow, diode = _polygons(name)
    arrow_x = arrow[0][0] - sum(p[0] for p in arrow[1:]) // 2
    assert arrow_x * direction < 0
    assert diode[2][1] * direction > 0
    assert all(p[1] * direction < 0 for p in diode[:2])
    assert ((3210, direction * 600), (4410, direction * 600)) in lines
    assert ((2540, 0), (2540, -1524)) in lines


def test_igbt_has_isolated_gate_outgoing_emitter_and_no_mandatory_diode() -> None:
    assert len(_polygons("IGBT")) == 1
    tip, *base = _polygons("IGBT")[0]
    assert tip[0] > max(p[0] for p in base) and tip[1] < sum(p[1] for p in base) / 2
    assert ((-2032, -1905), (-2032, 1905)) in _lines("IGBT")
    assert ((-1270, -1905), (-1270, 1905)) in _lines("IGBT")


def test_thyristor_gate_enters_cathode_or_mt1_side() -> None:
    assert ((-2540, -2540), (0, -1270)) in _lines("SCR")
    assert ((-2540, -2540), (-1270, -1270)) in _lines("TRIAC")
    assert len(_polygons("SCR")) == 1
    first, second = _polygons("TRIAC")
    assert first[2][1] < first[0][1] and second[2][1] > second[0][1]
    for name in ("SCR", "TRIAC"):
        pins = {p.name: p for p in get_symbol(f"Fenolite:{name}").pins}
        assert pins["G"].etype == "input"
        assert pins["G"].position.y < 0


def test_schottky_cathode_is_continuous_and_tvs_is_opposed_nonpolar() -> None:
    s = get_symbol("Fenolite:Schottky_Diode")
    path = [g for g in s.graphics if g.kind == "line"]
    assert len(path) == 5
    assert all(a.points[-1] == b.points[0] for a, b in zip(path, path[1:], strict=False))
    left, right = _polygons("TVS_Bidirectional")
    assert left[1] == right[1] == (0, 0)
    assert left[0][0] < 0 < right[0][0]
    assert [p.name for p in get_symbol("Fenolite:TVS_Bidirectional").pins] == ["A", "B"]


ADDITIONAL_ROLES = {
    "Potentiometer": ("A", "W", "B"),
    "Thermistor_NTC": ("A", "B"),
    "Thermistor_PTC": ("A", "B"),
    "Crystal": ("X1", "X2"),
    "Switch_SPST": ("A", "B"),
    "Switch_SPDT": ("COM", "NC", "NO"),
    "Pushbutton_NO": ("A1", "A2", "B1", "B2"),
    "Relay_SPDT": ("COIL1", "COIL2", "COM", "NC", "NO"),
    "Transformer": ("P1", "P2", "S1", "S2"),
    "Photodiode": ("A", "K"),
    "Phototransistor": ("C", "E"),
}


@pytest.mark.parametrize("name,roles", ADDITIONAL_ROLES.items())
def test_remaining_symbol_roles_and_explicit_assignment(name: str, roles: tuple[str, ...]) -> None:
    test_new_semiconductors_use_conceptual_roles_without_footprint(name, roles)


def _stem_ends(name: str) -> dict[str, tuple[int, int]]:
    ends = {}
    for pin in get_symbol(f"Fenolite:{name}").pins:
        dx, dy = {0: (1, 0), 90_000_000: (0, 1), 180_000_000: (-1, 0), 270_000_000: (0, -1)}[pin.rotation]
        ends[pin.name] = (
            (pin.position.x + dx * pin.length) // 1000,
            (pin.position.y + dy * pin.length) // 1000,
        )
    return ends


def _connected(name: str, first: str, second: str) -> bool:
    # Trace only line geometry: circles are contact decorations, and separate
    # arrow polygons do not turn optical or mechanical cues into conductors.
    lines = _lines(name)
    ends = _stem_ends(name)
    nodes = set(ends.values()) | {p for line in lines for p in line}

    def on_segment(p: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> bool:
        return (
            (p[0] - a[0]) * (b[1] - a[1]) == (p[1] - a[1]) * (b[0] - a[0])
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
        )

    visited = {ends[first]}
    while True:
        reached = {
            n
            for a, b in lines
            if any(on_segment(v, a, b) for v in visited)
            for n in nodes
            if on_segment(n, a, b)
        }
        if reached <= visited:
            return ends[second] in visited
        visited |= reached


def test_potentiometer_wiper_meets_actual_zigzag_vertex() -> None:
    from fenolite.core.coords import Point

    symbol = get_symbol("Fenolite:Potentiometer")
    resistor = get_symbol("Fenolite:Resistor")
    assert symbol.graphics[:8] == resistor.graphics
    wiper_end = symbol.graphics[8].points[-1]
    assert wiper_end == Point(635_000, 1_050_000)
    assert any(wiper_end in g.points for g in resistor.graphics)
    assert symbol.graphics[-1].points[0] == wiper_end
    assert _connected("Potentiometer", "A", "W")
    assert _connected("Potentiometer", "B", "W")


def test_temperature_coefficient_signs_differ_only_by_plus_stroke() -> None:
    ntc = _lines("Thermistor_NTC")
    ptc = _lines("Thermistor_PTC")
    assert ptc - ntc == {((1150, 2100), (1150, 2900))}
    assert ntc <= ptc
    assert ((750, 2500), (1550, 2500)) in ntc
    assert ((2350, 3000), (3550, 3000)) in ntc
    assert ((2950, 3000), (2950, 1900)) in ntc


def test_crystal_body_and_electrodes_are_separate() -> None:
    symbol = get_symbol("Fenolite:Crystal")
    body = next(g for g in symbol.graphics if g.kind == "rect")
    assert body.points[0].x > -2_540_000 and body.points[1].x < 2_540_000
    assert not _connected("Crystal", "X1", "X2")


def test_switches_and_pushbutton_show_resting_contacts() -> None:
    assert not _connected("Switch_SPST", "A", "B")
    assert _connected("Switch_SPDT", "COM", "NC")
    assert not _connected("Switch_SPDT", "COM", "NO")
    assert _connected("Pushbutton_NO", "A1", "A2")
    assert _connected("Pushbutton_NO", "B1", "B2")
    assert not _connected("Pushbutton_NO", "A1", "B1")
    assert ((-1905, 1270), (1905, 1270)) in _lines("Pushbutton_NO")


def test_relay_resting_contact_and_coil_are_independent() -> None:
    assert _connected("Relay_SPDT", "COIL1", "COIL2")
    assert _connected("Relay_SPDT", "COM", "NC")
    assert not _connected("Relay_SPDT", "COM", "NO")
    assert not _connected("Relay_SPDT", "COIL1", "COM")
    assert len([g for g in get_symbol("Fenolite:Relay_SPDT").graphics if g.width == 180_000]) == 5


def test_transformer_windings_have_separate_terminals_and_phase_marks() -> None:
    assert _connected("Transformer", "P1", "P2")
    assert _connected("Transformer", "S1", "S2")
    assert not _connected("Transformer", "P1", "S1")
    dots = [g for g in get_symbol("Fenolite:Transformer").graphics if g.kind == "circle"]
    assert len(dots) == 2 and all(g.points[0].y == 1_905_000 for g in dots)
    assert all(g.width == 320_000 for g in dots)


@pytest.mark.parametrize("name,center", [("Photodiode", (0, 0)), ("Phototransistor", (-1270, 0))])
def test_optical_arrows_point_inward(name: str, center: tuple[int, int]) -> None:
    symbol = get_symbol(f"Fenolite:{name}")
    # The last two arrowhead polygons identify the incident-light rays.
    heads = [g.points[0] for g in symbol.graphics if g.kind == "polygon"][-2:]
    for head in heads:
        ray = next(g for g in symbol.graphics if g.kind == "line" and g.points[-1] == head)
        distances = [(p.x // 1000 - center[0]) ** 2 + (p.y // 1000 - center[1]) ** 2 for p in ray.points]
        assert distances[1] < distances[0]
    if name == "Phototransistor":
        assert tuple(p.name for p in symbol.pins) == ("C", "E")
        assert _polygons(name)[0] == _polygons("BJT_NPN")[0]


def test_all_49_symbols_include_exact_expansion_and_distinct_new_drawings() -> None:
    from fenolite.catalog import list_entries

    entries = list_entries(kind="symbol")
    assert len(entries) == 49
    names = set(SEMICONDUCTOR_ROLES) | set(ADDITIONAL_ROLES)
    assert len(names) == 20
    inventory = Path("docs/catalog/target-20-symbols.md").read_text()
    assert all(f"`{name}`" in inventory for name in names)
    assert {f"Fenolite:{name}" for name in names} <= {e.lib_id for e in entries}
    patterns = {get_symbol(f"Fenolite:{name}").graphics for name in names}
    assert len(patterns) == 20
