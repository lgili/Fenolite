# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The net roles of a board joined to its scene (capability board-viewer, "Role data on a board"; change
c0305).

``overlay(reply, scene)`` turns the reply of ``fenolite roles PATH --check`` (change c0222) into
``scene.roles``, ``fenolite.view_roles.v0``: the reply's role rows unchanged, each with its state and the
index of its net in the scene; the hot loops, gate loops and Kelvin pairs with the points of their pads and
the loop measures the reply holds; and the role findings placed on the board by ``check_overlay``, the group
names standing for their pads. The numbers on the page are the numbers an agent reads. The schema name,
``state_of`` and the idea of joining the reply to the scene come from the role view of
c0245-engineering-viewer (another session, superseded by the maintainer's decision of 2026-10-29 except for
that view). ``view`` imports neither the
command nor the roles package: ``cmd_view`` runs the command and passes the reply in. Standard library and
``fenolite.model.rules`` only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.model.rules import ROLE_KINDS
from fenolite.view import check_overlay

SCHEMA = "fenolite.view_roles.v0"
STATES = ("confirmed", "declared", "inferred")
SEVERITIES = ("error", "warning", "info")
GROUP_KEYS = (("loops", "hot"), ("gates", "gate"), ("kelvins", "kelvin"))
"""The group lists of a roles reply and the type the page gives each."""
LOOP_VALUES = ("area_nm2", "bound_nm2", "ratio_permille")
"""The values of a loop measure a group carries to the page."""

Json = dict[str, Any]


def read_reply(data: Any, *, name: str = "") -> Json:
    """The ``roles`` reply ``data`` (a parsed JSON envelope); ``FormatError`` when it is not one: another
    command's reply, or the role document itself."""
    what = name or "the reply"
    if not isinstance(data, dict):
        raise FormatError(f"{what} is not a fenolite roles reply", file=name)
    reply = cast("Json", data)
    result = reply.get("result")
    if reply.get("command") != "roles" or not isinstance(result, dict) or "roles" not in result:
        found = reply.get("command")
        said = f" (it is a {found} reply)" if isinstance(found, str) and found != "roles" else ""
        if not said and "schema" in reply:
            said = " (it looks like a role document: pass the reply of fenolite roles PATH --check --json)"
        raise FormatError(f"{what} is not a fenolite roles reply{said}", file=name)
    return reply


def state_of(row: Mapping[str, Any]) -> str:
    """The state a role row shows: ``declared`` by a script, ``confirmed`` by a person, or ``inferred``."""
    source = str(row.get("source", "inferred"))
    return source if source in STATES else "inferred"


def _pads_of(kind: str, group: Mapping[str, Any]) -> list[str]:
    if kind == "gate":
        return [str(group[k]) for k in ("drive", "gate", "source", "ret") if group.get(k)]
    if kind == "kelvin":
        return [str(p) for p in (*group.get("element", []), *group.get("receiver", []))]
    return [str(p) for p in group.get("pads", [])]


def groups_of(reply: Mapping[str, Any]) -> list[Json]:
    """The groups of a roles reply in one list: ``name``, ``type`` (``hot``, ``gate``, ``kelvin``), ``pads``
    and the reply's own keys."""
    result = cast("Json", reply.get("result") or {})
    out: list[Json] = []
    for key, kind in GROUP_KEYS:
        for raw in cast("list[Any]", result.get(key) or []):
            if isinstance(raw, dict):
                group = cast("Json", raw)
                out.append(
                    {**group, "name": str(group.get("name", "")), "type": kind, "pads": _pads_of(kind, group)}
                )
    return out


