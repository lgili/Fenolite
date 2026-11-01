# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The verification matrix of ``fenolite check --matrix`` (change c0274; capability cli-contract,
"Verification matrix of check"; ``docs/contracts.md``, "The verification matrix"; hypothesis
``H-G-CIRCUIT-ROW-IDS``).

The matrix lists the requirement rows of the stages ``circuit.rules`` and ``roles.rules`` that ran, sorted by
their stable id, each with what it judged, its status (``waived`` when a waiver accepted its finding), its
evidence, its decidable stage and its digest, and a receipt of the inputs: the SHA-256 of the canonical
``.fenolite/`` texts and of the sorted device digests, so a matrix pasted into a review names exactly what it
judged. The matrix is a reply of ``check``: nothing is written.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, cast

from fenolite import __version__
from fenolite.checks.circuit.table import device_digest
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.model.library import DeviceDef

STAGES: tuple[str, ...] = ("circuit.rules", "roles.rules")
"""The stages whose requirement rows the matrix lists."""
COLUMNS: tuple[str, ...] = ("id", "check", "value", "limit", "source", "status")
"""The columns of the matrix in a terminal."""
HYPOTHESIS = "H-G-CIRCUIT-ROW-IDS"


def model_digest(model: Design | None) -> str | None:
    """The SHA-256 of the canonical ``.fenolite/`` texts of ``model``, each as ``<file name>\\n<text>`` in the
    order of the layer files; ``None`` without a model (a native project)."""
    if model is None:
        return None
    digest = hashlib.sha256()
    for name, text in canonical.dump_texts(model).items():
        digest.update(f"{name}\n{text}".encode())
    return digest.hexdigest()


def devices_digest(devices: Mapping[str, DeviceDef] | None) -> str:
    """The SHA-256 of the sorted digests of the device records judged, one per line."""
    found = sorted(device_digest(device) for device in (devices or {}).values())
    return hashlib.sha256("\n".join(found).encode()).hexdigest()


def _text(side: object) -> str:
    return str(cast(Mapping[str, Any], side).get("text", "")) if isinstance(side, Mapping) else ""


def _origin(value: object) -> str | None:
    if not isinstance(value, Mapping):
        return None
    origin = cast(Mapping[str, Any], value).get("origin")
    if not isinstance(origin, Mapping):
        return None
    found = cast(Mapping[str, Any], origin)
    if found.get("kind") != "propagated":
        return str(found.get("kind"))
    return f"propagated via {', '.join(str(r) for r in found.get('via', ()))} from {found.get('from')}"


def matrix_row(row: Mapping[str, Any]) -> dict[str, object]:
    """One row of the matrix from a requirement row in JSON (``RequirementRow.to_json``)."""
    limit = cast(Mapping[str, Any], row.get("limit") or {})
    waiver = row.get("waiver")
    return {
        "id": row["id"],
        "check": row["check"],
        "value": _text(row.get("value")),
        "limit": _text(limit),
        "source": limit.get("source"),
        "origin": _origin(row.get("value")),
        "status": "waived" if waiver else row["status"],
        "evidence": limit.get("evidence", ""),
        "decidable": row.get("decidable", "build"),
        "digest": row.get("digest"),
        "waiver": waiver,
    }


def matrix(
    stages: Iterable[Mapping[str, Any]], *, model: Design | None, devices: Mapping[str, DeviceDef] | None
) -> dict[str, object]:
    """``result.matrix``: the rows of the stages of ``STAGES`` that ran (each a stage's JSON), sorted by id
    (a repeated id keeps its first row), and the receipt."""
    rows: dict[str, dict[str, object]] = {}
    ran: list[str] = []
    for stage in stages:
        if stage.get("name") not in STAGES or stage.get("status") == "skipped":
            continue
        summary = cast(Mapping[str, Any], stage.get("summary") or {})
        table = summary.get("requirements")
        if not isinstance(table, list):
            continue
        ran.append(str(stage["name"]))
        for row in cast(list[Mapping[str, Any]], table):
            rows.setdefault(str(row["id"]), matrix_row(row))
    receipt = {
        "fenolite": __version__,
        "model_sha256": model_digest(model),
        "devices_sha256": devices_digest(devices),
        "stages": ran,
    }
    return {"receipt": receipt, "rows": [rows[key] for key in sorted(rows)]}


def matrix_text(rows: Sequence[Mapping[str, object]]) -> str:
    """The rows as a table for a terminal: the columns of ``COLUMNS``, one line per row."""
    table = [list(COLUMNS)] + [[str(row.get(column) or "") for column in COLUMNS] for row in rows]
    widths = [max(len(line[i]) for line in table) for i in range(len(COLUMNS))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip() for line in table]
    return "\n".join(lines) + "\n"


__all__ = [
    "COLUMNS",
    "HYPOTHESIS",
    "STAGES",
    "devices_digest",
    "matrix",
    "matrix_row",
    "matrix_text",
    "model_digest",
]
