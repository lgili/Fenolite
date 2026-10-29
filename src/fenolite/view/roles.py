# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The data of the Net Roles workspace of the viewer (change c0245, capability roles-workspace).

``payload(reply, ...)`` turns the reply of ``fenolite roles PATH --check`` into ``fenolite.view_roles.v0``:
the reply's own roles, groups, part classes, measures, limits and findings, unchanged, so that the numbers on
the screen are the numbers an agent reads; the locked copper of the board, by the labels the scene gives its
tracks, arcs and vias; and the counts that ``fenolite view --workspace roles --json`` replies with. The page
joins it to the scene: a net to its copper, a group to the polygon of its pads, a finding to the place it
names. ``fenolite view`` runs the command in its own process and read-only; this module imports neither the
command nor the roles package (the import rules of ``tests/unit/test_import_graph.py``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

SCHEMA = "fenolite.view_roles.v0"
CORRIDOR_PREFIX = "role.corridor."
"""The name prefix of the corridors of c0243 and c0244 (``role.corridor.<group>.<net>``, task 0.1)."""
STATES = ("confirmed", "declared", "inferred")
SEVERITIES = ("error", "warning", "info")


def state_of(row: Mapping[str, Any]) -> str:
    """The state a role row shows: ``declared`` by a script, ``confirmed`` by a person, or ``inferred``."""
    source = str(row.get("source", "inferred"))
    return source if source in STATES else "inferred"


def payload(
    reply: Mapping[str, Any],
    *,
    document: str,
    sha256: str,
    locked: Mapping[str, Iterable[int]] | None = None,
) -> dict[str, Any]:
    """The data of the workspace for the board ``document`` (its SHA-256 ``sha256``) from a ``roles --check``
    envelope ``reply``; ``locked`` maps ``tracks``, ``arcs`` and ``vias`` to the 1-based numbers of the
    locked items, which the scene labels ``track N``, ``arc N`` and ``via N``."""
    result = cast("Mapping[str, Any]", reply.get("result") or {})
    roles = [
        dict(cast("Mapping[str, Any]", row)) | {"state": state_of(cast("Mapping[str, Any]", row))}
        for row in result.get("roles", [])
    ]
    issues = [dict(cast("Mapping[str, Any]", issue)) for issue in reply.get("issues", [])]
    states = {state: sum(1 for row in roles if row["state"] == state) for state in STATES}
    severities = {sev: sum(1 for issue in issues if issue.get("severity") == sev) for sev in SEVERITIES}
    evidence = cast("Mapping[str, Any]", reply.get("evidence") or {})
    locked_items = {kind: sorted(int(n) for n in numbers) for kind, numbers in (locked or {}).items()}
    return {
        "schema": SCHEMA,
        "document": document,
        "sha256": sha256,
        "evidence": {
            "level": evidence.get("level", "INFERRED"),
            "hypotheses": list(evidence.get("hypotheses", [])),
        },
        "roles": roles,
        "loops": list(result.get("loops", [])),
        "kelvins": list(result.get("kelvins", [])),
        "gates": list(result.get("gates", [])),
        "classes": dict(result.get("classes", {})),
        "measures": list(result.get("measures", [])),
        "limits": list(result.get("limits", [])),
        "summary": dict(result.get("summary", {})),
        "store": dict(result.get("store", {})),
        "issues": issues,
        "locked": locked_items,
        "counts": {"roles": states, "findings": severities},
    }


def summary(data: Mapping[str, Any]) -> dict[str, Any]:
    """What ``fenolite view --workspace roles --json`` replies with: the counts of the workspace."""
    counts = cast("Mapping[str, Any]", data.get("counts", {}))
    return {
        "document": data.get("document"),
        "counts": dict(cast("Mapping[str, int]", counts.get("roles", {}))),
        "findings": dict(cast("Mapping[str, int]", counts.get("findings", {}))),
        "groups": len(data.get("loops", [])) + len(data.get("kelvins", [])) + len(data.get("gates", [])),
        "locked": sum(len(v) for v in cast("Mapping[str, list[int]]", data.get("locked", {})).values()),
    }


__all__ = ["CORRIDOR_PREFIX", "SCHEMA", "payload", "state_of", "summary"]
