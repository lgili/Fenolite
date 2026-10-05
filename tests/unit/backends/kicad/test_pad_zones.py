# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pad zone connection requests on a built copy and on a kept footprint (capabilities design-dsl, "Pad
zone connections in a build", and layout-lens, "Pad zone connections across rebuilds"; change c0068).
Hermetic."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import pytest
from _placed import Part, design_of

from fenolite.backends.kicad import zones
from fenolite.backends.kicad.zones import (
    PAD_OVERRIDE_HINT,
    PAD_ZONE_ISSUE_CODES,
    apply_pad_connections,
    keep_pad_connections,
)
from fenolite.core.errors import Issue
from fenolite.model.board import FootprintInstance


@dataclass(frozen=True)
class Request:
    number: str
    index: int | None
    connection: str
    locked: bool = False


def footprint(name: str = "Mini_R_0603") -> FootprintInstance:
    design = design_of(Part("X1", name, 10, 10))
    assert design.board is not None
    return design.board.footprints[0]


def connections(instance: FootprintInstance) -> list[tuple[str, str | None]]:
    return [(pad.number, pad.zone_connection) for pad in instance.pads]


def with_pad(instance: FootprintInstance, position: int, connection: str | None) -> FootprintInstance:
    pads = list(instance.pads)
    pads[position] = dataclasses.replace(pads[position], zone_connection=connection)  # type: ignore[arg-type]
    return dataclasses.replace(instance, pads=tuple(pads))


def note(issues: list[Issue]) -> list[Issue]:
    for issue in issues:
        assert issue.severity == PAD_ZONE_ISSUE_CODES[issue.code]
    return issues


# --- a built copy --------------------------------------------------------------------------------


def test_apply_sets_every_pad_with_the_number() -> None:
    base = footprint()
    issues: list[Issue] = []
    found = apply_pad_connections(base, [Request("1", None, "solid")], where="R1", issues=issues)
    assert connections(found) == [("1", "solid"), ("2", None)] and issues == []
    assert connections(base) == [("1", None), ("2", None)]  # pure
    # nothing but the named pad changed
    assert dataclasses.replace(found, pads=base.pads) == base
    assert dataclasses.replace(found.pads[0], zone_connection=None) == base.pads[0]


@pytest.mark.parametrize("connection", ["solid", "thermal", "none", "thru_hole_only"])
def test_apply_the_four_values(connection: str) -> None:
    found = apply_pad_connections(footprint(), [Request("2", None, connection)])
    assert connections(found) == [("1", None), ("2", connection)]


def test_apply_one_of_several_pads_by_index() -> None:
    base = footprint("Mini_Edge_Cases")
    numbers = [pad.number for pad in base.pads]
    repeated = next(n for n in numbers if n and numbers.count(n) > 1)
    positions = [i for i, n in enumerate(numbers) if n == repeated]
    found = apply_pad_connections(base, [Request(repeated, 1, "solid")])
    assert [i for i, pad in enumerate(found.pads) if pad.zone_connection == "solid"] == [positions[1]]
    every = apply_pad_connections(base, [Request(repeated, None, "none")])
    assert [i for i, pad in enumerate(every.pads) if pad.zone_connection == "none"] == positions


def test_apply_without_requests_returns_the_instance() -> None:
    base = footprint()
    assert apply_pad_connections(base, []) is base


def test_apply_unknown_pad_and_index() -> None:
    base = footprint()
    issues: list[Issue] = []
    found = apply_pad_connections(
        base, [Request("7", None, "solid"), Request("1", 3, "solid")], where="D1", issues=issues
    )
    assert found is base
    first, second = note(issues)
    assert {first.code, second.code} == {"kicad.pad.zone-unknown-pad"} and first.severity == "error"
    assert "D1" in second.message and "'7'" in second.message and second.where == "D1:7"
    assert "D1" in first.message and "'1'" in first.message and "index 3" in first.message


def test_apply_refuses_an_unknown_connection() -> None:
    with pytest.raises(ValueError, match="direct"):
        apply_pad_connections(footprint(), [Request("1", None, "direct")])


# --- a kept footprint: the four cases of a named pad ---------------------------------------------


def test_keep_a_pad_that_equals_the_request_stays() -> None:
    kept = with_pad(footprint(), 0, "solid")
    issues: list[Issue] = []
    for locked in (False, True):
        found = keep_pad_connections(kept, [Request("1", None, "solid", locked)], where="D1", issues=issues)
        assert found is kept
    assert issues == []


