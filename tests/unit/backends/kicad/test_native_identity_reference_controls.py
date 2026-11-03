# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authorial reference negatives before any private runtime identity rewrite (c0355)."""

import pytest
from _native_identity_refs import unreferenced_id_facts

from fenolite.backends.kicad.sexpr import parse

UID = "00000000-0000-4000-8000-000000003555"
PAD = f'(pad "1" smd circle (uuid "{UID}"))'


def test_unreferenced_aliases_are_reported_and_never_automatically_admitted():
    row = unreferenced_id_facts(parse(f"(kicad_pcb (footprint Own {PAD} {PAD}))"))
    assert row["definition_fields"] == 2 and row["aliased_ids"] == 1
    assert not row["physical_correspondence_or_runtime_admission_claimed"]


@pytest.mark.parametrize(
    "reference", [f'(members "{UID}")', f'(unknown "{UID}")', f'(unknown "prefix/{UID}/suffix")']
)
def test_known_unknown_and_embedded_references_refuse(reference):
    with pytest.raises(ValueError, match="reference"):
        unreferenced_id_facts(parse(f"(kicad_pcb (footprint Own {PAD}) {reference})"))


def test_context_references_are_not_hidden_by_json_escapes():
    with pytest.raises(ValueError, match="reference"):
        unreferenced_id_facts(
            parse(f"(kicad_pcb (footprint Own {PAD}))"),
            {"x.kicad_pro": ('{"hidden":"' + UID.replace("-", r"\u002d") + '"}').encode()},
        )


def test_cross_kind_alias_and_missing_id_refuse():
    for body in (
        f'(kicad_pcb (footprint Own {PAD}) (via (uuid "{UID}")))',
        '(kicad_pcb (footprint Own (pad "1" smd circle)))',
    ):
        with pytest.raises(ValueError):
            unreferenced_id_facts(parse(body))


def test_nested_polygon_arc_is_not_a_root_track_identity_but_references_are_scanned():
    primitive = "(primitives (gr_poly (pts (arc (start 0 0) (mid 1 1) (end 2 0)))))"
    body = f'(kicad_pcb (footprint Own (pad "1" smd custom (uuid "{UID}") {primitive})))'
    assert unreferenced_id_facts(parse(body))["definition_fields"] == 1
    with pytest.raises(ValueError, match="reference"):
        unreferenced_id_facts(parse(body.replace("(start 0 0)", f'(unknown "{UID}")')))
