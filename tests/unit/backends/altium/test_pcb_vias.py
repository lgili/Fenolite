# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Blind and buried vias of the Altium PCB document (capability altium-pcb-writer, "Blind and buried via
records"; change c0085)."""

from __future__ import annotations

import dataclasses

import pytest
from _altium_board6 import LAYERS, at, bare_spec, imported_point, near, read_back

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.pcbdoc import (
    unstated_tenting,
    unwritten_features,
    via_tenting,
    write_pcbdoc,
)
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.model.board import Via, ViaProtection


def via(key: str, x: float, layers: tuple[str, ...], kind: str = "through", **changes: object) -> Via:
    fields: dict[str, object] = {
        "id": f"via_{key}",
        "position": at(x, 10),
        "diameter": 600_000,
        "drill": 300_000,
        "layers": layers,
        "via_type": kind,
    }
    return Via(**{**fields, **changes})  # type: ignore[arg-type]


THREE = (
    via("a", 10, ("F.Cu", "B.Cu")),
    via("b", 12, ("F.Cu", "In1.Cu"), "blind"),
    via("c", 14, ("In1.Cu", "In2.Cu"), "buried"),
)


def test_three_spans() -> None:
    """Scenario "Three spans": the three vias have their spans and the board record three drill pairs."""
    document, design = read_back(bare_spec(copper_layers=LAYERS, vias=THREE))
    assert [(v.start_layer, v.end_layer) for v in document.vias] == [(1, 32), (1, 2), (2, 3)]
    assert document.board.layer_pairs == (("TOP", "BOTTOM"), ("TOP", "MID1"), ("MID1", "MID2"))
    assert design.board is not None
    found = {(v.layers, v.via_type) for v in design.board.vias}
    assert found == {(v.layers, v.via_type) for v in THREE}
    for wanted in THREE:
        (read,) = [v for v in design.board.vias if v.layers == wanted.layers]
        assert near(read.position, imported_point(wanted.position))
        assert abs(read.diameter - wanted.diameter) <= 2 and abs(read.drill - wanted.drill) <= 2


def test_one_drill_pair_per_distinct_span() -> None:
    vias = (*THREE, via("d", 16, ("In1.Cu", "F.Cu"), "blind"), via("e", 18, ("In4.Cu", "B.Cu"), "blind"))
    document, _ = read_back(bare_spec(copper_layers=LAYERS, vias=vias))
    assert document.board.layer_pairs == (
        ("TOP", "BOTTOM"), ("TOP", "MID1"), ("MID1", "MID2"), ("MID4", "BOTTOM"),
    )  # fmt: skip
    assert [(v.start_layer, v.end_layer) for v in document.vias].count((1, 2)) == 2  # upper layer first


def test_a_through_via_keeps_its_bytes() -> None:
    """A through via is written as before change c0085, and a document of through vias has one pair."""
    assert pcbrecords.via_record(1, 2, 3, 4) == pcbrecords.via_record(1, 2, 3, 4, start=1, end=32)
    body = pcbrecords.via_record(1, 2, 60, 30, start=2, end=39)[5:]
    assert (body[29], body[30], len(body)) == (2, 39, pcbrecords.VIA_SIZE)
    document, _ = read_back(bare_spec(copper_layers=LAYERS, vias=THREE[:1]))
    assert document.board.layer_pairs == (("TOP", "BOTTOM"),)
    assert b"LAYERPAIR1" not in document.board.raw