def test_keep_a_pad_without_a_setting_takes_the_request() -> None:
    kept = footprint()
    issues: list[Issue] = []
    for locked in (False, True):
        found = keep_pad_connections(kept, [Request("1", None, "solid", locked)], where="D1", issues=issues)
        assert connections(found) == [("1", "solid"), ("2", None)]
    assert issues == []


def test_keep_an_unlocked_request_leaves_the_board_setting() -> None:
    kept = with_pad(footprint(), 0, "thermal")
    issues: list[Issue] = []
    found = keep_pad_connections(kept, [Request("1", None, "solid")], where="D1", issues=issues)
    assert found is kept
    (info,) = note(issues)
    assert (info.code, info.severity, info.where) == ("kicad.pad.zone-overridden", "info", "D1:1")
    assert all(word in info.message for word in ("D1", "pad 1", "solid", "thermal"))
    assert (
        info.hint
        == PAD_OVERRIDE_HINT
        == ("lock the request in the script, edit the pad in KiCad, or re-run with --discard-layout")
    )


def test_keep_a_locked_request_replaces_the_board_setting() -> None:
    kept = with_pad(footprint(), 0, "thermal")
    issues: list[Issue] = []
    request = Request("1", None, "solid", True)
    found = keep_pad_connections(kept, [request], where="D1", issues=issues)
    assert connections(found) == [("1", "solid"), ("2", None)]
    (warning,) = note(issues)
    assert (warning.code, warning.severity, warning.where) == ("kicad.pad.zone-forced", "warning", "D1:1")
    assert all(word in warning.message for word in ("D1", "pad 1", "solid", "thermal"))
    # stable: a second run on its own result reports nothing and returns an equal footprint
    again: list[Issue] = []
    assert keep_pad_connections(found, [request], where="D1", issues=again) == found and again == []


def test_keep_unknown_pad() -> None:
    kept = footprint()
    issues: list[Issue] = []
    assert keep_pad_connections(kept, [Request("9", None, "none")], where="D1", issues=issues) is kept
    (error,) = note(issues)
    assert error.code == "kicad.pad.zone-unknown-pad" and "D1" in error.message and "'9'" in error.message


def test_keep_changes_nothing_but_the_named_pads() -> None:
    kept = with_pad(with_pad(footprint(), 0, "thermal"), 1, "none")
    found = keep_pad_connections(kept, [Request("1", None, "solid", True)], where="D1")
    assert connections(found) == [("1", "solid"), ("2", "none")]
    assert dataclasses.replace(found, pads=kept.pads) == kept
    assert found.pads[1] is kept.pads[1]
    assert connections(kept) == [("1", "thermal"), ("2", "none")]  # pure


def test_requests_are_applied_in_number_then_index_order() -> None:
    kept = with_pad(with_pad(footprint(), 0, "thermal"), 1, "thermal")
    issues: list[Issue] = []
    keep_pad_connections(
        kept, [Request("2", None, "solid"), Request("1", None, "solid")], where="D1", issues=issues
    )
    assert [issue.where for issue in note(issues)] == ["D1:1", "D1:2"]


def test_module_exports_and_imports() -> None:
    assert {
        "PAD_ZONE_ISSUE_CODES",
        "PadZoneRequestLike",
        "apply_pad_connections",
        "keep_pad_connections",
    } <= set(zones.__all__)
    source = zones.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        assert "fenolite.dsl" not in handle.read()


def test_closed_set() -> None:
    """Scenario "Closed code table": every code the two functions produce is a key of the table with its
    severity, and every key is produced. The cases are run here, so the test does not depend on the order
    or the worker of the tests above."""
    produced: list[Issue] = []
    base = footprint()
    edited = with_pad(base, 0, "thermal")
    apply_pad_connections(base, [Request("7", None, "solid")], where="D1", issues=produced)
    apply_pad_connections(base, [Request("1", None, "solid")], where="D1", issues=produced)
    keep_pad_connections(base, [Request("7", 0, "solid")], where="D1", issues=produced)
    keep_pad_connections(base, [Request("1", None, "solid")], where="D1", issues=produced)
    keep_pad_connections(edited, [Request("1", None, "solid")], where="D1", issues=produced)
    keep_pad_connections(edited, [Request("1", None, "solid", True)], where="D1", issues=produced)
    keep_pad_connections(edited, [Request("1", None, "thermal", True)], where="D1", issues=produced)
    assert dict(PAD_ZONE_ISSUE_CODES) == {
        "kicad.pad.zone-unknown-pad": "error",
        "kicad.pad.zone-forced": "warning",
        "kicad.pad.zone-overridden": "info",
    }
    assert {issue.code for issue in note(produced)} == set(PAD_ZONE_ISSUE_CODES)
    assert len(produced) == 4
