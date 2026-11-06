# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The package checks ``IsSOIC``, ``IsLCC`` and ``IsBGA`` on authored footprints (change c0462, design D3;
capability altium-project-reader, scenario "Package checks on authored footprints"). Coordinates are file
units; every footprint is authored for this test."""

from __future__ import annotations

import pytest

from fenolite.backends.altium.read import packages
from fenolite.backends.altium.read.scope import (
    NOTHING,
    Refusal,
    ScopeComponent,
    ScopeDocument,
    ScopePad,
    parse_scope,
)
from fenolite.model.rules import Selector

PITCH = 500_000  # 50 mil


def _soic() -> ScopeComponent:
    pads = [ScopePad(x * PITCH, y * 2_000_000, True) for y in (0, 1) for x in range(4)]
    return ScopeComponent("U1", "SOIC-8", pads=tuple(pads))


def _lcc() -> ScopeComponent:
    side = [PITCH * (k + 1) for k in range(4)]
    edge = PITCH * 5
    pads = [ScopePad(x, 0, True) for x in side] + [ScopePad(x, edge, True) for x in side]
    pads += [ScopePad(0, y, True) for y in side] + [ScopePad(edge, y, True) for y in side]
    return ScopeComponent("U2", "LCC-16", pads=tuple(pads))


def _bga() -> ScopeComponent:
    pads = [ScopePad(x * PITCH, y * PITCH, True) for y in range(10) for x in range(10)]
    return ScopeComponent("U3", "BGA-100", pads=tuple(pads))


def _chip() -> ScopeComponent:
    return ScopeComponent("C1", "0603", pads=(ScopePad(0, 0, True), ScopePad(PITCH, 0, True)))


PARTS = (_soic(), _lcc(), _bga(), _chip())


@pytest.mark.parametrize(("name", "designator"), [("IsSOIC", "U1"), ("IsLCC", "U2"), ("IsBGA", "U3")])
def test_each_check_selects_its_own_footprint(name: str, designator: str) -> None:
    """Scenario "Package checks on authored footprints"."""
    assert [part.designator for part in PARTS if packages.PACKAGE_CHECKS[name](part)] == [designator]
    document = ScopeDocument(components=PARTS, parents=frozenset({"component"}))
    assert parse_scope(name, document=document) == Selector("ref", designator)


def test_a_soic_turned_a_quarter_turn() -> None:
    turned = ScopeComponent(
        "U4", "SOIC-8", rotation=90.0, pads=tuple(ScopePad(p.y, p.x, True) for p in _soic().pads)
    )
    assert packages.is_soic(turned) and not packages.is_lcc(turned) and not packages.is_bga(turned)


def test_a_through_hole_pad_is_no_package() -> None:
    pads = (*_soic().pads[:-1], ScopePad(3 * PITCH, 2_000_000, False))
    mixed = ScopeComponent("U5", "SOIC-8", pads=pads)
    assert not any(check(mixed) for check in packages.PACKAGE_CHECKS.values())


def test_a_sparse_grid_is_a_bga() -> None:
    """At least half of rows times columns: a 10 x 10 grid with its centre 4 x 4 left out."""
    pads = tuple(p for p in _bga().pads if not (3 <= p.x // PITCH <= 6 and 3 <= p.y // PITCH <= 6))
    assert len(pads) == 84 and packages.is_bga(ScopeComponent("U6", "BGA", pads=pads))


def test_no_component_selected() -> None:
    document = ScopeDocument(components=(_chip(),), parents=frozenset({"component"}))
    assert parse_scope("IsBGA", document=document) == NOTHING


def test_a_turn_off_the_axes_is_not_decided() -> None:
    turned = ScopeComponent("U7", "SOIC-8", rotation=45.0, pads=_soic().pads)
    with pytest.raises(packages.PackageUndecided):
        packages.is_soic(turned)
    found = parse_scope(
        "IsSOIC", document=ScopeDocument(components=(turned,), parents=frozenset({"component"}))
    )
    assert isinstance(found, Refusal) and found.reason == "package-check"


def test_dsl_names_the_function_of_an_expanded_rule() -> None:
    """Design D2: ``fenolite.dsl`` prints a rule expanded from the document with a comment naming the
    function."""
    from fenolite.backends.altium.adapter.ids import bag
    from fenolite.importer.emit.design import _expanded_note  # pyright: ignore[reportPrivateUsage]
    from fenolite.model.rules import Rule

    def rule(scope1: str, scope2: str = "All") -> Rule:
        return Rule(
            id="rul_x", name="r", kind="clearance", selector_a=Selector("ref", "U1"), min=1,
            ext=bag((("rule_kind", "Clearance"), ("scope1", scope1), ("scope2", scope2))),
        )  # fmt: skip

    assert _expanded_note(rule("IsBGA", "HasFootprint('SOIC*') And InNet('A')")) == [
        "expanded from Altium HasFootprint, IsBGA over the board read: a fixed list"
    ]
    assert _expanded_note(rule("InNet('IsBGA')")) == []
    assert _expanded_note(rule("AsMM(HoleDiameter) > 1")) == [
        "expanded from Altium HoleDiameter over the board read: a fixed list"
    ]
    assert _expanded_note(rule("InNet('A') And IsTrack")) == []
    assert (
        _expanded_note(Rule(id="rul_y", name="r", kind="clearance", selector_a=Selector("all"), min=1)) == []
    )