def test_a_via_may_end_on_a_plane() -> None:
    stack_ids = pcbrecords.copper_stack(LAYERS, ("In2.Cu",))
    from fenolite.backends.altium.libboard import StackSpec

    spec = bare_spec(
        copper_layers=LAYERS,
        stack=StackSpec.default(stack_ids, ("GND",)),
        nets=("GND",),
        vias=(via("p", 10, ("In1.Cu", "In2.Cu"), "buried", net_id="GND"),),
    )
    document, _ = read_back(spec)
    assert [(v.start_layer, v.end_layer) for v in document.vias] == [(2, 39)]
    assert document.board.layer_pairs[1] == ("MID1", "PLANE1")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"via_type": "micro", "layers": ("F.Cu", "In1.Cu")}, "via_bad: a micro via is not written"),
        ({"layers": ("F.Cu", "In9.Cu")}, "via_bad: the via spans F.Cu, In9.Cu"),
        ({"layers": ("F.Cu",)}, "via_bad: the via spans F.Cu, not two copper layers"),
    ],
)
def test_vias_the_writer_refuses(changes: dict[str, object], message: str) -> None:
    bad = dataclasses.replace(via("bad", 10, ("F.Cu", "B.Cu")), **changes)
    with pytest.raises(ValueError, match=message):
        write_pcbdoc(bare_spec(copper_layers=LAYERS, vias=(bad,)))
    with pytest.raises(ValueError, match="layer 33 is not a copper layer"):
        pcbrecords.via_record(0, 0, 60, 30, start=1, end=33)


# --- tenting flags (capability altium-pcb-writer, "Via tenting flags"; altium-import, "Via tenting of
# imported vias"; change c0112) ----------------------------------------------------------------------

P = ViaProtection
FLAG_CASES = ((False, False), (True, False), (False, True), (True, True))


def test_tenting_flags_of_the_four_cases() -> None:
    """Scenario "Flags of the four cases": bytes 0 to 4 of the subrecord, and nothing else moves."""
    plain = pcbrecords.via_record(393701, 393701, 236220, 118110, net=2)
    records = [
        pcbrecords.via_record(393701, 393701, 236220, 118110, net=2, tented_top=top, tented_bottom=bottom)
        for top, bottom in FLAG_CASES
    ]
    bodies = [record[5:] for record in records]
    assert [body[:5].hex(" ").upper() for body in bodies] == [
        "4A 0C 00 02 00", "4A 2C 00 02 00", "4A 4C 00 02 00", "4A 6C 00 02 00",
    ]  # fmt: skip
    assert records[0] == plain
    for record in records[1:]:
        assert len(record) == len(plain)
        assert [k for k, (a, b) in enumerate(zip(record, plain, strict=True)) if a != b] == [6]
    # the solder-mask expansions stay the values of "Via records": no recorded fact ties them to the flags
    assert {record[5 + 54 : 5 + 58] for record in records} == {plain[5 + 54 : 5 + 58]}
    assert {record[5 + 242 : 5 + 246] for record in records} == {plain[5 + 242 : 5 + 246]}
    assert (pcbrecords.VIA_TENTED_TOP, pcbrecords.VIA_TENTED_BOTTOM) == (0x20, 0x40)
    # the lock bit of c0108 and the two tenting bits are independent: 08, 28, 48, 68 for a locked via
    locked = [
        pcbrecords.via_record(1, 2, 60, 30, locked=True, tented_top=top, tented_bottom=bottom)[6]
        for top, bottom in FLAG_CASES
    ]
    assert locked == [0x08, 0x28, 0x48, 0x68]


def tented_vias() -> tuple[Via, ...]:
    return tuple(
        via(f"t{k}", 10 + 2 * k, ("F.Cu", "B.Cu"), protection=P(tenting_front=top, tenting_back=bottom))
        for k, (top, bottom) in enumerate(FLAG_CASES)
    )


def test_tenting_flags_read_back_and_become_the_protection() -> None:
    """Scenarios "Written flags read back" and "Flags become tenting": the four records, and the four
    imported vias with explicit tenting and nothing else."""
    document, design = read_back(bare_spec(copper_layers=LAYERS, vias=tented_vias()))
    found = sorted(document.vias, key=lambda v: v.x)
    assert [(v.tented_top, v.tented_bottom) for v in found] == list(FLAG_CASES)
    assert [f"{v.prefix.flags1:02X}" for v in found] == ["0C", "2C", "4C", "6C"]
    assert design.board is not None and design.board.via_protection is None
    imported = sorted(design.board.vias, key=lambda v: v.position.x)
    assert [v.protection for v in imported] == [
        P(tenting_front=top, tenting_back=bottom) for top, bottom in FLAG_CASES
    ]
    for read in imported:
        rest = dataclasses.replace(read.protection, tenting_front=None, tenting_back=None)
        assert rest == P()  # covering, plugging, capping and filling stay None


