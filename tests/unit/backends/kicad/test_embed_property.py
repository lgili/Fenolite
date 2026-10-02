# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path property on placed footprints (capability kicad-file-backend, "Path property on placed
footprints"; change c0011)."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from fenolite.backends.kicad.embed import PATH_PROPERTY, place_footprint, with_property
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse, walk
from fenolite.backends.kicad.versions import FileKind, check_emittable
from fenolite.core.coords import Point
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

V9 = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs" / "Mini_v9.pretty"


def defn(name: str = "Mini_R_0603"):  # noqa: ANN201
    return read_footprint(V9 / f"{name}.kicad_mod", library="Mini")


def component(ref: str, n: int = 1) -> Component:
    return Component(id=f"cmp_00000000-0000-4000-8000-{n:012d}", ref=ref, value="1k")


def props(node: Node) -> list[Node]:
    return [c for c in node.nodes("property")]


def test_property_appended_last() -> None:
    d = defn()
    extended = with_property(d, name=PATH_PROPERTY, value="power/R1")
    assert extended.properties[PATH_PROPERTY] == "power/R1" and PATH_PROPERTY not in d.properties
    c = component("R1")
    c = dataclasses.replace(
        c, properties={k: v for k, v in extended.properties.items() if k not in ("Reference", "Value")}
    )
    placed = place_footprint(extended, component=c, at=Point(0, 0), key="power/R1")
    base = Design.new("p", seed=0)
    assert base.board is not None
    design = dataclasses.replace(
        base,
        circuit=Circuit(components=(c,)),
        board=dataclasses.replace(base.board, layers=created_layers(2), footprints=(placed,)),
    )
    text = write_board(design, target=10).text
    (fp,) = parse(text).nodes("footprint")
    last = props(fp)[-1]
    assert last.atoms()[0].value == PATH_PROPERTY and last.atoms()[1].value == "power/R1"
    assert last.find("layer").atoms()[0].value == "F.Fab" and last.find("hide") is not None  # type: ignore[union-attr]
    back = read_board(text)
    assert back.circuit.components[0].properties[PATH_PROPERTY] == "power/R1"


def uuids(instance_text: str) -> dict[str, str]:
    root = parse(instance_text)
    return {loc: n.find("uuid").atoms()[0].value for loc, n in walk(root) if n.find("uuid") is not None}  # type: ignore[union-attr]


def test_no_other_uuid_moves() -> None:
    d, c = defn(), component("R1")
    plain = place_footprint(d, component=c, at=Point(0, 0), key="R1")
    extended = place_footprint(
        with_property(d, name=PATH_PROPERTY, value="R1"), component=c, at=Point(0, 0), key="R1"
    )
    assert {p.native_ids["kicad"] for p in plain.pads} == {p.native_ids["kicad"] for p in extended.pads}
    assert plain.native_ids == extended.native_ids

    def fragment_uuids(instance: object) -> set[str]:
        from fenolite.backends.kicad import slots as slotlib
        from fenolite.model.base import Opaque

        bag = instance.ext["kicad"]  # type: ignore[attr-defined]
        found = set()
        for slot in slotlib.from_ext(bag):
            if isinstance(slot, Opaque) and PATH_PROPERTY not in slot.fragment:
                found |= set(re.findall(r'\(uuid "([^"]+)"\)', slot.fragment))
        return found

    assert fragment_uuids(plain) == fragment_uuids(extended) and fragment_uuids(plain)


def test_bottom_side() -> None:
    placed = place_footprint(
        with_property(defn(), name=PATH_PROPERTY, value="D"),
        component=component("R1"),
        at=Point(0, 0),
        key="R1",
        side="bottom",
    )
    from fenolite.backends.kicad import slots as slotlib
    from fenolite.model.base import Opaque

    fragments = [s.fragment for s in slotlib.from_ext(placed.ext["kicad"]) if isinstance(s, Opaque)]
    (frag,) = [f for f in fragments if f.startswith(f'(property "{PATH_PROPERTY}"')]
    assert '(layer "B.Fab")' in frag and "(hide yes)" in frag


def test_emit_check_is_clean_on_both_targets() -> None:
    parts = [
        ("Mini_R_0603", "R1", "top"),
        ("Mini_LED_THT_3mm", "D1", "bottom"),
        ("Mini_QFP-32_7x7mm_P0.8mm", "U1", "top"),
    ]
    instances, comps = [], []
    for n, (name, ref, side) in enumerate(parts, start=1):
        extended = with_property(defn(name), name=PATH_PROPERTY, value=ref)
        c = component(ref, n)
        placed = place_footprint(
            extended, component=c, at=Point(20_000_000 * n, 20_000_000), key=ref, side=side
        )  # type: ignore[arg-type]
        comps.append(
            dataclasses.replace(
                c,
                properties={k: v for k, v in extended.properties.items() if k not in ("Reference", "Value")},
            )
        )
        instances.append(placed)
    base = Design.new("p", seed=0)
    assert base.board is not None
    design = dataclasses.replace(
        base,
        circuit=Circuit(components=tuple(comps)),
        board=dataclasses.replace(base.board, layers=created_layers(2), footprints=tuple(instances)),
    )
    for target in (9, 10):
        text = write_board(design, target=target).text
        assert check_emittable(parse(text), FileKind.BOARD, target) == ()
