# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native scope aliases preserve literal source, complete pin coverage and strict diagnostics (c0320)."""

from __future__ import annotations

from dataclasses import replace

import _bus_scope
import pytest

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.lens.drawn import write_drawn
from fenolite.model.drawn import DrawnLabelKind, DrawnSchematic


def extracted(drawing: DrawnSchematic) -> kdrawn.Extracted:
    file, files, refs = _bus_scope.native_drawing(drawing, 9)
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        path: sch.read_schematic(data.decode(), file=path)
        for path, data in files.items()
        if path.endswith(".kicad_sch") and path != file
    }
    return kdrawn.extract_with_pins(
        root, children, components={ref: path for path, ref in refs.items()}, root_file=file
    )


@pytest.mark.parametrize("form", _bus_scope.FORMS)
def test_native_bus_policy_keeps_all_source_fields(form: _bus_scope.Form) -> None:
    found = extracted(_bus_scope.value(form, "entry"))
    raw, pins = write_drawn(found.drawn), dict(found.pins)
    first = kdrawn._resolve_extracted(found)
    assert kdrawn._resolve_extracted(found) == first
    assert len(first.pins) == 40
    assert write_drawn(found.drawn) == raw  # labels, ports, geometry, fields and opaque source
    assert found.pins == pins


@pytest.mark.parametrize("kind", ["local", "hierarchical", "global"])
@pytest.mark.parametrize("equal", [True, False])
def test_native_scalar_aliases_preserve_scope_and_unmatched_ports(kind: DrawnLabelKind, equal: bool) -> None:
    found = extracted(_bus_scope.scalar_labels(kind, equal=equal))
    raw = write_drawn(found.drawn)
    netlist = kdrawn._resolve_extracted(found)
    child = netlist.net_of(("child/R10", "1"))
    assert child is not None and (("child/R11", "1") in child.members) is equal
    assert ("U1", "17") not in child.members
    errors = [issue for issue in netlist.issues if issue.severity == "error"]
    assert [issue.code for issue in errors] == (
        ["drawn.sheet-pin-unmatched"] if kind == "hierarchical" else []
    )
    assert write_drawn(found.drawn) == raw


@pytest.mark.parametrize("form", _bus_scope.FORMS)
def test_native_bus_policy_does_not_guess_an_unlabelled_member(form: _bus_scope.Form) -> None:
    drawing = _bus_scope.value(form, "entry")
    root, child = drawing.sheets
    missing = "CHANNEL.D2" if form in ("group", "overbar") else "D2"
    child = replace(child, labels=tuple(label for label in child.labels if label.text != missing))
    found = extracted(replace(drawing, sheets=(root, child)))
    netlist = kdrawn._resolve_extracted(found)
    assert ("child/R12", "1") in netlist.open
    assert any(
        issue.code == "drawn.bus-member-unknown" and missing in issue.message for issue in netlist.issues
    )
