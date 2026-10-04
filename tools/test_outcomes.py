# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Compare the test outcomes of two pytest runs from their JUnit XML files.

    uv run pytest -q --junitxml serial.xml
    uv run pytest -q -n auto --dist loadfile --junitxml parallel.xml
    uv run python tools/test_outcomes.py serial.xml parallel.xml

Prints the totals of each run and every test id whose outcome differs. Exit 0 when both runs hold
the same test ids with the same outcomes, 1 when they differ, 2 on a usage error. It proves that a
parallel run (capability ci-baseline, "Parallel test runs") gives the results of a serial run.
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

NOT_PASSED = ("error", "failure", "skipped")


def outcomes(path: Path) -> dict[str, str]:
    """Test id → ``passed``, ``skipped``, ``failure`` or ``error`` (joined with ``+`` when several apply)."""
    found: dict[str, str] = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        key = f"{case.get('classname', '')}::{case.get('name', '')}"
        kinds = sorted({child.tag for child in case} & set(NOT_PASSED))
        outcome = "+".join(kinds) or "passed"
        if key in found and found[key] != outcome:  # setup and teardown of one test reported apart
            outcome = "+".join(sorted({*found[key].split("+"), *outcome.split("+")} - {"passed"}))
        found[key] = outcome
    return found


def totals(found: dict[str, str]) -> str:
    counts = Counter(found.values())
    return ", ".join(f"{counts[name]} {name}" for name in sorted(counts)) or "no tests"


def differences(first: dict[str, str], second: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for key in sorted(set(first) | set(second)):
        one, two = first.get(key, "absent"), second.get(key, "absent")
        if one != two:
            lines.append(f"{key}: {one} -> {two}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("first", type=Path, help="JUnit XML of the reference run")
    parser.add_argument("second", type=Path, help="JUnit XML of the run to compare")
    args = parser.parse_args(argv)
    runs: list[dict[str, str]] = []
    for path in (args.first, args.second):
        try:
            runs.append(outcomes(path))
        except (OSError, ET.ParseError) as error:
            print(f"cannot read {path}: {error}", file=sys.stderr)
            return 2
        print(f"{path.name}: {len(runs[-1])} tests: {totals(runs[-1])}")
    lines = differences(runs[0], runs[1])
    print(f"differences: {len(lines)}")
    for line in lines:
        print(f"  {line}")
    return 1 if lines else 0


if __name__ == "__main__":
    sys.exit(main())
