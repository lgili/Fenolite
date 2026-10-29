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

import re
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


WRITE_FLAGS: dict[str, str] = {
    "--accept": "names",
    "--accept-all": "",
    "--min-confidence": "confidence",
    "--set": "set",
    "--reject": "names",
    "--forget": "names",
    "--current": "current",
    "--accept-group": "names",
    "--reject-group": "names",
    "--forget-group": "names",
}
"""The options of ``fenolite roles`` a served page may ask for (decision 11): the role writes only."""
_NAME = r"[^\s,=:/\\]+"
_VALUES = {
    "names": re.compile(rf"{_NAME}(?:,{_NAME})*"),
    "confidence": re.compile(r"high|medium"),
    "set": re.compile(rf"{_NAME}=[a-z_]+(?::[a-z_]+=\d+)*"),
    "current": re.compile(rf"{_NAME}=\d+(?:\.\d+)?"),
}


def write_argv(argv: object) -> list[str]:
    """The options of a role write a page sent, checked against ``WRITE_FLAGS``: no path, no other option.
    Raises ``ValueError``."""
    if not isinstance(argv, list) or not argv or len(cast("list[object]", argv)) > 64:
        raise ValueError("a role write is a short list of options")
    items = cast("list[object]", argv)
    out: list[str] = []
    k = 0
    while k < len(items):
        flag = items[k]
        if not isinstance(flag, str) or flag not in WRITE_FLAGS:
            raise ValueError(f"{flag!r} is not an option of a role write")
        out.append(flag)
        kind = WRITE_FLAGS[flag]
        k += 1
        if kind:
            value = items[k] if k < len(items) else None
            if not isinstance(value, str) or not _VALUES[kind].fullmatch(value):
                raise ValueError(f"{flag}: {value!r} is not a value it takes")
            out.append(value)
            k += 1
    return out


_LEVEL = {"high": 2, "medium": 1, "low": 0, "": 0}


def inverse(data: Mapping[str, Any], argv: list[str]) -> list[list[str]]:
    """The exact inverse of the role write ``argv`` on the stored roles that ``data`` (the workspace's data
    before the write) shows, as at most two steps of options, applied in order (decision 11):

    - a net that was inferred is forgotten; a net confirmed from an inference is forgotten, then accepted
      again (with its current); a net set by hand is set back (with its working voltage, sensitivity and
      current); a declared net is never written;
    - a group that was inferred is forgotten; a confirmed group is forgotten, then accepted again; a rejected
      group is rejected again.
    """
    flags: dict[str, list[str]] = {}
    k = 0
    while k < len(argv):
        flag = argv[k]
        if WRITE_FLAGS.get(flag):
            flags.setdefault(flag, []).append(argv[k + 1])
            k += 2
        else:
            flags.setdefault(flag, []).append("")
            k += 1

    def names(flag: str) -> list[str]:
        return [n for value in flags.get(flag, []) for n in value.split(",") if n]

    def keyed(flag: str) -> list[str]:
        return [value.split("=", 1)[0] for value in flags.get(flag, [])]

    roles = {str(r["net"]): r for r in cast("list[Mapping[str, Any]]", data.get("roles", []))}
    groups = {
        str(g["name"]): str(g.get("origin", "inferred"))
        for key in ("loops", "kelvins", "gates")
        for g in cast("list[Mapping[str, Any]]", data.get(key, []))
    }
    floor = _LEVEL[(flags.get("--min-confidence") or ["low"])[0]]
    nets = [*names("--accept"), *names("--reject"), *names("--forget"), *keyed("--set"), *keyed("--current")]
    touched_groups = [*names("--accept-group"), *names("--reject-group"), *names("--forget-group")]
    if "--accept-all" in flags:
        nets += [
            n
            for n, r in roles.items()
            if r.get("state") == "inferred" and _LEVEL[str(r.get("confidence", ""))] >= floor
        ]
        for key in ("loops", "kelvins", "gates"):
            for g in cast("list[Mapping[str, Any]]", data.get(key, [])):
                if g.get("origin") == "inferred" and _LEVEL[str(g.get("confidence", ""))] >= floor:
                    touched_groups.append(str(g["name"]))
    forget: list[str] = []
    forget_groups: list[str] = []
    again: list[str] = []
    for net in dict.fromkeys(nets):
        row = roles.get(net)
        if row is None or row.get("state") == "declared":
            continue
        if row.get("state") == "inferred" or row.get("rule"):
            forget.append(net)
        if row.get("state") == "confirmed":
            if row.get("rule"):
                again += ["--accept", net]
            else:
                extra = [f"working_mv={row['working_mv']}"] if row.get("working_mv") else []
                extra += ["sensitive=1"] if row.get("sensitive") else []
                again += ["--set", ":".join([f"{net}={row['kind']}", *extra])]
            if row.get("milliamps"):
                again += ["--current", f"{net}={int(row['milliamps']) / 1000:g}"]
    for name in dict.fromkeys(touched_groups):
        origin = groups.get(name, "rejected")
        if origin in ("inferred", "confirmed"):
            forget_groups.append(name)
        if origin == "confirmed":
            again += ["--accept-group", name]
        elif origin == "rejected":
            again += ["--reject-group", name]
    first = (["--forget", ",".join(forget)] if forget else []) + (
        ["--forget-group", ",".join(forget_groups)] if forget_groups else []
    )
    return [step for step in (first, again) if step]


__all__ = [
    "CORRIDOR_PREFIX",
    "SCHEMA",
    "WRITE_FLAGS",
    "inverse",
    "payload",
    "state_of",
    "summary",
    "write_argv",
]
