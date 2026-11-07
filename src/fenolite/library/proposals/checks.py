# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pure datasheet binding and parameter cross-checks for proposals (c0265)."""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, cast

from fenolite.catalog.footprints.record import FAMILIES
from fenolite.core.errors import Issue
from fenolite.core.quantities import micro_units
from fenolite.library.codes import issue
from fenolite.library.proposals.schema import RATING_UNITS, Proposal
from fenolite.library.rules import row_name

MAX_PROPOSAL_PINS = 10_000


def terminal_bound(proposal: Proposal) -> int:
    package = proposal.data["package"]
    return max(
        int(package.get("pins", 0)),
        int(package.get("rows", 0)) * int(package.get("columns", 0)),
        int(package.get("leads", 0)),
        int(str(package.get("positions", "0..0")).split("..", 1)[0]),
    )


def bind(proposal: Proposal, datasheet: bytes) -> list[Issue]:
    if proposal.data["datasheet"]["sha256"] == hashlib.sha256(datasheet).hexdigest():
        return []
    return [
        issue("proposal.datasheet-mismatch", "proposal names another datasheet SHA-256", where=proposal.file)
    ]


def grid_positions(proposal: Proposal) -> tuple[set[str], set[str]]:
    package = proposal.data["package"]
    rows, columns = int(package.get("rows", 0)), int(package.get("columns", 0))
    labels = package.get("row_labels", [row_name(i) for i in range(rows)])
    grid = {f"{label}{c + 1}" for label in labels for c in range(columns)}
    depopulated = package.get("depopulated", [])
    if isinstance(depopulated, dict):
        r, c = (int(v) for v in cast(str, depopulated["center"]).split("x"))
        removed = {
            f"{labels[i]}{j + 1}"
            for i in range(max(0, (rows - r) // 2), min(len(labels), (rows + r) // 2))
            for j in range(max(0, (columns - c) // 2), min(columns, (columns + c) // 2))
        }
    else:
        removed = set(cast(list[str], depopulated))
    return grid, removed


def expected_numbers(proposal: Proposal) -> set[str]:
    package = proposal.data["package"]
    family = proposal.family
    if family == "grid":
        grid, removed = grid_positions(proposal)
        return grid - removed
    if family == "gullwing" and package.get("arrangement") == "sides":
        numbers = {str(n) for side in package.get("side", []) for n in side["numbers"]}
        if "tab" in package:
            numbers.add(str(package["tab"]["number"]))
        return numbers
    if family in {"chip", "molded"}:
        count = 2
    elif family == "header":
        count = int(package.get("rows", 0)) * int(package.get("columns", 0))
    elif family == "connector":
        count = int(str(package.get("positions", "0..0")).split("..", 1)[0])
    elif family == "to":
        count = int(package.get("leads", 0))
    else:
        count = int(package.get("pins", 0))
    numbers = {str(i + 1) for i in range(count)}
    if family == "nolead" and "ep" in package:
        numbers.add(str(package.get("ep_number", count + 1)))
    if family == "to" and "tab" in package and "number" in package["tab"]:
        numbers.add(str(package["tab"]["number"]))
    return numbers


def self_check(proposal: Proposal) -> list[Issue]:
    found = list(proposal.parse_issues)
    package = proposal.data["package"]
    extent = terminal_bound(proposal)
    if extent > MAX_PROPOSAL_PINS or len(proposal.pins) > MAX_PROPOSAL_PINS:
        return [
            issue(
                "proposal.range",
                f"proposal exceeds the {MAX_PROPOSAL_PINS}-terminal input bound",
                where="package",
            )
        ]
    numbers = [str(row["number"]) for row in proposal.pins]
    numbers += [str(number) for row in proposal.pins for number in row.get("stacked", [])]
    for number, count in Counter(numbers).items():
        if count > 1:
            found.append(
                issue("proposal.duplicate-pin", f"pin {number} appears {count} times", where=f"pin[{number}]")
            )
    if proposal.family not in FAMILIES:
        found.append(
            issue("proposal.unknown-family", f"unknown family {proposal.family!r}", where="package.family")
        )
    else:
        expected = expected_numbers(proposal)
        if len(numbers) != len(expected):
            found.append(
                issue(
                    "proposal.pin-count",
                    f"{len(numbers)} rows against {len(expected)} package pins",
                    where="pin",
                )
            )
        if proposal.family == "grid" and "pins" in package and int(package["pins"]) != len(expected):
            found.append(
                issue(
                    "proposal.pin-count",
                    f"{len(expected)} grid positions against {package['pins']} stated pins",
                    where="package.pins",
                )
            )
        for number in sorted(set(numbers) - expected):
            found.append(
                issue(
                    "proposal.pin-outside",
                    f"pin {number} is outside the package numbering",
                    where=f"pin[{number}]",
                )
            )
        if proposal.family == "grid":
            grid, removed = grid_positions(proposal)
            labels = package.get("row_labels", [])
            if len(labels) != package.get("rows") or len(set(labels)) != len(labels):
                found.append(
                    issue(
                        "proposal.pin-outside",
                        "row_labels must list each printed grid row exactly once",
                        where="package.row_labels",
                    )
                )
            for number in sorted(removed - grid):
                found.append(
                    issue(
                        "proposal.pin-outside",
                        f"depopulated ball {number} is outside the grid",
                        where="package.depopulated",
                    )
                )
            depopulated = package.get("depopulated", [])
            if isinstance(depopulated, dict):
                r, c = (int(v) for v in cast(str, depopulated["center"]).split("x"))
                if r > package["rows"] or c > package["columns"]:
                    found.append(
                        issue(
                            "proposal.pin-outside",
                            "excluded centre exceeds the grid",
                            where="package.depopulated",
                        )
                    )
            for number in sorted(removed & set(numbers)):
                found.append(
                    issue(
                        "proposal.depopulated-used",
                        f"depopulated ball {number} is also a pin",
                        where=f"pin[{number}]",
                    )
                )
        if (
            package.get("arrangement") == "quad"
            and int(package.get("pins", 0)) % 4
            and not package.get("side")
        ):
            found.append(
                issue(
                    "proposal.sides",
                    "four-sided pins do not divide by four and no side counts are given",
                    where="package.pins",
                )
            )
        if proposal.family == "connector":
            first, last = str(package.get("positions", "0..0")).split("..", 1)
            if first != last:
                found.append(
                    issue(
                        "proposal.range",
                        "one proposal describes one connector position count",
                        where="package.positions",
                    )
                )
    ep_name = str(package.get("ep_number", int(package.get("pins", 0)) + 1 if "ep" in package else ""))
    ep_rows = [
        row
        for row in proposal.pins
        if str(row["name"]).upper() in {"EP", "PAD", "THERMAL"} or ep_name and row["number"] == ep_name
    ]
    if bool(package.get("ep")) != bool(ep_rows):
        found.append(
            issue(
                "proposal.exposed-pad",
                "exposed-pad declaration and named pin rows disagree",
                where="package.ep",
            )
        )
    for name in ("span", "span_x", "span_y"):
        span = proposal.quantities.get("package." + name)
        body = proposal.quantities.get("package.body." + ("length" if name == "span_y" else "width"))
        if (
            span
            and body
            and span.min is not None
            and body.max is not None
            and proposal.family in {"gullwing", "to", "dip", "molded"}
            and span.min <= body.max
        ):
            found.append(
                issue("proposal.range", "span minimum must exceed the body maximum", where="package." + name)
            )
    ratings = proposal.data.get("ratings", {})
    for key, row in ratings.items():
        if {"min", "max"} <= row.keys() and micro_units(RATING_UNITS[key], row["min"]) > micro_units(
            RATING_UNITS[key], row["max"]
        ):
            found.append(issue("proposal.range", "rating minimum exceeds maximum", where="ratings." + key))
    if "vin" in ratings and "voltage" in ratings:
        found.append(
            issue(
                "proposal.range",
                "vin and voltage both name the same device voltage rating; supply one",
                where="ratings",
            )
        )
    for name in proposal.uncited:
        found.append(issue("proposal.uncited", "row or parameter group has no citation", where=name))
    for row in proposal.data.get("doubt", []):
        found.append(issue("proposal.doubt", str(row["reason"]), where=str(row["field"])))
    return found


def normalized_pin(row: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "group": "",
        "side": "",
        "unit": None,
        "bus": "",
        "shape": "line",
        "hidden": False,
        "stacked": [],
        "alternates": [],
    }
    return {**defaults, **{k: v for k, v in row.items() if k != "cite"}}
