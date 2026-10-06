# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium libraries as library definitions (capability altium-import, "Footprint libraries" and "Symbol
libraries"; change c0043)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import _altium_records as rec

from fenolite.backends.altium.adapter.library import import_footprints, import_symbols
from fenolite.backends.altium.adapter.pins import PIN_TYPES
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.library import Library, SymbolDef

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "tests" / "data" / "altium"
MINI = ROOT / "tests" / "data" / "libs" / "Mini_v9.pretty"
DEMO = ROOT / "examples" / "altium_kicad" / "FenoliteDemo.kicad_sym"
MIL = rec.MIL


def blink_footprints(issues: list[Issue] | None = None, name: str = "blink") -> Library:
    data = (DATA / "blink" / "blink.PcbLib").read_bytes()
    return import_footprints(
        read_pcblib(data),
        name=name,
        file="blink.PcbLib",
        sha256=hashlib.sha256(data).hexdigest(),
        issues=issues,
    )


def example_symbols(issues: list[Issue] | None = None) -> Library:
    data = (DATA / "kicad_example" / "altium_kicad.SchLib").read_bytes()
    return import_symbols(
        read_schlib(data), name="altium_kicad", file="altium_kicad.SchLib",
        sha256=hashlib.sha256(data).hexdigest(), issues=issues,
    )  # fmt: skip


# --- footprints -----------------------------------------------------------------------------------------


def test_footprints_of_the_blink_library_equal_their_kicad_sources() -> None:
    library = blink_footprints()
    assert library.name == "blink" and library.symbols == ()
    assert sorted(f.name for f in library.footprints) == [
        "Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603",
    ]  # fmt: skip
    ids = [e.id for f in library.footprints for e in (f, *f.pads, *f.graphics)]
    assert len(ids) == len(set(ids))
    for footprint in library.footprints:
        source = KicadBackend().read(MINI / f"{footprint.name}.kicad_mod").content
        assert isinstance(source, Library)
        (want,) = source.footprints
        assert footprint.kind == want.kind and footprint.library == "blink"
        assert footprint.native_ids == {"altium": f"blink:{footprint.name}"}
        assert footprint.id == derived_id("fpd", "altium", f"blink:{footprint.name}")
        theirs = {pad.number: pad for pad in want.pads}
        assert len(footprint.pads) == len(want.pads)
        for pad in footprint.pads:
            other = theirs[pad.number]
            assert (pad.shape, pad.kind) == (other.shape, other.kind), (footprint.name, pad.number)
            assert abs((pad.drill or 0) - (other.drill or 0)) <= 2
            assert abs(pad.position.x - other.position.x) <= 2 and abs(pad.position.y - other.position.y) <= 2
            assert pad.padstack is None and pad.net_id is None
            assert pad.layers == (("*.Cu",) if pad.drill else ("F.Cu",))
        assert footprint.graphics and {g.layer for g in footprint.graphics} <= {
            "F.SilkS", "F.Cu", "Mech.13", "Mech.15", "Mech.1",
        }  # fmt: skip


def test_footprints_same_file_under_two_names() -> None:
    first, second = blink_footprints(name="A"), blink_footprints(name="B")
    again = blink_footprints(name="A")
    ids_a = {e.id for f in first.footprints for e in (f, *f.pads, *f.graphics)}
    ids_b = {e.id for f in second.footprints for e in (f, *f.pads, *f.graphics)}
    assert not ids_a & ids_b
    assert [p.id for f in first.footprints for p in f.pads] == [
        p.id for f in again.footprints for p in f.pads
    ]


def test_footprints_definition_from_records() -> None:
    issues: list[Issue] = []
    primitives = [
        rec.pad("1", (-50 * MIL, 0), layer=1),
        rec.pad("2", (50 * MIL, 0), hole=30 * MIL, layer=74, stack_mode=1, mid=(50 * MIL, 50 * MIL)),
        rec.pad("2", (50 * MIL, 0), hole=30 * MIL, layer=74, stack_mode=1, mid=(50 * MIL, 50 * MIL)),
        rec.track((-100 * MIL, 100 * MIL), (100 * MIL, 100 * MIL), layer=33),
        rec.arc((0, 0), 20 * MIL, 0.0, 360.0, layer=69),
        rec.fill((0, 0), (10 * MIL, 10 * MIL), layer=33),
        rec.region([(0, 0), (9 * MIL, 0), (0, 9 * MIL)], layer=71),
        rec.text(".Designator", layer=33),
    ]
    part = rec.footprint(
        "CONN", primitives, description="A connector", height="120mil", unique_ids={0: "PADUID01"}
    )
    library = import_footprints(
        rec.pcb_library(part, rec.footprint("EMPTY")), name="Parts", file="Parts.PcbLib", sha256=rec.SHA,
        issues=issues,
    )  # fmt: skip
    conn, empty = library.footprints
    assert (conn.kind, empty.kind) == ("through_hole", "unspecified")
    assert conn.description == "A connector"
    assert conn.properties == {"Description": "A connector", "Height": "120mil"} and empty.properties == {}
    surface, hole, twin = conn.pads
    assert (
        surface.layers == ("F.Cu",) and hole.layers == ("*.Cu",) and surface.position == Point(-1_270_000, 0)
    )
    assert surface.native_ids == {"altium": "Parts:CONN:PADUID01"} and hole.native_ids == {}
    assert hole.id != twin.id and hole.padstack is not None
    assert [layer.layer for layer in hole.padstack.layers] == ["F.Cu", "In*.Cu", "B.Cu"]
    assert [layer.size.w for layer in hole.padstack.layers] == [1_524_000, 1_270_000, 1_524_000]
    assert [(g.kind, g.layer, g.filled) for g in conn.graphics] == [
        ("line", "F.SilkS", False),
        ("circle", "Mech.13", False),
        ("rect", "F.SilkS", True),
        ("polygon", "Mech.15", True),
    ]
    assert conn.provenance is not None and conn.provenance.locator == "CONN/Data"
    assert surface.provenance is not None and surface.provenance.locator == "CONN/Data#0"
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert unmapped.message.endswith("texts 1")