def overlay(reply: Mapping[str, Any], scene: Mapping[str, Any]) -> Json:
    """``scene.roles`` for the roles ``reply`` on the board ``scene`` (module docstring)."""
    result = cast("Json", reply.get("result") or {})
    nets = [
        str(cast("Json", n).get("name", "")) if isinstance(n, dict) else str(n)
        for n in cast("list[Any]", scene.get("nets", []))
    ]
    index = {name: k for k, name in enumerate(nets) if name}
    pads = {
        str(p.get("label")): (p["x"], p["y"])
        for p in cast("list[Json]", scene.get("pads", []))
        if p.get("label") is not None and p.get("x") is not None and p.get("y") is not None
    }
    roles: list[Json] = []
    for raw in cast("list[Any]", result.get("roles") or []):
        if isinstance(raw, dict):
            row = cast("Json", raw)
            roles.append({**row, "state": state_of(row), "net_index": index.get(str(row.get("net")), -1)})
    loops: dict[str, Json] = {}
    for raw in cast("list[Any]", result.get("measures") or []):
        measure = cast("Json", raw) if isinstance(raw, dict) else {}
        if measure.get("kind") == "loop" and isinstance(measure.get("values"), dict):
            loops[str(measure.get("subject"))] = cast("Json", measure["values"])
    groups: list[Json] = []
    notes: list[str] = []
    for group in groups_of(reply):
        points = [list(pads[label]) for label in group["pads"] if label in pads]
        missing = [label for label in group["pads"] if label not in pads]
        entry: Json = {
            "name": group["name"],
            "type": group["type"],
            "origin": group.get("origin"),
            "rule": group.get("rule"),
            "confidence": group.get("confidence"),
            "pads": group["pads"],
            "points": points,
        }
        measured = loops.get(group["name"])
        if measured is not None:
            entry |= {key: measured[key] for key in LOOP_VALUES if measured.get(key) is not None}
            if measured.get("net"):
                entry["net"] = measured["net"]
        if missing:
            notes.append(
                f"the group {group['name']} names pads this board does not hold: {', '.join(missing)}"
            )
        groups.append(entry)
    aliases = {g["name"]: g["pads"] for g in groups if g["name"]}
    listed: Json = {
        "command": "check",
        "issues": list(cast("list[Any]", reply.get("issues") or [])),
        "result": {"stages": []},
        "evidence": reply.get("evidence"),
    }
    placed = check_overlay.overlay(listed, dict(scene), aliases=aliases)
    findings = [f | {"stage": "roles.rules"} for f in placed["findings"]]
    evidence = cast("Json", reply.get("evidence") or {})
    kinds = {kind: n for kind in ROLE_KINDS if (n := sum(1 for r in roles if r.get("kind") == kind))}
    source = cast("Json", reply.get("input") or {})
    return {
        "schema": SCHEMA,
        "document": source.get("path"),
        "sha256": source.get("sha256"),
        "evidence": {
            "level": str(evidence.get("level") or "INFERRED"),
            "hypotheses": list(cast("list[str]", evidence.get("hypotheses") or [])),
        },
        "roles": roles,
        "kinds": kinds,
        "groups": groups,
        "classes": dict(cast("Json", result.get("classes") or {})),
        "measures": list(cast("list[Any]", result.get("measures") or [])),
        "summary": dict(cast("Json", result.get("summary") or {})),
        "store": dict(cast("Json", result.get("store") or {})),
        "findings": findings,
        "counts": {
            "roles": {state: sum(1 for r in roles if r["state"] == state) for state in STATES},
            "findings": {sev: sum(1 for f in findings if f["severity"] == sev) for sev in SEVERITIES},
        },
        "notes": notes + [n for n in placed["notes"] if "no position" in n],
    }


def aliases_of(data: Mapping[str, Any] | None) -> dict[str, list[str]]:
    """The group names of ``scene.roles`` and the pads each stands for (``check_overlay.overlay``)."""
    if not data:
        return {}
    return {
        str(g["name"]): list(g["pads"]) for g in cast("list[Json]", data.get("groups", [])) if g.get("name")
    }


def summary(data: Mapping[str, Any]) -> Json:
    """``result.roles`` of ``fenolite view``: the roles by state, the findings by severity, the groups."""
    counts = cast("Json", data.get("counts") or {})
    return {
        "document": data.get("document"),
        "roles": dict(cast("Json", counts.get("roles") or {})),
        "findings": dict(cast("Json", counts.get("findings") or {})),
        "groups": len(cast("list[Any]", data.get("groups") or [])),
        "evidence": cast("Json", data.get("evidence") or {}).get("level"),
    }


__all__ = ["SCHEMA", "aliases_of", "groups_of", "overlay", "read_reply", "state_of", "summary"]
