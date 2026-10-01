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
