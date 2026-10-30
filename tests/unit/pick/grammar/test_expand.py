# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Lazy expansion of grammar families (change c0263, "Lazy expansion", "Validity matrix", scenario "A query
prunes before it expands")."""

from __future__ import annotations

import pytest
from _grammars import MLCC, edited, mlcc

from fenolite.pick.grammar import EXPANSION_LIMIT
from fenolite.pick.grammar.candidates import candidate_row
from fenolite.pick.grammar.expand import Candidate, Expansion, ExpansionLimitError, admitted, expand
from fenolite.pick.grammar.schema import GrammarFamily, parse_family
from fenolite.pick.match import failure
from fenolite.pick.query import parse_query
from fenolite.pick.rows import PROJECT

CASES = ("0201", "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2220", "2512")


def generated(codes: int = 10, grades: int = 16, low: str = "1p", high: str = "100mF") -> GrammarFamily:
    """An authored capacitor grammar of ``codes`` codes per field (three voltages), ``grades`` grades and
    E192 values from ``low`` to ``high`` (10⁹ combinations by default)."""
    lines = [
        'schema = "fenolite.family.v1"',
        'id = "Example:EX_GEN"',
        'kind = "capacitor"',
        'summary = "Generated grammar for the expansion tests (illustrative)"',
        'manufacturer = "Example Passive"',
        'version = "1.0.0"',
        'licence = "CC0-1.0"',
        'evidence = "INFERRED"',
        'sources = ["authored for the test"]',
        'symbol = "Fenolite:Capacitor"',
        'footprint = "Fenolite:Chip_0603"',
        'pattern = "EG{size}{dielectric}{value}{tolerance}{voltage}{grade}{packing}"',
    ]
    fields = {
        "size": [f'"S{i}" = {{ case = "{CASES[i]}" }}' for i in range(codes)],
        "dielectric": [f'D{i} = {{ dielectric = "X{i}" }}' for i in range(codes)],
        "tolerance": [f'T{i} = {{ tolerance = "{i + 1}%" }}' for i in range(codes)],
        "voltage": [f'V{i} = {{ rating = "{i + 1}V" }}' for i in range(3)],
        "grade": [f"G{i} = {{}}" for i in range(grades)],
        "packing": [f'P{i} = {{ packing = "p{i}" }}' for i in range(codes)],
    }
    for name, entries in fields.items():
        lines.append(f"[fields.{name}]")
        if name == "packing":
            lines += ['role = "ordering"', 'prefer = "P0"']
        lines += [f"codes.{entry}" for entry in entries]
    lines += ["[fields.value]", 'scheme = "eia4"', 'unit = "pF"', 'series = "E192"']
    lines += ["[[valid]]", f'value = {{ min = "{low}", max = "{high}" }}']
    lines += ["[[exclude]]", 'grade = "G1"', 'value = { min = "1n", max = "2n" }']
    return parse_family("\n".join(lines) + "\n", file="generated.toml")


def test_canonical_order() -> None:
    found = [candidate.mpn for candidate in expand(mlcc())]
    assert found[:4] == ["EX03R101JAB", "EX03R101JAT", "EX03R101JBB", "EX03R101JBT"]
    keys = [
        (c.codes[0][1], c.codes[1][1], c.value, c.codes[3][1], c.codes[4][1], c.codes[5][1])
        for c in expand(mlcc())
    ]
    assert keys == sorted(keys) and len(found) == len(set(found))


def test_the_matrix_and_its_exclusion() -> None:
    family = mlcc()
    found = {candidate.mpn for candidate in expand(family)}
    assert "EX03R104KAT" in found and "EX03R104KBT" not in found  # excluded: 0603 at 50 V from 47 nF
    assert "EX03R393KBT" in found and "EX05C471JBT" in found and "EX05R471JBT" not in found
    assert not admitted(family, {"size": "03", "dielectric": "R", "tolerance": "K", "voltage": "B",
                                 "packing": "T"}, parse_query("capacitor(100nF)").value.low)  # type: ignore[union-attr]  # fmt: skip


def test_ordering_fields_take_prefer_under_a_query() -> None:
    query = parse_query("capacitor(470pF, case=0805)")
    assert [candidate.mpn for candidate in expand(mlcc(), query)] == ["EX05C471JBT"]
    assert {candidate.mpn for candidate in expand(mlcc())} >= {"EX05C471JBT", "EX05C471JBB"}


def _matching(family: GrammarFamily, query_text: str, candidates: list[Candidate]) -> list[str]:
    query = parse_query(query_text)
    prefer = family.fields["packing"].prefer
    preferred = [candidate for candidate in candidates if dict(candidate.codes)["packing"] == prefer]
    return [
        candidate.mpn
        for candidate in preferred
        if failure(query, candidate_row(candidate, origin=PROJECT, catalog="test")) is None
    ]


@pytest.mark.parametrize(
    "query",
    [
        "capacitor(4.7nF, tolerance<=1%, rating>=3V, case=0402, dielectric=X1)",
        "capacitor(4.7nF..4.9nF, tolerance<=1%, rating>=3V, case=0201, dielectric=X0)",
        "capacitor(1nF, tolerance<=1%, rating>=3V, case=0402, dielectric=X1)",
    ],
)
def test_a_query_prunes_before_it_expands(query: str) -> None:
    """Scenario "A query prunes before it expands": the cut expansion of a 10⁹-combination grammar visits
    fewer than 100 combinations and agrees with a brute-force filter over a small copy."""
    big = generated()
    assert Expansion(big).size >= 10**9
    cut = Expansion(big, parse_query(query))
    found = [candidate.mpn for candidate in cut]
    assert cut.visited < 100 and found
    small = generated(codes=2, grades=2, low="1n", high="10n")
    brute = _matching(small, query, list(Expansion(small)))
    pruned = _matching(small, query, list(Expansion(small, parse_query(query))))
    assert pruned == brute and brute


def test_the_expansion_limit() -> None:
    with pytest.raises(ExpansionLimitError) as error:
        expand(generated(), parse_query("capacitor(1pF..1uF, case=0402)"))
    found = error.value.issue
    assert found.code == "family.expansion-limit" and found.severity == "error"
    assert "dielectric 10" in found.message and str(EXPANSION_LIMIT) in found.message
    assert Expansion(generated(), parse_query("capacitor(1pF..1uF, case=0402)")).visited == 0


def test_row_pins_one_candidate() -> None:
    query = parse_query("capacitor(100nF, row=Example:EX_MLCC@EX03R104JAT)")
    assert [candidate.mpn for candidate in expand(mlcc(), query)] == ["EX03R104JAT"]
    assert list(expand(mlcc(), parse_query("capacitor(100nF, row=Other:X)"))) == []
    bulk = parse_query("capacitor(100nF, row=Example:EX_MLCC@EX03R104JAB)")  # an ordering code beside prefer
    assert [candidate.mpn for candidate in expand(mlcc(), bulk)] == ["EX03R104JAB"]


def test_candidate_text_is_stable_across_unrelated_edits() -> None:
    before = {c.mpn: c.sha256() for c in expand(mlcc())}
    widened = edited(MLCC, 'value = { min = "10pF", max = "1nF" }', 'value = { min = "10pF", max = "2.2nF" }')
    after = {c.mpn: c.sha256() for c in expand(widened)}
    assert before["EX03R104KAT"] == after["EX03R104KAT"] and set(before) < set(after)
    renamed = edited(MLCC, 'codes.T = { packing = "reel" }', 'codes.T = { packing = "tape" }')
    assert {c.mpn: c.sha256() for c in expand(renamed)}["EX03R104KAT"] != before["EX03R104KAT"]
