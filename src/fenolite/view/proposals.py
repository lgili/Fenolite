# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Route proposals joined to the scene of their board (capability board-viewer, "Route proposals on a board";
change c0280; ``docs/viewer.md``, "Route proposals").

``overlay(reply, scene)`` turns the reply of ``fenolite route BOARD --router octilinear --propose`` into
``scene.proposals``, ``fenolite.view_proposals.v0``: per proposal its id, kind, net, subject, box, reason and
alternatives; per candidate its id, source, polylines and via points per layer in scene units (whole
micrometres of the board frame, as ``view.scene``) and its facts unchanged; and the record's locked decisions.
A value the reply does not hold is left out, and nothing like a score is added: the numbers on the page are
the reply's. ``view`` imports neither the command nor the routing package: ``cmd_view`` runs the command and
passes the reply in. Standard library only.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from fenolite.core.errors import FormatError

SCHEMA = "fenolite.view_proposals.v0"
BOX_MARGIN_UM = 2_000
"""How far a proposal's box reaches beyond its ends and candidates, in micrometres (decision 6's 2 mm)."""

Json = dict[str, Any]


def read_reply(data: Any, *, name: str = "") -> Json:
    """The ``route --propose`` reply ``data`` (a parsed JSON envelope); ``FormatError`` when it is not one."""
    what = name or "the reply"
    if not isinstance(data, dict):
        raise FormatError(f"{what} is not a fenolite route --propose reply", file=name)
    reply = cast("Json", data)
    result = reply.get("result")
    if (
        reply.get("command") != "route"
        or not isinstance(result, dict)
        or cast("Json", result).get("mode") != "propose"
    ):
        found = reply.get("command")
        said = f" (it is a {found} reply)" if isinstance(found, str) and found != "route" else ""
        raise FormatError(f"{what} is not a fenolite route --propose reply{said}", file=name)
    return reply


def _um(value: Any) -> int:
    return round(int(value) / 1000)


def _point(raw: Any) -> list[int] | None:
    if isinstance(raw, list) and len(cast("list[Any]", raw)) == 2:
        x, y = cast("list[Any]", raw)
        if isinstance(x, int) and isinstance(y, int):
            return [_um(x), _um(y)]
    return None


def _candidate(raw: Mapping[str, Any]) -> tuple[Json, list[list[int]]]:
    polylines: list[Json] = []
    vias: list[Json] = []
    points: list[list[int]] = []
    for item in cast("list[Any]", raw.get("geometry") or []):
        if not isinstance(item, dict):
            continue
        part = cast("Json", item)
        if part.get("kind") == "track":
            line = [p for p in (_point(q) for q in cast("list[Any]", part.get("points") or [])) if p]
            polylines.append({"layer": part.get("layer"), "width": _um(part.get("width", 0)), "points": line})
            points += line
        elif part.get("kind") == "via":
            at = _point(part.get("at"))
            if at is None:
                continue
            vias.append(
                {"at": at, "diameter": _um(part.get("diameter", 0)), "layers": list(part.get("layers") or [])}
            )
            points.append(at)
    entry: Json = {
        "id": raw.get("id"),
        "source": raw.get("source"),
        "relaxed": list(cast("list[Any]", raw.get("relaxed") or [])),
        "polylines": polylines,
        "vias": vias,
        "facts": raw.get("facts"),
        "rejected": bool(raw.get("rejected")),
    }
    return {key: value for key, value in entry.items() if value is not None}, points


def _box(points: list[list[int]]) -> list[int] | None:
    if not points:
        return None
    return [
        min(p[0] for p in points) - BOX_MARGIN_UM,
        min(p[1] for p in points) - BOX_MARGIN_UM,
        max(p[0] for p in points) + BOX_MARGIN_UM,
        max(p[1] for p in points) + BOX_MARGIN_UM,
    ]


def overlay(reply: Mapping[str, Any], scene: Mapping[str, Any]) -> Json:
    """``scene.proposals`` for the ``route --propose`` reply on the board ``scene`` (module docstring)."""
    del scene  # the reply's positions are in the board frame the scene is drawn in
    result = cast("Json", reply.get("result") or {})
    proposals: list[Json] = []
    count = 0
    for raw in cast("list[Any]", result.get("proposals") or []):
        if not isinstance(raw, dict):
            continue
        proposal = cast("Json", raw)
        ends = [cast("Json", e) for e in cast("list[Any]", proposal.get("ends") or []) if isinstance(e, dict)]
        points = [p for p in (_point(e.get("at")) for e in ends) if p]
        candidates: list[Json] = []
        for item in cast("list[Any]", proposal.get("candidates") or []):
            if isinstance(item, dict):
                entry, drawn = _candidate(cast("Json", item))
                candidates.append(entry)
                points += drawn
        count += len(candidates)
        entry = {
            "id": proposal.get("id"),
            "kind": proposal.get("kind"),
            "net": proposal.get("net"),
            "subject": proposal.get("subject"),
            "box": _box(points),
            "reason": proposal.get("reason"),
            "alternatives": proposal.get("alternatives"),
            "region": proposal.get("region"),
            "candidates": candidates,
        }
        proposals.append({key: value for key, value in entry.items() if value is not None})
    evidence = cast("Json", reply.get("evidence") or {})
    source = cast("Json", reply.get("input") or {})
    data: Json = {
        "schema": SCHEMA,
        "document": source.get("path"),
        "sha256": source.get("sha256"),
        "order": result.get("order"),
        "evidence": {
            "level": str(evidence.get("level") or "UNVERIFIED"),
            "hypotheses": list(cast("list[str]", evidence.get("hypotheses") or [])),
        },
        "proposals": proposals,
        "rejected": list(cast("list[Any]", result.get("rejected") or [])),
        "locked": list(cast("list[Any]", result.get("locked") or [])),
        "counts": {"proposals": len(proposals), "candidates": count},
    }
    return {key: value for key, value in data.items() if value is not None}


def ids_of(data: Mapping[str, Any] | None) -> tuple[frozenset[str], frozenset[str]]:
    """The candidate ids and the proposal ids of ``scene.proposals`` (the route actions of the page)."""
    if not data:
        return frozenset(), frozenset()
    proposals = [
        cast("Json", p) for p in cast("list[Any]", data.get("proposals") or []) if isinstance(p, dict)
    ]
    candidates = {
        str(cast("Json", c).get("id"))
        for p in proposals
        for c in cast("list[Any]", p.get("candidates") or [])
        if isinstance(c, dict) and cast("Json", c).get("id")
    }
    return frozenset(candidates), frozenset(str(p["id"]) for p in proposals if p.get("id"))


def summary(data: Mapping[str, Any]) -> Json:
    """``result.proposals`` of ``fenolite view``: the counts and the evidence of the reply shown."""
    counts = cast("Json", data.get("counts") or {})
    return {
        "document": data.get("document"),
        "proposals": counts.get("proposals", 0),
        "candidates": counts.get("candidates", 0),
        "evidence": cast("Json", data.get("evidence") or {}).get("level"),
    }


__all__ = ["SCHEMA", "ids_of", "overlay", "read_reply", "summary"]
