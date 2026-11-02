# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored bus contact/identity controls against the actual native CLI, with no source CAD (c0320)."""

from __future__ import annotations

from typing import Literal

import _bus_scope
import _erc
import _probes
import pytest

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.model.drawn import DrawnLabelKind, DrawnSchematic

pytestmark = pytest.mark.needs_kicad


def partitions(drawing: DrawnSchematic):
    target = _probes.major()
    file, files, refs = _bus_scope.native_drawing(drawing, target)
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        path: sch.read_schematic(data.decode(), file=path)
        for path, data in files.items()
        if path.endswith(".kicad_sch") and path != file
    }
    _raw, own, _issues = kdrawn.resolve_sheets(
        root,
        children,
        circuit=_bus_scope.base(target).design.circuit,
        name="authored-contact",
        root_file=file,
    )
    native = _erc.netlist(_probes.runner(), file, files)
    expected = {(refs[path], number) for path, number in own.pins}
    assert {pin for group in native.values() for pin in group} == expected
    ours = {frozenset((refs[path], number) for path, number in net.members) for net in own.nets}
    ours |= {frozenset({(refs[path], number)}) for path, number in own.open}
    theirs = {frozenset(group) for group in native.values()}
    return ours, theirs, native, expected


@pytest.mark.parametrize("form", _bus_scope.FORMS)
@pytest.mark.parametrize("contact", _bus_scope.CONTACTS)
def test_native_bus_contacts_preserve_the_complete_partition(
    form: _bus_scope.Form, contact: _bus_scope.Contact
) -> None:
    ours, theirs, _native, pins = partitions(_bus_scope.value(form, contact))
    print(
        f"{_probes.runner().version()} {form}/{contact}: {len(pins)} pins; "
        f"own={len(ours)}, native={len(theirs)}, differing={len(ours ^ theirs)}"
    )
    assert ours == theirs


@pytest.mark.parametrize("form", ["vector", "group", "vector-group"])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("connected", [True, False])
def test_native_bus_member_correspondence_is_scoped(
    form: Literal["vector", "group", "vector-group"], reverse: bool, connected: bool
) -> None:
    drawing = _bus_scope.renamed(form, reverse=reverse, connected=connected)
    ours, theirs, native, pins = partitions(drawing)
    first = next(sorted(group) for group in native.values() if ("U1", "17") in group)
    print(
        f"{_probes.runner().version()} {form} reverse={reverse} connected={connected}: "
        f"pins={len(pins)}, own={len(ours)}, native={len(theirs)}, first={first}"
    )
    assert ours == theirs


@pytest.mark.parametrize("kind", ["local", "hierarchical", "global"])
@pytest.mark.parametrize("equal", [True, False])
def test_native_scalar_label_scopes_remain_on_their_sheet(kind: DrawnLabelKind, equal: bool) -> None:
    ours, theirs, native, pins = partitions(_bus_scope.scalar_labels(kind, equal=equal))
    first = next(group for group in native.values() if ("R10", "1") in group)
    print(
        f"{_probes.runner().version()} scalar {kind} equal={equal}: "
        f"pins={len(pins)}, own={len(ours)}, native={len(theirs)}, child={sorted(first)}"
    )
    assert (("R11", "1") in first) is equal
    assert ("U1", "17") not in first  # the root's local D0 is a different sheet instance
    assert ours == theirs


@pytest.mark.parametrize("reverse", [False, True])
def test_native_vector_identity_uses_ascending_index_positions(reverse: bool) -> None:
    ours, theirs, native, pins = partitions(_bus_scope.offset_vector(reverse=reverse))
    second = next(group for group in native.values() if ("U1", "19") in group)
    print(
        f"{_probes.runner().version()} offset vector reverse={reverse}: "
        f"pins={len(pins)}, own={len(ours)}, native={len(theirs)}, index2={sorted(second)}"
    )
    assert second == {("U1", "19"), ("R12", "1")}
    assert ours == theirs
