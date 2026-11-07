# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent agreement on printed pin rows and exact package facts (c0265)."""

from __future__ import annotations

from typing import Any, cast

from fenolite.core.errors import Issue
from fenolite.library.codes import issue
from fenolite.library.proposals.checks import normalized_pin, terminal_bound
from fenolite.library.proposals.schema import Proposal

DENSE_PIN_THRESHOLD = 100


def _differences(a: Any, b: Any, path: str) -> list[tuple[str, Any, Any]]:
    if (
        isinstance(a, dict)
        and isinstance(b, dict)
        and not set(cast(dict[str, Any], a)) <= {"min", "nom", "max"}
    ):
        left, right = cast(dict[str, Any], a), cast(dict[str, Any], b)
        return [
            row
            for key in sorted(set(left) | set(right))
            for row in _differences(left.get(key), right.get(key), path + "." + key)
        ]
    return [(path, a, b)] if a != b else []


def agreement(proposals: list[Proposal]) -> list[Issue]:
    if len(proposals) not in {1, 2}:
        raise ValueError("one or two proposals are supported")
    first = proposals[0]
    if len(proposals) == 1:
        if first.family == "grid" or terminal_bound(first) > DENSE_PIN_THRESHOLD:
            return [
                issue(
                    "proposal.second-required",
                    "a grid or package above 100 pins needs two independent proposals",
                    where="proposer",
                )
            ]
        return []
    second = proposals[1]
    a, b = first.data["proposer"], second.data["proposer"]
    found: list[Issue] = []
    if (a["kind"], a["name"]) == (b["kind"], b["name"]):
        found.append(issue("proposal.not-independent", "proposer kind/name must differ", where="proposer"))
    if first.data["datasheet"]["sha256"] != second.data["datasheet"]["sha256"]:
        found.append(
            issue(
                "proposal.datasheet-mismatch",
                "proposals name different datasheet digests",
                where="datasheet.sha256",
            )
        )
    left = {str(r["number"]): normalized_pin(r) for r in first.pins}
    right = {str(r["number"]): normalized_pin(r) for r in second.pins}
    differences = [
        (f"pin[{n}]", left.get(n), right.get(n))
        for n in sorted(set(left) | set(right))
        if left.get(n) != right.get(n)
    ]
    differences += _differences(
        {"family": first.family, "row_labels": first.data["package"].get("row_labels"), **first.parameters},
        {
            "family": second.family,
            "row_labels": second.data["package"].get("row_labels"),
            **second.parameters,
        },
        "package",
    )
    pages = [p.data["package"].get("cite", {}).get("page") for p in proposals]
    for path, a, b in differences:
        pin = path.removeprefix("pin[").removesuffix("]")
        cited = (
            [
                next((r.get("cite", {}).get("page") for r in p.pins if r["number"] == pin), None)
                for p in proposals
            ]
            if path.startswith("pin[")
            else pages
        )
        found.append(issue("proposal.disagree", f"{a!r} != {b!r}; cited pages {cited}", where=path))
    return found
