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

import copy
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any, TypedDict, cast

from fenolite.core.errors import FormatError

SCHEMA = "fenolite.view_proposals.v0"
BOX_MARGIN_UM = 2_000
"""How far a proposal's box reaches beyond its ends and candidates, in micrometres (decision 6's 2 mm)."""

Json = dict[str, Any]


class SceneLine(TypedDict):
    layer: str
    width: int
    points: list[list[int]]


class SceneVia(TypedDict, total=False):
    at: list[int]
    diameter: int
    drill: int
    layers: list[str]


class SceneEnd(TypedDict, total=False):
    kind: str
    name: str
    at: list[int]
    layers: list[str]


class SceneCandidate(TypedDict, total=False):
    id: str
    source: str
    relaxed: list[str]
    polylines: list[SceneLine]
    vias: list[SceneVia]
    facts: Json
    rejected: bool
    locked: bool
    bundle: str
    tool: Json
    unknown_geometry: bool


def _array(value: Any) -> list[Any]:
    return cast("list[Any]", value) if isinstance(value, list) else []


def _objects(value: Any) -> list[Json]:
    return [cast(Json, item) for item in _array(value) if isinstance(item, dict)]


def _texts(value: Any) -> list[str]:
    return [item for item in _array(value) if isinstance(item, str)]


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


def _um(value: int) -> int:
    quotient, remainder = divmod(value, 1000)
    return quotient + int(remainder > 500 or (remainder == 500 and quotient % 2 != 0))


def _point(raw: Any) -> list[int] | None:
    if isinstance(raw, list) and len(cast("list[Any]", raw)) == 2:
        x, y = cast("list[Any]", raw)
        if type(x) is int and type(y) is int:
            point = [_um(x), _um(y)]
            if all(abs(value) <= 2**53 - 1 for value in point):
                return point
    return None


def _size(value: Any) -> int | None:
    return _um(value) if type(value) is int and value > 0 else None


def _candidate(raw: Mapping[str, Any]) -> tuple[SceneCandidate, list[list[int]]]:
    polylines: list[SceneLine] = []
    vias: list[SceneVia] = []
    points: list[list[int]] = []
    unknown = False
    for item in _array(raw.get("geometry")):
        if not isinstance(item, dict):
            unknown = True
            continue
        part = cast("Json", item)
        if part.get("kind") == "track":
            given = _array(part.get("points"))
            line = [_point(q) for q in given]
            width = _size(part.get("width"))
            layer = part.get("layer")
            if len(line) < 2 or any(p is None for p in line) or not width or not isinstance(layer, str):
                unknown = True
                continue
            valid = cast("list[list[int]]", line)
            polylines.append({"layer": layer, "width": width, "points": valid})
            points += valid
        elif part.get("kind") == "via":
            at, diameter = _point(part.get("at")), _size(part.get("diameter"))
            layers = _texts(part.get("layers"))
            if at is None or not diameter or not layers:
                unknown = True
                continue
            via: SceneVia = {"at": at, "diameter": diameter, "layers": layers}
            if drill := _size(part.get("drill")):
                via["drill"] = drill
            vias.append(via)
            points.append(at)
        else:
            unknown = True
    entry: SceneCandidate = {
        "relaxed": _texts(raw.get("relaxed")),
        "polylines": polylines,
        "vias": vias,
        "rejected": bool(raw.get("rejected")),
    }
    if isinstance(raw.get("id"), str):
        entry["id"] = raw["id"]
    if isinstance(raw.get("source"), str):
        entry["source"] = raw["source"]
    if isinstance(raw.get("facts"), dict):
        entry["facts"] = copy.deepcopy(raw["facts"])
    if isinstance(raw.get("bundle"), str):
        entry["bundle"] = raw["bundle"]
    if isinstance(raw.get("tool"), dict):
        entry["tool"] = copy.deepcopy(raw["tool"])
    if type(raw.get("locked")) is bool:
        entry["locked"] = raw["locked"]
    if unknown:
        entry["unknown_geometry"] = True
    return entry, points


def _ends(raw: Any) -> list[SceneEnd]:
    ends: list[SceneEnd] = []
    for value in _array(raw):
        if not isinstance(value, dict):
            continue
        given = cast(Json, value)
        end: SceneEnd = {"layers": _texts(given.get("layers"))}
        for key in ("kind", "name"):
            if isinstance(given.get(key), str):
                end[key] = given[key]
        if at := _point(given.get("at")):
            end["at"] = at
        ends.append(end)
    return ends


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
        ends = _ends(proposal.get("ends"))
        points = [end["at"] for end in ends if "at" in end]
        candidates: list[SceneCandidate] = []
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
        for key in ("id", "kind", "net", "subject", "reason", "region"):
            if not isinstance(entry.get(key), str):
                entry.pop(key, None)
        if "ends" in proposal:
            entry["ends"] = ends
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
    for key in ("bundles", "role_fields", "external", "controls"):
        if key in result:
            data[key] = copy.deepcopy(result[key])
    return {key: value for key, value in data.items() if value is not None}