def test_tenting_of_a_via_without_protection_is_clear_and_imports_as_false() -> None:
    plain = (via("a", 10, ("F.Cu", "B.Cu")),)
    assert write_pcbdoc(bare_spec(copper_layers=LAYERS, vias=plain)) == write_pcbdoc(
        bare_spec(copper_layers=LAYERS, vias=(dataclasses.replace(plain[0], protection=P(False, False)),))
    )
    document, design = read_back(bare_spec(copper_layers=LAYERS, vias=plain))
    assert [(v.tented_top, v.tented_bottom) for v in document.vias] == [(False, False)]
    assert design.board is not None
    assert design.board.vias[0].protection == P(tenting_front=False, tenting_back=False)


def test_tenting_writes_nothing_for_the_four_other_features() -> None:
    """Covering, plugging, capping and filling write no byte and raise nothing, whatever their value."""
    base = via("a", 10, ("F.Cu", "B.Cu"), protection=P(tenting_front=True))
    wanted = write_pcbdoc(bare_spec(copper_layers=LAYERS, vias=(base,)))
    for value in (True, False):
        more = P(True, None, value, value, value, value, value, value)
        full = dataclasses.replace(base, protection=more)
        assert write_pcbdoc(bare_spec(copper_layers=LAYERS, vias=(full,))) == wanted


def test_tenting_resolved_from_the_via_and_the_board_default() -> None:
    """For each side: the via's own value, else the board default's, else a clear flag."""
    plain = via("a", 10, ("F.Cu", "B.Cu"))
    assert via_tenting(plain, None) == (False, False)
    assert via_tenting(plain, P(tenting_front=True)) == (True, False)
    own = dataclasses.replace(plain, protection=P(tenting_front=False, filling=True))
    assert via_tenting(own, P(True, True)) == (False, True)
    stated = dataclasses.replace(plain, protection=P(True, False))
    assert via_tenting(stated, P(False, True)) == (True, False)
    assert unstated_tenting(plain, None) and unstated_tenting(plain, P(tenting_front=True))
    assert not unstated_tenting(plain, P(True, False)) and not unstated_tenting(stated, None)
    assert unwritten_features(own, None) == ("filling",)
    assert unwritten_features(plain, P(capping=True, plugging_back=True)) == ("plugging", "capping")
    assert unwritten_features(dataclasses.replace(plain, protection=P(capping=False)), P(capping=True)) == ()
    # the document takes the default from the spec: the vias themselves stay as the model holds them
    second = dataclasses.replace(own, id="via_b", position=at(12, 10))
    spec = bare_spec(copper_layers=LAYERS, vias=(plain, second), via_protection=P(True, True))
    document, _ = read_back(spec)
    found = sorted(document.vias, key=lambda v: v.x)
    assert [(v.tented_top, v.tented_bottom) for v in found] == [(True, True), (False, True)]


def test_tenting_of_an_imported_board_written_for_kicad() -> None:
    """Scenario "An imported board written for KiCad": every via holds its own tenting child, so none
    follows KiCad's board default."""
    _, design = read_back(bare_spec(copper_layers=("F.Cu", "B.Cu"), vias=tented_vias()))
    assert design.board is not None
    vias = tuple(
        dataclasses.replace(v, ext={}, provenance=None, layers=("F.Cu", "B.Cu"), net_id=None)
        for v in sorted(design.board.vias, key=lambda v: v.position.x)
    )
    board = dataclasses.replace(
        design.board, ext={}, provenance=None, layers=created_layers(2), vias=vias, footprints=(), tracks=(),
        arcs=(), zones=(), keepouts=(), texts=(), graphics=(), holes=(), outline=None, stackup=None,
    )  # fmt: skip
    created = dataclasses.replace(design, board=board)
    written = parse(write_board(created, target=10).text)
    found = [
        [dumps(c, style="compact") for c in node.nodes() if c.name == "tenting"]
        for node in written.nodes("via")
    ]
    assert found == [
        ["(tenting (front no) (back no))"],
        ["(tenting (front yes) (back no))"],
        ["(tenting (front no) (back yes))"],
        ["(tenting (front yes) (back yes))"],
    ]
