# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a target KiCad major cannot read (capability kicad-version-gating, requirement "Emit check")."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import parse, walk
from fenolite.backends.kicad.versions import FileKind, check_emittable, wrap_rules

B = FileKind.BOARD


def board(version: int, body: str) -> str:
    return f'(kicad_pcb (version {version}) (generator "fenolite") {body})'


def codes(issues: tuple[object, ...]) -> list[str]:
    return [i.code for i in issues]  # type: ignore[attr-defined]


def test_padstack_allowed_for_9() -> None:
    padstack = '(padstack (mode front_inner_back) (layer "Inner" (shape circle) (size 1 1)))'
    pad = f'(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") {padstack})'
    node = parse(board(20241229, f'(footprint "x" {pad})'))
    assert [i for i in check_emittable(node, B, 9) if i.severity == "error"] == []


def test_via_protection_refused_for_9() -> None:
    node = parse(board(20241229, "(setup (tenting (front yes) (back yes)))"))
    issues = check_emittable(node, B, 9)
    assert {i.code for i in issues} == {"kicad.token.too-new"}
    assert "/kicad_pcb/setup[0]/tenting[0]/front[0]" in [i.where for i in issues]
    assert all("tenting-" in i.hint and "S-0030" in i.hint for i in issues)


def test_header_newer_than_target() -> None:
    node = parse(board(20260206, '(gr_line (start 0 0) (end 1 1) (layer "Edge.Cuts"))'))
    issues = check_emittable(node, B, 9)
    assert codes(issues) == ["kicad.version.header-too-new"] and issues[0].where == "/kicad_pcb"


def test_header_missing() -> None:
    issues = check_emittable(parse('(kicad_pcb (generator "x"))'), B, 10)
    assert codes(issues) == ["kicad.version.header-missing"] and issues[0].severity == "error"


def test_obsolete_token_for_10() -> None:
    node = parse(board(20260206, "(setup (pcbplotparams (plotinvisibletext no)))"))
    issues = check_emittable(node, B, 10)
    assert codes(issues) == ["kicad.token.obsolete"] and issues[0].severity == "warning"
    assert codes(check_emittable(node, B, 9)) == ["kicad.version.header-too-new"]


def test_obsolete_not_reported_for_9() -> None:
    node = parse(board(20241229, '(net 0 "") (net 1 "A") (setup (pcbplotparams (plotinvisibletext no)))'))
    assert check_emittable(node, B, 9) == ()
    assert codes(check_emittable(node, B, 10)) == ["kicad.token.obsolete"] * 3


def test_rules_constraint_refused_for_9() -> None:
    node = wrap_rules("(version 1)\n(rule mask (constraint bridged_mask))\n")
    issues = check_emittable(node, FileKind.RULES, 9)
    assert codes(issues) == ["kicad.token.too-new"] and "rules-type-bridged-mask" in issues[0].hint
    assert issues[0].where == "/kicad_dru/rule[0]/constraint[0]"
    assert check_emittable(node, FileKind.RULES, 10) == ()


def test_rules_unknown_constraint_value() -> None:
    node = wrap_rules("(version 1)\n(rule a (constraint frobnication (min 1mm)))\n")
    assert codes(check_emittable(node, FileKind.RULES, 10)) == ["kicad.token.uninventoried"]


def test_unknown_worksheet_token() -> None:
    node = parse('(kicad_wks (version 20231118) (generator "x") (frobnicate 1))')
    issues = check_emittable(node, FileKind.WORKSHEET, 10)
    assert codes(issues) == ["kicad.token.uninventoried"] and issues[0].where == "/kicad_wks/frobnicate[0]"


def test_worksheet_name_missing_from_the_public_page() -> None:
    header = '(version 20231118) (generator "pl_editor") (generator_version "10.0")'
    text = f"(kicad_wks {header} (setup (textsize 1 1)))"
    node = parse(text)
    assert check_emittable(node, FileKind.WORKSHEET, 10) == ()


def test_unmatched_board_path_not_reported() -> None:
    node = parse(board(20241229, '(gr_line (start 0 0) (end 1 1) (layer "Edge.Cuts"))'))
    assert check_emittable(node, B, 9) == ()


def test_value_rows() -> None:
    node = parse(board(20241229, '(via buried (at 1 1) (size 0.6) (drill 0.3) (layers "In1.Cu" "In2.Cu"))'))
    issues = check_emittable(node, B, 9)
    assert codes(issues) == ["kicad.token.too-new"] and issues[0].where == "/kicad_pcb/via[0]"


def test_where_is_exactly_a_walk_locator() -> None:
    node = parse(board(20241229, '(footprint "a") (footprint "b" (pad "1" (tenting (front yes))) (barcode))'))
    locators = {loc for loc, _ in walk(node)}
    issues = check_emittable(node, B, 9)
    assert issues and all(i.where in locators for i in issues)
    assert "/kicad_pcb/footprint[1]/pad[0]/tenting[0]/front[0]" in {i.where for i in issues}


def test_document_order_and_no_mutation() -> None:
    text = board(20241229, '(setup (tenting (front yes))) (variants (variant (name "V")))')
    node = parse(text)
    issues = check_emittable(node, B, 9)
    order = [loc for loc, _ in walk(node)]
    assert [order.index(i.where) for i in issues] == sorted(order.index(i.where) for i in issues)
    assert node == parse(text)


def test_unsupported_target() -> None:
    with pytest.raises(ValueError):
        check_emittable(parse(board(20241229, "")), B, 8)
