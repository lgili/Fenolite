# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Entirely authored bus contact controls, derived only from Fenolite's own bus fixture.

Build the unchanged fixture before applying a controlled native perturbation: the resolver under test
must not prevent an independent native export. No product build/refusal path is waived or changed.
"""

from __future__ import annotations

from dataclasses import replace
from functools import cache
from typing import Literal

import _drawn

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.drawn import DrawnBusAlias, DrawnJunction, DrawnLabelKind, DrawnSchematic
from fenolite.model.schematic import BusAlias, BusWire, Junction, NetLabel, SchematicSheet, SheetPin, SheetRef

Form = Literal["vector", "group", "alias", "overbar"]
Contact = Literal["entry", "junction", "endpoint"]
FORMS: tuple[Form, ...] = ("vector", "group", "alias", "overbar")
CONTACTS: tuple[Contact, ...] = ("entry", "junction")


def repeated_bus_files(target: int, *, connected: bool, labels: int):
    """Original repeated-sheet control: equal bus ports on isolated parent bus islands."""
    output = _drawn.build("repeat", target)
    assert output.files and not any(issue.severity == "error" for issue in output.issues)
    files = dict(output.files)
    name = _drawn.root_name(output)
    root = parse(files[name].decode())
    refs = root.nodes("sheet")
    assert len(refs) == 2
    changed = {}
    extras = []
    for index, ref in enumerate(refs):
        y = "55.88" if index == 0 else "81.28"
        pin = parse(f'(pin "{{FB}}" bidirectional (at 50.8 {y} 180) (effects (font (size 1.27 1.27))))')
        changed[id(ref)] = ref.with_children((*ref.children, pin))
        extras.append(parse(f"(bus (pts (xy 38.1 {y}) (xy 50.8 {y})) (stroke (width 0) (type default)))"))
        if index < labels:
            extras.append(
                parse(
                    f'(label "{{FB}}" (at 40.64 {y} 0) '
                    "(effects (font (size 1.27 1.27)) (justify left bottom)))"
                )
            )
    if connected:
        extras.append(parse("(bus (pts (xy 38.1 55.88) (xy 38.1 81.28)) (stroke (width 0) (type default)))"))
    files[name] = dumps(
        root.with_children((*[changed.get(id(item), item) for item in root.children], *extras))
    ).encode()
    child_name = next(key for key in files if key.endswith(".kicad_sch") and key != name)
    child = parse(files[child_name].decode())
    fragments = (
        "(wire (pts (xy 88.9 80.01) (xy 101.6 80.01)) (stroke (width 0) (type default)))",
        "(bus (pts (xy 86.36 77.47) (xy 86.36 90.17)) (stroke (width 0) (type default)))",
        "(bus_entry (at 86.36 77.47) (size 2.54 2.54) (stroke (width 0) (type default)))",
        '(hierarchical_label "{FB}" (shape bidirectional) (at 86.36 90.17 90) '
        "(effects (font (size 1.27 1.27)) (justify left)))",
    )
    files[child_name] = dumps(
        child.with_children((*child.children, *(parse(text) for text in fragments)))
    ).encode()
    paths = {
        component.properties["fenolite.path"]: component.ref for component in output.design.circuit.components
    }
    return output, name, files, paths


def value(form: Form, contact: Contact) -> DrawnSchematic:
    original = _drawn.drawn("bus")
    bus_name = {
        "vector": "D[0..3]",
        "group": "CHANNEL{D[0..3]}",
        "alias": "{CHANNEL}",
        "overbar": "CHANNEL{~{READY} D[1..3]}",
    }[form]

    def name(text: str) -> str:
        if text == "D[0..3]":
            return bus_name
        if form == "overbar" and text == "D0":
            return "CHANNEL.~{READY}"
        return f"CHANNEL.{text}" if form in ("group", "overbar") else text

    sheets = []
    for sheet in original.sheets:
        labels = tuple(replace(label, text=name(label.text)) for label in sheet.labels)
        refs = tuple(
            replace(ref, pins=tuple(replace(pin, name=name(pin.name)) for pin in ref.pins))
            for ref in sheet.sheet_refs
        )
        aliases = (DrawnBusAlias("CHANNEL", ("D[0..3]",)),) if form == "alias" else ()
        junctions = sheet.junctions
        if sheet.key == "child":
            bus_label = next(label for label in labels if label.kind == "hierarchical")
            if contact == "entry":
                anchor = sheet.bus_entries[0].at  # this authored entry starts on the bus side
                labels = tuple(replace(label, at=anchor) if label is bus_label else label for label in labels)
            elif contact == "junction":
                junctions = (*junctions, DrawnJunction(bus_label.at))
        sheets.append(
            replace(sheet, labels=labels, sheet_refs=refs, bus_aliases=aliases, junctions=junctions)
        )
    return replace(original, sheets=tuple(sheets))


@cache
def base(target: int):
    output = _drawn.build("bus", target)
    assert output.files and not any(issue.severity == "error" for issue in output.issues), output.issues
    return output


def native_files(form: Form, contact: Contact, target: int) -> tuple[str, dict[str, bytes], dict[str, str]]:
    return native_drawing(value(form, contact), target)


def renamed(
    form: Literal["vector", "group", "vector-group"], *, reverse: bool, connected: bool
) -> DrawnSchematic:
    """Distinct qualified bus names, optionally disconnected; source labels stay literal."""
    drawing = value("vector" if form == "vector" else "group", "endpoint")
    root, child = drawing.sheets
    first, last = (3, 0) if reverse else (0, 3)
    old = "D[0..3]" if form == "vector" else "CHANNEL{D[0..3]}"
    new = f"Q[{first}..{last}]" if form == "vector" else f"OTHER{{D[{first}..{last}]}}"
    if form == "group":
        root = replace(
            root,
            labels=tuple(
                replace(label, text="CHANNEL{D0 D1 D2 D3}") if label.text == old else label
                for label in root.labels
            ),
        )
        old = "CHANNEL{D0 D1 D2 D3}"
        order = "D3 D2 D1 D0" if reverse else "D0 D1 D2 D3"
        new = f"OTHER{{{order}}}"
        child = replace(
            child,
            labels=tuple(
                replace(label, text=old) if label.kind == "hierarchical" else label for label in child.labels
            ),
        )
    labels = tuple(
        replace(
            label,
            text=new
            if label.text == old
            else label.text.replace("CHANNEL.", "OTHER.", 1)
            if form != "vector"
            else "Q" + label.text[1:],
        )
        for label in child.labels
    )
    child = replace(child, labels=labels)
    refs = tuple(
        replace(ref, pins=tuple(replace(pin, name=new) for pin in ref.pins)) for ref in root.sheet_refs
    )
    root = replace(root, sheet_refs=refs)
    if not connected:
        start, end = root.buses[0][:2]
        anchor = Point((start.x + end.x) // 2, (start.y + end.y) // 2)
        port = root.sheet_refs[0].pins[0].at
        root = replace(
            root,
            buses=((start, end), (port, Point(port.x + 12_700_000, port.y))),
            labels=tuple(replace(label, at=anchor) if label.text == old else label for label in root.labels),
        )
    return replace(drawing, sheets=(root, child))


def scalar_labels(kind: DrawnLabelKind, *, equal: bool) -> DrawnSchematic:
    """Two child labels share a text across scopes; the root's same text remains on its own sheet."""
    drawing = value("vector", "endpoint")
    sheets = []
    for sheet in drawing.sheets:
        labels = tuple(
            replace(
                label,
                kind=kind,
                text="D0" if equal else "OTHER",
                shape="" if kind == "local" else "bidirectional",
            )  # fmt: skip
            if sheet.key == "child" and label.text == "D1"
            else label
            for label in sheet.labels
            if label.text != "D[0..3]"
        )
        refs = tuple(replace(ref, pins=()) for ref in sheet.sheet_refs)
        sheets.append(replace(sheet, labels=labels, sheet_refs=refs, buses=(), bus_entries=()))
    return replace(drawing, sheets=tuple(sheets))


