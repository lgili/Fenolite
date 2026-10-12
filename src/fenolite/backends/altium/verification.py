# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project-wide electrical and identity readback for authored composition output."""

# evidence: see project

from collections.abc import Mapping

from fenolite.backends.altium.adapter import SheetInput, netlist
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.read import sch
from fenolite.core.errors import Issue
from fenolite.schematic.composition import fail


def signature(files: Mapping[str, bytes]) -> tuple[object, ...]:
    sheets: list[SheetInput] = []
    identities: list[tuple[object, ...]] = []
    footprints: list[tuple[object, ...]] = []
    for name, data in sorted(files.items()):
        document = sch.read_schematic(data, file=name)
        if (
            document.sheet is None
            or document.of_type(sch.UnknownRecord)
            or any(i.severity in ("error", "warning") for i in document.issues)
        ):
            raise fail(
                "connectivity-changed",
                "native readback could not verify sheet",
                name,
                "inspect native reader findings before generating",
            )
        for component in document.components():
            children = document.children_of(component)
            identities.append(
                (
                    name,
                    component.unique_id,
                    component.current_part,
                    component.lib_reference,
                    component.design_item_id,
                    component.source_library,
                    tuple(
                        sorted(
                            (p.designator, p.name, p.electrical, p.owner_part)
                            for p in children
                            if isinstance(p, sch.Pin)
                        )
                    ),
                    tuple(
                        sorted(
                            (p.record_id, p.name, p.text)
                            for p in children
                            if isinstance(p, (sch.Parameter, sch.Designator))
                        )
                    ),
                )
            )
        footprints.extend(
            (name, g.unique_ids, g.lib_footprint_ref, g.pin_pads) for g in part_groups(document)
        )
        sheets.append(SheetInput(name, "", document))
    issues: list[Issue] = []
    nets = netlist(sheets, issues=issues)
    if any(i.severity in ("error", "warning") for i in issues):
        raise fail(
            "connectivity-changed",
            "native netlist has unresolved findings",
            "project",
            "inspect native connectivity findings",
        )
    return (
        tuple(sorted(identities)),
        tuple(sorted(footprints)),
        tuple(sorted((n.name, n.aliases, n.pins) for n in nets.nets)),
        tuple(sorted(nets.no_connects)),
        tuple(sorted((b.name, b.label, b.members) for b in nets.buses)),
        tuple(sorted((h.type, h.members) for h in nets.harnesses)),
    )


def verify(before: Mapping[str, bytes], after: Mapping[str, bytes]) -> None:
    if set(before) != set(after) or signature(before) != signature(after):
        raise fail(
            "connectivity-changed",
            "composition changed circuit or component identities",
            "project",
            "retain the previous files and report this composition failure",
        )
