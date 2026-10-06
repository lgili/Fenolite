# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The committed token fuzz results reproduce on the running kicad-cli (capability ci-baseline)."""

from __future__ import annotations

from pathlib import Path

import _fuzzmod
import pytest
from _kicad import cli

pytestmark = [pytest.mark.needs_kicad, pytest.mark.slow]
fuzz = _fuzzmod.load()
RESULTS = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "kicad" / "token-fuzz"


def test_committed_results() -> None:
    runner = fuzz.subprocess_runner(cli())
    version = fuzz.probe_version(runner)
    if not (RESULTS / f"{version}.json").is_file():
        command = "uv run python tools/kicad_token_fuzz.py --write docs/evidence/kicad/token-fuzz"
        pytest.fail(f"the results file for kicad-cli {version} is missing: run '{command}' with it")
    assert fuzz.main(["--check", str(RESULTS)], runner=runner) == 0


def test_schematic_and_symbol_skeletons_load() -> None:
    """The positive controls of the two load checks of c0060 load on the running major."""
    from fenolite.backends.kicad.versions import FileKind, load_inventory

    runner = fuzz.subprocess_runner(cli())
    major = int(fuzz.probe_version(runner).split(".")[0])
    inventory = load_inventory()
    examples = fuzz.load_examples((fuzz.DATA / "examples.toml").read_text(encoding="utf-8"), inventory)
    wanted = {"positive-baseline", "negative-unknown-sch-top", "negative-unknown-sym-top"}
    cases = fuzz.build_cases(inventory, [e for e in examples if e.id in wanted], major)
    kinds = (FileKind.SCHEMATIC, FileKind.SYMBOL_LIB)
    skeletons = [c for c in cases if c.example == "positive-baseline" and c.kind in kinds]
    assert {c.kind for c in skeletons} == set(kinds)
    for case in skeletons:
        assert fuzz.run_case(case, runner).outcome == "load", case.key
    rejected = next(c for c in cases if c.example == "negative-unknown-sch-top")
    outcome = fuzz.run_case(rejected, runner)
    assert (outcome.outcome, outcome.exit_code) == ("reject", 3)