def test_footprints_body_of_a_library_definition() -> None:
    from fenolite.backends.altium.read.pcbprims import RawPrimitive

    raw = rec.body_bytes([(-50, -25), (50, -25), (50, 25), (-50, 25)], component=None)
    body = RawPrimitive(12, (raw[5:],), raw)
    library = import_footprints(
        rec.pcb_library(rec.footprint("R", [body])), name="Parts", file="Parts.PcbLib", sha256=rec.SHA
    )
    (found,) = library.footprints[0].bodies
    assert (found.kind, found.height, found.layer) == ("extruded", 1_016_000, "Mech.13")
    assert found.outline[0] == Point(-1_270_000, 635_000) and len(found.outline) == 4


# --- symbols --------------------------------------------------------------------------------------------


def test_pin_type_table() -> None:
    assert dict(PIN_TYPES) == {
        0: "input", 1: "bidirectional", 2: "output", 3: "open_collector", 4: "passive", 5: "tri_state",
        6: "open_emitter", 7: "power_in",
    }  # fmt: skip


LOSSLESS_TYPES = set(PIN_TYPES.values())
LOSSLESS_SHAPES = {"line", "inverted", "clock", "inverted_clock"}


def test_symbols_of_the_kicad_example_equal_their_source() -> None:
    """kicad_example: each symbol has the source's pins by (unit, number)."""
    issues: list[Issue] = []
    library = example_symbols(issues)
    source = KicadBackend().read(DEMO).content
    assert isinstance(source, Library) and library.footprints == ()
    theirs = {symbol.name: symbol for symbol in source.symbols}
    assert sorted(s.name for s in library.symbols) == sorted(theirs) and len(theirs) == 4
    compared = 0
    for symbol in library.symbols:
        want: SymbolDef = theirs[symbol.name]
        assert symbol.unit_count == want.unit_count, symbol.name
        assert symbol.native_ids == {"altium": f"altium_kicad:{symbol.name}"} and symbol.power == ""
        mine = {(pin.unit, pin.number): pin for pin in symbol.pins}
        assert len(mine) == len(symbol.pins) == len(want.pins), symbol.name
        for pin in want.pins:
            got = mine[(pin.unit, pin.number)]
            assert (got.position, got.rotation, got.length) == (pin.position, pin.rotation, pin.length)
            assert got.hidden == pin.hidden and got.body_style == 1
            if pin.etype in LOSSLESS_TYPES and pin.shape in LOSSLESS_SHAPES:
                assert (got.etype, got.shape) == (pin.etype, pin.shape), (symbol.name, pin.number)
                compared += 1
            if "~{" not in pin.name and pin.name != "~":
                assert got.name == pin.name, (symbol.name, pin.number)
        assert symbol.properties.get("Reference", "").rstrip("?") == want.reference
    assert compared >= 10
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "symbol-graphics" in unmapped.message


def test_symbols_units_and_properties() -> None:
    library = example_symbols()
    by_name = {symbol.name: symbol for symbol in library.symbols}
    dual = next(s for s in library.symbols if s.unit_count == 2)
    assert [(u.unit, u.body_style) for u in dual.units] == [(1, 1), (2, 1)]
    assert {pin.unit for pin in dual.pins} <= {0, 1, 2}
    for symbol in by_name.values():
        assert symbol.id == derived_id("sym", "altium", f"altium_kicad:{symbol.name}")
        assert symbol.provenance is not None and symbol.provenance.file == "altium_kicad.SchLib"
        assert "Value" in symbol.properties
    assert any(symbol.footprint for symbol in by_name.values())
