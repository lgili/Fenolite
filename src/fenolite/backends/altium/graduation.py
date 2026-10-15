# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Installed graduation decisions, checked against repository proofs by the generator."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from fenolite.backends.base import MatrixRow
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-ACC-KIT",))
SNAPSHOT = Path(__file__).with_name("graduation.json")


def decisions(
    rows: Sequence[MatrixRow],
    readbacks: Mapping[str, str],
) -> tuple[tuple[MatrixRow, ...], dict[str, tuple[str, ...]]]:
    """Apply packaged decisions; changed declarations remain experimental."""
    data: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if data.get("schema") != "fenolite.altium-graduation.v0" or not isinstance(data.get("kinds"), dict):
        raise ValueError("invalid Altium graduation snapshot; regenerate tools/gen_altium_graduation.py")
    result: list[MatrixRow] = []
    missing: dict[str, tuple[str, ...]] = {}
    for row in rows:
        if row.write is None:
            result.append(row)
            continue
        value = data["kinds"].get(row.kind)
        entry = cast(dict[str, Any], value) if isinstance(value, dict) else None
        if (
            not isinstance(entry, dict)
            or entry.get("hypotheses") != sorted(row.write.hypotheses)
            or entry.get("write_level") != row.write.level.value
            or entry.get("own_readback") != readbacks.get(row.kind)
        ):
            reasons = ("graduation snapshot does not match write declarations",)
        else:
            values: object = entry.get("missing")
            if not isinstance(values, list) or any(
                not isinstance(value, str) for value in cast(list[object], values)
            ):
                raise ValueError(f"invalid graduation conditions for {row.kind}")
            reasons = tuple(cast(list[str], values))
        missing[row.kind] = reasons
        flags = tuple(flag for flag in row.experimental if flag != "write")
        write = Evidence.combine(row.write, Evidence(Level.INFERRED)) if reasons else row.write
        result.append(replace(row, write=write, experimental=(*flags, "write") if reasons else flags))
    return tuple(result), missing


__all__ = ["EVIDENCE", "SNAPSHOT", "decisions"]
