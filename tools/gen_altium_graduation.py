# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Freeze repository-verified graduation decisions for an installed package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fenolite.backends.altium import claims
from fenolite.backends.altium.graduation import SNAPSHOT
from fenolite.backends.base import graduated
from fenolite.cli._kit import kit_sources
from fenolite.verify import load_register
from fenolite.verify.graduation import readback_tests, run_snapshots
from fenolite.verify.kit.manifest import KIT_FILE, kit_files, read_kit
from fenolite.verify.kit.record import label_problems, load_records

ROOT = Path(__file__).resolve().parents[1]


def render() -> str:
    """Canonical snapshot, using actual current kit bytes and committed records."""
    register = load_register(ROOT / "docs/hypotheses.md")
    records = load_records(ROOT)
    kit = read_kit(kit_files(kit_sources())[KIT_FILE])
    problems = label_problems(register, records, kit)
    if problems:
        raise ValueError("invalid graduation evidence: " + "; ".join(problems))
    runs = run_snapshots(register, records, kit, committed=True)
    suite = readback_tests(ROOT, claims.OWN_READBACK)
    by_id = {row.id: row for row in register}
    kinds: dict[str, Any] = {}
    for row in sorted(claims.RAW_MATRIX, key=lambda row: row.kind):
        if row.write is None:
            continue
        _, missing = graduated(
            row,
            by_id,
            runs,
            own_readback=claims.OWN_READBACK.get(row.kind),
            suite_tests=suite,
        )
        kinds[row.kind] = {
            "hypotheses": sorted(row.write.hypotheses),
            "write_level": row.write.level.value,
            "own_readback": claims.OWN_READBACK.get(row.kind),
            "missing": list(missing),
        }
    return json.dumps({"schema": "fenolite.altium-graduation.v0", "kinds": kinds}, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render()
    if args.check:
        if SNAPSHOT.read_text(encoding="utf-8") != text:
            print("Altium graduation snapshot is stale; run uv run python tools/gen_altium_graduation.py")
            return 1
    else:
        SNAPSHOT.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
