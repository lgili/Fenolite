# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The committed token fuzz results agree with the current inventory and examples (capability
kicad-token-inventory, requirement "Committed fuzz results")."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import _fuzzmod
import pytest

from fenolite.backends.kicad.versions import FileKind, load_inventory
from fenolite.core.evidence import Level

fuzz = _fuzzmod.load()
ROOT = Path(__file__).resolve().parents[4]
RESULTS = ROOT / "docs" / "evidence" / "kicad" / "token-fuzz"
COMMITTED = ("9.0.9", "10.0.6")
INV = load_inventory()
EXAMPLES = fuzz.load_examples((fuzz.DATA / "examples.toml").read_text(encoding="utf-8"), INV)


def committed(version: str) -> dict[str, Any]:
    return json.loads((RESULTS / f"{version}.json").read_text(encoding="utf-8"))


def stale_cases(result: dict[str, Any]) -> list[str]:
    major = int(result["kicad_cli"]["version"].split(".")[0])
    fresh = {c.key: c for c in fuzz.build_cases(INV, EXAMPLES, major)}
    problems = []
    for case in result["cases"]:
        key = (case["example"], case["kind"], case["header_version"])
        now = fresh.get(key)
        if now is None:
            problems.append(f"{key}: no such case any more; run the fuzz again")
        elif now.example_sha256 != case["example_sha256"]:
            problems.append(f"{key}: example {case['example']} changed since the results; run the fuzz again")
        elif list(now.rows) != case["rows"] or now.expected != case["expected"]:
            problems.append(f"{key}: rows or expectation changed with the inventory; run the fuzz again")
    missing = sorted(set(fresh) - {(c["example"], c["kind"], c["header_version"]) for c in result["cases"]})
    problems += [f"{key}: case not in the committed results" for key in missing]
    return problems


@pytest.mark.parametrize("version", COMMITTED)
def test_results_are_current(version: str) -> None:
    problems = stale_cases(committed(version))
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("version", COMMITTED)
def test_outcomes_match_expectations(version: str) -> None:
    problems = fuzz.mismatches(committed(version)["cases"])
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("version", COMMITTED)
def test_results_header(version: str) -> None:
    result = committed(version)
    assert result["format"] == 1 and result["kicad_cli"]["version"] == version
    assert result["kicad_cli"]["env"] == {"KICAD_CONFIG_HOME": "<tmp>/cfg", "LANG": "C", "LC_ALL": "C"}
    keys = [(c["example"], c["kind"], c["header_version"]) for c in result["cases"]]
    assert keys == sorted(keys)
    assert all(c["outcome"] in fuzz.OUTCOMES for c in result["cases"])
    assert "timestamp" not in json.dumps(result)


def test_nine_comes_from_the_pinned_image() -> None:
    assert committed("9.0.9")["kicad_cli"]["image"].startswith("kicad/kicad:9.0.9@sha256:")


def required_rows() -> list[str]:
    floor = {
        FileKind.BOARD: 8,
        FileKind.FOOTPRINT: 8,
        FileKind.RULES: 9,
        FileKind.SCHEMATIC: 8,
        FileKind.SYMBOL_LIB: 8,
    }
    rows = [
        r.id
        for r in INV.tokens
        if FileKind.WORKSHEET in r.kinds
        or r.until_major is not None
        or any(k in floor and r.since_major > floor[k] for k in r.kinds)
    ]
    return rows + [f.id for f in INV.forms]


def test_required_rows_verified_or_hypothesised() -> None:
    levels = fuzz.row_levels(INV, [committed(v) for v in COMMITTED])
    hypotheses = {r.id: r.hypothesis for r in INV.tokens} | {f.id: f.hypothesis for f in INV.forms}
    unproven = {
        r for r, by_major in levels.items() if any(by_major.get(m) != Level.KICAD_VERIFIED for m in (9, 10))
    }
    weak = [r for r in required_rows() if r in unproven and not hypotheses[r]]
    assert not weak, (
        "required rows neither verified on 9.0.9 and 10.0.6 nor under a hypothesis: " + ", ".join(weak)
    )


def test_keyword_only_rows_have_results() -> None:
    levels = fuzz.row_levels(INV, [committed(v) for v in COMMITTED])
    for row in INV.tokens:
        if set(row.sources) <= {"S-0033", "S-0034", "S-0036"}:
            assert Level.KICAD_VERIFIED in levels[row.id].values(), row.id


def test_stale_example_detected() -> None:
    result = committed("10.0.6")
    edited = dict(result, cases=[dict(c) for c in result["cases"]])
    edited["cases"][0]["example_sha256"] = "0" * 64
    assert any("changed since the results" in p for p in stale_cases(edited))


def test_unexpected_acceptance_detected() -> None:
    case = next(c for c in committed("9.0.9")["cases"] if c["expected"] == "reject")
    problems = fuzz.mismatches([dict(case, outcome="load")])
    assert problems and case["example"] in problems[0] and "expected reject, got load" in problems[0]
