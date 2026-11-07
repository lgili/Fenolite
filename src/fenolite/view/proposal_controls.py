# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Closed regeneration metadata for viewer decisions; never consume command strings (c0369)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fenolite.core.units import parse_length

SCHEMA = "fenolite.proposal_controls.v0"
FIELDS = frozenset(
    {
        "schema",
        "router_options",
        "external_routers",
        "nets",
        "kinds",
        "groups",
        "candidate_limit",
        "requirements",
        "timeout",
        "gate",
        "portable",
    }
)
INTEGER = {
    "candidates",
    "search-max-states",
    "search-max-vias",
    "negotiate-max-rounds",
    "rounds",
    "gate-vias",
    "kelvin-vias",
}
LENGTHS = {"search-grid", "max-length", "keep-away"}
ENUMS = {"search": {"off", "fallback", "only"}, "negotiate": {"on", "off"}, "z-shapes": {"on", "off"}}


@dataclass(frozen=True, slots=True)
class ControlError:
    reason: str


def _texts(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    rows = cast("list[Any]", value)
    if len(rows) > 64 or any(
        not isinstance(v, str) or not 0 < len(v) <= 256 or not v.isprintable() for v in rows
    ):
        return None
    return cast("list[str]", rows)


def words(raw: object, root: Path) -> tuple[str, ...] | ControlError:
    """Only individual, validated arguments of fixed octilinear proposal regeneration."""
    if raw is None:
        return ()  # legacy fixed-pattern scene; callers guard unsupported families separately
    if not isinstance(raw, dict):
        return ControlError("proposal controls must be a structured object")
    data = cast("dict[str, Any]", raw)
    if set(data) - FIELDS or data.get("schema") != SCHEMA:
        return ControlError("unknown proposal control schema or field")
    if data.get("portable") is not True:
        return ControlError(
            "proposal tool paths cannot be replayed from the viewer; use environment configuration"
        )
    result: list[str] = []
    for field, flag in (
        ("nets", "nets"),
        ("kinds", "kind"),
        ("groups", "group"),
        ("external_routers", "propose-with"),
    ):
        rows = _texts(data.get(field, []))
        if rows is None:
            return ControlError(f"invalid proposal {field}")
        if field == "kinds" and any(
            v not in {"connection", "group", "fanout", "join", "role-net"} for v in rows
        ):
            return ControlError("unknown proposal subject kind")
        if field == "external_routers" and any(v not in {"freerouting", "kicadroutingtools"} for v in rows):
            return ControlError("unknown local candidate adapter")
        result += [f"--{flag}={value}" for value in rows]
    options = _texts(data.get("router_options", []))
    if options is None:
        return ControlError("invalid proposal router options")
    for option in options:
        key, separator, value = option.partition("=")
        valid = False
        if separator and key in INTEGER:
            valid = value.isascii() and value.isdigit() and len(value) <= 12
        elif separator and key in ENUMS:
            valid = value in ENUMS[key]
        elif separator and key in LENGTHS:
            try:
                valid = (key == "keep-away" and value == "clearance") or parse_length(
                    value, default_unit="mm"
                ) >= 0
            except ValueError:
                valid = False
        if not valid:
            return ControlError(f"unsupported proposal router option {key!r}")
        result.append(f"--router-option={option}")
    limit = data.get("candidate_limit")
    if limit is not None:
        if type(limit) is not int or not 1 <= limit <= 8:
            return ControlError("proposal candidate limit must be an integer from 1 to 8")
        result.append(f"--candidates={limit}")
    budget = data.get("timeout")
    if budget is not None:
        try:
            valid_budget = type(budget) in (int, float) and math.isfinite(budget) and budget > 0
        except OverflowError:
            valid_budget = False
        if not valid_budget:
            return ControlError("invalid proposal timeout")
        result.append(f"--timeout={budget}")
    requirements = data.get("requirements")
    if requirements is not None:
        if not isinstance(requirements, str) or not requirements or not requirements.isprintable():
            return ControlError("invalid proposal requirements path")
        try:
            relative = (root / requirements).resolve().relative_to(root.resolve())
        except (ValueError, OSError):
            return ControlError("proposal requirements leave the project root")
        if not (root / relative).is_file():
            return ControlError("proposal requirements file is missing")
        result.append(f"--requirements={relative.as_posix()}")
    gate = data.get("gate")
    if gate is not None:
        if gate != "drc":
            return ControlError("unknown proposal native gate")
        result.append("--gate=drc")
    return tuple(result)
