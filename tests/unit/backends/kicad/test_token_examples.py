# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored fuzz examples (capability kicad-token-inventory, requirement "Examples and controls")."""

from __future__ import annotations

from pathlib import Path

import _fuzzmod
import pytest

from fenolite.backends.kicad.versions import FileKind, load_inventory

fuzz = _fuzzmod.load()
DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "tokens"
INV = load_inventory()
EXAMPLES = fuzz.load_examples((DATA / "examples.toml").read_text(encoding="utf-8"), INV)
NEGATIVES = {f"negative-unknown-{c}" for c in ("top", "setup", "segment", "footprint", "pad")}
OTHER_CONTROLS = ("lenient-general", "future-header", "dev-header-9", "wks-future", "wks-unknown")
CONTROLS = {"positive-baseline", "rules-canary-invented", *OTHER_CONTROLS, *NEGATIVES}


def toml_example(**fields: object) -> str:
    """One [[example]] table; strings and lists are written as TOML literals."""
    body = "".join(f"{k} = {v!r}\n".replace("'", '"') for k, v in fields.items())
    return "[[example]]\n" + body


def test_examples_load_and_are_ascii() -> None:
    assert (DATA / "examples.toml").read_bytes().isascii()
    ids = {e.id for e in EXAMPLES}
    assert CONTROLS <= ids
    for example in EXAMPLES:
        if example.id in CONTROLS:
            assert example.expect and set(example.expect) == {"9", "10"}, example.id


def test_every_host_exists() -> None:
    for example in EXAMPLES:
        for kind in example.kinds:
            fuzz.exercised_rows(example, kind, INV)


def test_missing_host_fails() -> None:
    text = toml_example(id="x", kinds=["kicad_pcb"], host="kicad_pcb/nothing", mode="append", fragment="(a)")
    (loaded,) = fuzz.load_examples(text, INV)
    with pytest.raises(fuzz.UsageError, match=r"example x: host 'kicad_pcb/nothing'"):
        fuzz.build_cases(INV, [loaded], 10)


def test_unknown_form_id_fails() -> None:
    text = toml_example(id="y", kinds=["kicad_pcb"], host="kicad_pcb", mode="append", fragment="(a)",
                   exercises=["net-by-number"])  # fmt: skip
    with pytest.raises(fuzz.UsageError, match="example y: exercises unknown form row 'net-by-number'"):
        fuzz.load_examples(text, INV)


def test_form_row_exercised_explicitly() -> None:
    by_id = {e.id: e for e in EXAMPLES}
    assert fuzz.exercised_rows(by_id["net-by-name"], FileKind.BOARD, INV) == ("net-by-name",)
    text = toml_example(
        id="n", kinds=["kicad_pcb"], host="kicad_pcb", mode="append", fragment="(segment (net 1))"
    )
    (plain,) = fuzz.load_examples(text, INV)
    assert "net-by-name" not in fuzz.exercised_rows(plain, FileKind.BOARD, INV)


def test_examples_bad_shapes_rejected() -> None:
    cases = [
        (toml_example(id="a", kinds=["kicad_pcb"]), "give either file"),
        (toml_example(id="a", kinds=["kicad_pcb"], host="kicad_pcb", mode="insert", fragment="(a)"), "mode"),
        (toml_example(id="a", kinds=["kicad_pcb"], file="nope.kicad_pcb"), "not found"),
        (
            toml_example(id="a", kinds=["kicad_pcb"], host="kicad_pcb", mode="append", fragment="(\u00e9)"),
            "ASCII",
        ),
        (toml_example(id="a", kinds=["kicad_pcb"], file="future.kicad_pcb", colour="red"), "unknown key"),
    ]
    for text, message in cases:
        with pytest.raises(fuzz.UsageError, match=message):
            fuzz.load_examples(text, INV, base=DATA)


def required_rows() -> list[str]:
    floor = {FileKind.BOARD: 8, FileKind.FOOTPRINT: 8, FileKind.RULES: 9}
    rows = [
        r.id
        for r in INV.tokens
        if FileKind.WORKSHEET in r.kinds
        or r.until_major is not None
        or any(k in floor and r.since_major > floor[k] for k in r.kinds)
    ]
    return rows + [f.id for f in INV.forms]


def test_coverage() -> None:
    exercised: set[str] = set()
    for example in EXAMPLES:
        for kind in example.kinds:
            exercised.update(fuzz.exercised_rows(example, kind, INV))
    missing = [r for r in required_rows() if r not in exercised]
    assert not missing, "rows no example exercises: " + ", ".join(missing)


def test_coverage_isolates_rows_above_9() -> None:
    """Each row above 9 is the only row above 9 in at least one example (credit on 9.0)."""
    above = {r.id: r.since_major for r in INV.tokens if r.since_major > 9} | {
        f.id: f.since_major for f in INV.forms
    }
    isolated: set[str] = set()
    for example in EXAMPLES:
        for kind in example.kinds:
            rows = [r for r in fuzz.exercised_rows(example, kind, INV) if r in above]
            if len(rows) == 1:
                isolated.add(rows[0])
    assert not (set(above) - isolated), sorted(set(above) - isolated)
