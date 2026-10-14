# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Adapt validated kit records to the pure backend graduation rule.

Freshness is measured by the existing kit verifier; missing current kit data stays
unknown. This module does not build samples or launch any external application.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from fenolite.core.evidence import GraduationRun
from fenolite.verify.hypotheses import HypothesisRow
from fenolite.verify.kit.manifest import Kit
from fenolite.verify.kit.record import record_problems, stale_rows


def readback_tests(repository: Path, declared: Mapping[str, str]) -> frozenset[str]:
    """Declared pytest nodes whose source contains the named top-level test function.

    Parsing never imports tests or runs their fixtures. Missing nodes are excluded;
    malformed source and metadata raise an actionable error instead of hiding a bug.
    """
    found: set[str] = set()
    root = repository.resolve()
    for node in sorted(set(declared.values())):
        path, separator, name = node.partition("::")
        relative = Path(path)
        if not separator or not name.startswith("test_") or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid own-readback node: {node}")
        source = (root / relative).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            continue
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=path)
        if any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
            for item in tree.body
        ):
            found.add(node)
    return frozenset(found)


def run_snapshots(
    register: Sequence[HypothesisRow],
    records: Sequence[Mapping[str, Any]],
    kit: Kit | None,
    *,
    committed: bool = False,
) -> tuple[GraduationRun, ...]:
    """Validated records; only repository-loaded records may be marked committed."""
    for record in records:
        problems = record_problems(record)
        if problems:
            raise ValueError("invalid graduation kit record: " + "; ".join(problems))
    stale = None if kit is None else frozenset(stale_rows(register, records, kit))
    return tuple(
        GraduationRun(
            run_id=str(record["run_id"]),
            passed_hypotheses=frozenset(
                str(hypothesis["id"])
                for hypothesis in record["hypotheses"]
                if hypothesis["outcome"] == "pass"
            ),
            stale_hypotheses=stale,
            committed=committed and not record["synthetic"],
        )
        for record in records
    )


__all__ = ["readback_tests", "run_snapshots"]