def offset_vector(*, reverse: bool) -> DrawnSchematic:
    """Overlapping indices distinguish numeric identity from either written or sorted position."""
    drawing = renamed("vector", reverse=False, connected=True)
    root, child = drawing.sheets
    name = "Q[5..2]" if reverse else "Q[2..5]"
    labels = tuple(
        replace(label, text=name if label.kind == "hierarchical" else f"Q{int(label.text[1:]) + 2}")
        for label in child.labels
    )
    refs = tuple(
        replace(ref, pins=tuple(replace(pin, name=name) for pin in ref.pins)) for ref in root.sheet_refs
    )
    return replace(drawing, sheets=(replace(root, sheet_refs=refs), replace(child, labels=labels)))


def native_drawing(changed: DrawnSchematic, target: int) -> tuple[str, dict[str, bytes], dict[str, str]]:
    """Emit exactly the authored labels/aliases/contacts while retaining the authored embedded symbols."""
    output = base(target)
    root, children = _drawn.sheets(output)
    root_file = _drawn.root_name(output)
    files = dict(output.files)
    for file, native in ((root_file, root), *children.items()):
        key = "root" if file == root_file else "child"
        after = changed.sheet(key)
        assert after is not None
        labels = tuple(
            NetLabel(
                id=derived_id("lbl", "authored-contact", f"{file}:{i}"),
                kind=label.kind,
                name=label.text,
                position=label.at,
                rotation=label.rotation,
                shape=label.shape,
            )
            for i, label in enumerate(after.labels)
        )
        refs = tuple(
            SheetRef(
                id=ref.id,
                native_ids=ref.native_ids,
                name=ref.name,
                file=ref.file,
                position=ref.position,
                size=ref.size,
                uses=ref.uses,
                pins=tuple(
                    SheetPin(
                        id=derived_id("shr", "authored-contact", f"{file}:{i}:{j}"),
                        name=pin.name,
                        shape=pin.shape,
                        position=pin.at,
                        rotation=pin.rotation,
                    )
                    for j, pin in enumerate(after.sheet_refs[i].pins)
                ),
            )
            for i, ref in enumerate(native.sheets)
        )
        aliases = tuple(
            BusAlias(
                id=derived_id("bus", "authored-contact", f"{file}:{alias.name}"),
                name=alias.name,
                members=alias.members,
            )
            for alias in after.bus_aliases
        )
        junctions = tuple(
            Junction(
                id=derived_id("wir", "authored-contact", f"{file}:{i}"),
                position=junction.at,
                diameter=junction.diameter,
            )
            for i, junction in enumerate(after.junctions)
        )
        breaks = tuple(j.at for j in after.junctions) + tuple(
            point for entry in after.bus_entries for point in (entry.at, entry.end)
        )
        buses = tuple(
            BusWire(id=derived_id("bus", "authored-contact", f"{file}:bus:{i}:{j}"), start=a, end=b)
            for i, (start, end) in enumerate(after.bus_segments())
            for j, (a, b) in enumerate(kdrawn.split_at(start, end, breaks))
        )
        authored = SchematicSheet(
            id=derived_id("sch", "authored-contact", file),
            name="authored-contact",
            labels=labels,
            sheets=refs,
            bus_aliases=aliases,
            junctions=junctions,
            buses=buses,
        )
        fragments = parse(sch.write_schematic(authored, target=target).text)
        replaced_heads = {
            "label",
            "global_label",
            "hierarchical_label",
            "sheet",
            "junction",
            "bus_alias",
            "bus",
        }
        root_node = parse(files[file].decode("utf-8"))
        extras = tuple(node for node in fragments.children if node.head.value in replaced_heads)
        controlled = root_node.with_children(
            (
                *(node for node in root_node.children if node.head.value not in replaced_heads),
                *extras,
            )
        )
        files[file] = dumps(controlled).encode("utf-8")

    refs = {
        component.properties["fenolite.path"]: component.ref for component in output.design.circuit.components
    }
    return root_file, files, refs
