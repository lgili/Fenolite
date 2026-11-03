# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native root ports retain same-sheet identities and strict child mismatch guards (c0350)."""

from dataclasses import replace

import _bus_scope
import _root_hlabels
import pytest

from fenolite.backends.kicad import drawn, sch
from fenolite.lens.drawn import write_drawn
from fenolite.model.drawn_connect import resolve


def extracted(*, child_mismatch: bool = False, equal: bool = True):
    value = _root_hlabels.drawing(child_mismatch=child_mismatch, equal=equal)
    file, files, refs = _bus_scope.native_drawing(value, 10)
    root = sch.read_schematic(files[file].decode(), file=file)
    children = {
        p: sch.read_schematic(d.decode(), file=p)
        for p, d in files.items()
        if p.endswith(".kicad_sch") and p != file
    }
    result = drawn.extract_with_pins(
        root, children, components={r: p for p, r in refs.items()}, root_file=file
    )
    return result


@pytest.mark.parametrize("equal", [False, True])
def test_root_port_adapter_retains_every_pin_and_same_sheet_isolation(equal: bool) -> None:
    found = extracted(equal=equal)
    before = write_drawn(found.drawn)
    own = drawn._resolve_extracted(found)
    generic = resolve(found.drawn, found.pins)
    assert len(own.pins) == 40
    group = own.net_of(("child/R10", "1"))
    assert group is not None and (("child/R11", "1") in group.members) is equal
    assert ("U1", "17") not in group.members
    assert not [i for i in own.issues if i.severity == "error"]
    assert any(i.code == "drawn.sheet-pin-unmatched" and "root sheet" in i.message for i in generic.issues)
    assert replace(own, issues=generic.issues) == generic
    assert write_drawn(found.drawn) == before


def test_real_child_mismatch_is_still_an_error() -> None:
    found = extracted(child_mismatch=True)
    errors = [i for i in drawn._resolve_extracted(found).issues if i.severity == "error"]
    assert len(errors) == 1
    assert errors[0].code == "drawn.sheet-pin-unmatched"
    assert "child" in errors[0].message and "root sheet" not in errors[0].message