WRITABLE_FAMILIES = frozenset(
    {
        "shape",
        "z-shape",
        "via-l",
        "fanout",
        "role",
        "search",
        "external:kicadroutingtools",
        "external:freerouting",
    }
)


def _units(data: Mapping[str, Any]) -> tuple[dict[str, tuple[str, ...]], set[str]]:
    rows = [(p, c) for p in _objects(data.get("proposals")) for c in _objects(p.get("candidates"))]
    bundles = _objects(data.get("bundles"))
    owned = {str(c["id"]) for _, c in rows if c.get("id") and c.get("bundle")}
    claims: Counter[str] = Counter()
    for bundle in bundles:
        for member in _texts(bundle.get("members")):
            owned.add(member)
            claims[member] += 1
    controls = data.get("controls")
    if not isinstance(controls, dict):
        return {}, owned
    controls = cast(Json, controls)
    if controls.get("schema") != "fenolite.proposal_controls.v0":
        return {}, owned
    if "negotiate=on" not in _texts(controls.get("router_options")):
        return {}, owned
    by_id = {str(c.get("id")): (p, c) for p, c in rows}
    counts = Counter(str(c.get("id")) for _, c in rows)
    bundle_ids = Counter(str(b.get("id")) for b in bundles)
    valid: dict[str, tuple[str, ...]] = {}
    for bundle in bundles:
        ident, fingerprint = bundle.get("id"), bundle.get("fingerprint")
        members = _texts(bundle.get("members"))
        if not isinstance(bundle.get("members"), list) or len(members) != len(bundle["members"]):
            continue
        if (
            not isinstance(ident, str)
            or re.fullmatch(r"b-[0-9a-f]{16}", ident) is None
            or bundle_ids[ident] != 1
            or not isinstance(fingerprint, str)
            or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None
            or len(members) < 2
            or len(set(members)) != len(members)
        ):
            continue
        if any(
            re.fullmatch(r"c-[0-9a-f]{16}", member) is None or counts[member] != 1 or claims[member] != 1
            for member in members
        ):
            continue
        declared = {str(c.get("id")) for _, c in rows if c.get("bundle") == ident}
        if declared != set(members):
            continue
        if any(by_id[member][1].get("source") not in WRITABLE_FAMILIES for member in members):
            continue
        subjects = [by_id[member][0].get("subject") for member in members]
        if any(not isinstance(subject, str) for subject in subjects):
            continue
        if len(set(subjects)) != len(subjects) or subjects != bundle.get("subjects"):
            continue
        valid[ident] = tuple(members)
    return valid, owned


def bundle_units(data: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """Complete, unambiguous bundle units; malformed membership never falls back to member writes."""
    return _units(data)[0]


def ids_of(data: Mapping[str, Any] | None) -> tuple[frozenset[str], frozenset[str]]:
    """Writable units and independent proposal IDs; bound members cannot be accepted or rejected alone."""
    if not data:
        return frozenset(), frozenset()
    proposals = _objects(data.get("proposals"))
    bundles, owned = _units(data)
    candidates = {
        str(c["id"])
        for p in proposals
        for c in _objects(p.get("candidates"))
        if c.get("id") and c.get("id") not in owned and c.get("source") in WRITABLE_FAMILIES
    }
    proposal_ids = {
        str(p["id"])
        for p in proposals
        if p.get("id") and not any(c.get("id") in owned for c in _objects(p.get("candidates")))
    }
    return frozenset(candidates | set(bundles)), frozenset(proposal_ids)


def summary(data: Mapping[str, Any]) -> Json:
    """``result.proposals`` of ``fenolite view``: the counts and the evidence of the reply shown."""
    counts = cast("Json", data.get("counts") or {})
    return {
        "document": data.get("document"),
        "proposals": counts.get("proposals", 0),
        "candidates": counts.get("candidates", 0),
        "evidence": cast("Json", data.get("evidence") or {}).get("level"),
    }


__all__ = ["SCHEMA", "bundle_units", "ids_of", "overlay", "read_reply", "summary"]
