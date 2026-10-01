# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots persisted in the kicad extension bag (capability kicad-slots)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import parse
from fenolite.backends.kicad.slots import from_ext, from_ext_all, split, to_ext
from fenolite.model.base import ExtBag, Modeled, Opaque

PAD = parse('(pad "1" smd rect (at 1 2) (frobnicate 3) (size 1 1))')
PAD_SLOTS = split(PAD, {"at": "position", "size": "size"}, positional=("number", "type", "shape"),
                  min_version="20260206")  # fmt: skip


def test_round_trip_through_extbag() -> None:
    bag = to_ext(PAD_SLOTS)
    assert from_ext(bag) == PAD_SLOTS
    assert bag.min_version == "20260206"
    assert bag.payload[4] == ("slot:.:opaque@20260206", "(frobnicate 3)")
    assert bag.payload[0] == ("slot:.:modeled", "number")


def test_unknown_grandchild_of_a_modelled_sub_list() -> None:
    text = parse('(gr_text "x" (at 1 2) (effects (font (size 1 1)) (justify left)))')
    entity = split(
        text, {"at": "position", "effects": "effects"}, positional=("text",), min_version="20260206"
    )
    effects_node = text.nodes("effects")[0]
    effects = split(effects_node, {"justify": "justify"}, min_version="20260206")
    bag = to_ext({".": entity, "effects[0]": effects})
    groups = from_ext_all(bag)
    assert groups["effects[0]"] == (Opaque("(font (size 1 1))", "20260206"), Modeled("justify"))
    assert groups["."] == entity == (Modeled("text"), Modeled("position"), Modeled("effects"))
    assert [k for k, _ in bag.payload][:3] == ["slot:.:modeled"] * 3


def test_base_version_is_not_lowered_and_foreign_pairs_kept() -> None:
    base = ExtBag(
        "20260206", (("uuid", "abc"), ("slot:.:modeled", "old"), ("slot:x[0]:opaque", "(q)"), ("z", "1"))
    )
    slots = (Modeled("a"), Opaque("(b)", "20241229"))
    bag = to_ext(slots, base)
    assert bag.min_version == "20260206"
    assert bag.payload[:2] == (("uuid", "abc"), ("z", "1"))
    assert from_ext(bag) == slots
    assert from_ext(bag, "x[0]") == (Opaque("(q)"),)
    assert [k for k, _ in bag.payload[2:]] == ["slot:.:modeled", "slot:.:opaque@20241229", "slot:x[0]:opaque"]


def test_versions_compare_as_integers() -> None:
    bag = to_ext((Opaque("(a)", "9"), Opaque("(b)", "10")))
    assert bag.min_version == "10"
    assert to_ext((Modeled("a"),)).min_version is None


def test_groups_sorted_dot_first() -> None:
    bag = to_ext({"z[0]": (Modeled("z"),), "a[0]": (Modeled("a"),), ".": (Modeled("d"),)})
    assert [k for k, _ in bag.payload] == ["slot:.:modeled", "slot:a[0]:modeled", "slot:z[0]:modeled"]


def test_locator_with_colon() -> None:
    bag = to_ext({"odd:name[0]": (Opaque("x", "1"),)})
    assert from_ext(bag, "odd:name[0]") == (Opaque("x", "1"),)


@pytest.mark.parametrize("key", ["slot:.:weird", "slot:.:opaque@x", "slot:modeled", "slot::modeled"])
def test_unknown_slot_key(key: str) -> None:
    with pytest.raises(ValueError, match=key.replace(".", r"\.")):
        from_ext(ExtBag(None, ((key, "x"),)))


def test_non_decimal_version_rejected() -> None:
    with pytest.raises(ValueError):
        to_ext((Opaque("(a)", "v1"),))


def test_missing_locator_is_empty() -> None:
    assert from_ext(ExtBag(), "effects[0]") == ()
