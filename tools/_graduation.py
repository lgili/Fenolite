# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build the installed evidence snapshot from the public register and committed kit records."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from fenolite.verify.hypotheses import HypothesisRow
from fenolite.verify.kit import record


def snapshot(root: Path, register: Sequence[HypothesisRow]) -> str:
    records = record.load_records(root)
    stale: tuple[str, ...] = ()
    if records:
        from fenolite.cli._kit import kit_sources
        from fenolite.verify.kit.manifest import KIT_FILE, kit_files, read_kit

        kit = read_kit(kit_files(kit_sources(root / "examples/kit"))[KIT_FILE])
        problems = record.label_problems(register, records, kit)
        # Stale rows are data for the conservative rule, not grounds to keep a
        # formerly graduated write stable. All other malformed labels are refused.
        fatal = [problem for problem in problems if "stale" not in problem]
        if fatal:
            raise ValueError("; ".join(fatal))
        stale = record.stale_rows(register, records, kit)
    runs = []
    for run in records:
        relative = f"{record.RECORDS_DIR}/{run['run_id']}.json"
        tracked = (
            subprocess.run(
                ["git", "cat-file", "-e", f"HEAD:{relative}"],
                cwd=root,
                capture_output=True,
                check=False,
            ).returncode
            == 0
        )
        # A modified formerly committed record is not the committed evidence.
        original = (
            subprocess.run(
                ["git", "show", f"HEAD:{relative}"],
                cwd=root,
                capture_output=True,
                check=False,
            )
            if tracked
            else None
        )
        committed = bool(original and original.returncode == 0 and json.loads(original.stdout) == run)
        runs.append(
            {
                "id": run["run_id"],
                "hypotheses": sorted(row["id"] for row in run["hypotheses"] if row["outcome"] == "pass"),
                "stale": sorted(stale),
                "committed": committed,
                "synthetic": run["synthetic"],
            }
        )
    hypotheses = []
    for row in sorted(register, key=lambda row: row.id):
        label = record.KIT_LABEL.fullmatch(row.level_text)
        hypotheses.append(
            {
                "id": row.id,
                "level": row.level.value,
                "refuted": row.refuted,
                "run_id": label.group("run") if label else "",
            }
        )
    return (
        json.dumps(
            {"schema": "fenolite.graduation.v0", "hypotheses": hypotheses, "runs": runs},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
