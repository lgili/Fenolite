# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` findings drawn on a board or a sheet (capability check-overlay, change c0188).

A ``check`` reply names where a finding is in three forms (``docs/viewer.md``, "Check findings"):

* ``@<x>,<y>`` parts of ``where``: a position in millimetres, in the file's frame (the DRC and ERC stages of
  ``kicad-cli``; the ERC prefixes it with the sheet path, ``/Power/@12.5,30``);
* ``on <layer> at (<x>, <y>) mm`` in the message: Fenolite's own copper check;
* names in ``where``: a pad (``R1-2``), a part (``R1``), a KiCad locator (``/kicad_pcb/segment[3]``) or a net.

``overlay(reply, scene)`` resolves each finding against the scene shown: a marker at its first position, a box
around everything it names, and its layer when the finding states one. Findings that resolve to nothing are
listed only. Each finding carries the evidence of the stage its code belongs to. Standard library only.
"""

from __future__ import annotations

import re
from typing import Any, cast

from fenolite.core.errors import FormatError

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
STAGE_OF = (
    ("kicad.drc.", "drc.kicad"),
    ("kicad.erc.", "erc.kicad"),
    ("erc.", "erc.lite"),
    ("copper.", "copper.clearance"),
    ("length.", "length.rules"),
    ("place.", "placement.rules"),
    ("placement.", "placement.rules"),
    ("parity.", "parity"),
    ("model.", "model.validate"),
    ("netlist.", "netlist.assignment_compare"),
    ("zone.", "zone.fill"),
)
"""The stage a finding's code comes from, by the code's prefix; the first match wins."""

_AT = re.compile(r"(?P<sheet>[^@,]*)@(?P<x>-?\d+(?:\.\d+)?),(?P<y>-?\d+(?:\.\d+)?)$")
_MESSAGE_AT = re.compile(r"(?:\bon (?P<layer>\S+) )?at \((?P<x>-?\d+(?:\.\d+)?), (?P<y>-?\d+(?:\.\d+)?)\) mm")
_LOCATOR = re.compile(r"^/kicad_pcb/(?P<kind>segment|arc|via|zone)\[(?P<k>\d+)\]$")
_LABEL = {"segment": "track", "arc": "arc", "via": "via"}
UM_PER_MM = 1000

Box = list[float]


def read_reply(data: Any, *, name: str = "") -> dict[str, Any]:
    """The ``check`` reply ``data`` (a parsed JSON envelope); ``FormatError`` when it is not one."""
    if not isinstance(data, dict):
        raise FormatError(f"{name or 'the reply'} is not a fenolite check reply", file=name)
    reply = cast("dict[str, Any]", data)
    if reply.get("command") != "check" or not isinstance(reply.get("issues"), list):
        found = reply.get("command")
        raise FormatError(
            f"{name or 'the reply'} is not a fenolite check reply"
            + (f" (it is a {found} reply)" if isinstance(found, str) else ""),
            file=name,
        )
    return reply


def _label(evidence: Any) -> str:
    """An evidence object of a reply as one label: ``ORACLE-VERIFIED(kicad-cli 10.0.6)``."""
    if not isinstance(evidence, dict):
        return ""
    found = cast("dict[str, Any]", evidence)
    level, oracle = str(found.get("level") or ""), found.get("oracle")
    return f"{level}({oracle})" if level and oracle and "(" not in level else level


BOARD_STAGES = frozenset({"drc.kicad", "copper.clearance", "zone.fill", "placement.rules", "length.rules"})
SHEET_STAGES = frozenset({"erc.kicad", "erc.lite"})
"""Stages whose findings are placed only on a board, and only on a sheet; the others are placed on either."""


def _stage(code: str) -> str:
    return next((stage for prefix, stage in STAGE_OF if code.startswith(prefix)), "")


def _grow(box: Box | None, other: Box) -> Box:
    if box is None:
        return list(other)
    return [min(box[0], other[0]), min(box[1], other[1]), max(box[2], other[2]), max(box[3], other[3])]


def _prim_box(prim: list[Any]) -> Box | None:
    kind, d = prim[1], prim[2]
    if kind == "s" and len(d) >= 4:
        return [min(d[0], d[2]), min(d[1], d[3]), max(d[0], d[2]), max(d[1], d[3])]
    if kind == "a" and len(d) >= 6:
        xs, ys = d[0:6:2], d[1:6:2]
        return [min(xs), min(ys), max(xs), max(ys)]
    if kind == "c" and len(d) >= 3:
        return [d[0] - d[2], d[1] - d[2], d[0] + d[2], d[1] + d[2]]
    if kind in ("p", "o", "h") and d and isinstance(d[0], list):  # rings of flat x, y lists
        flat = [v for ring in cast("list[list[float]]", d) for v in ring]
        if len(flat) >= 2:
            return [min(flat[0::2]), min(flat[1::2]), max(flat[0::2]), max(flat[1::2])]
    return None


def _innermost(boxes: list[Box]) -> list[Box]:
    """``boxes`` without those that hold another one whole (a zone around the pad a finding names), so the
    marker lands on the item, not in the middle of the zone."""

    def holds(a: Box, b: Box) -> bool:
        return a != b and a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]

    return [a for a in boxes if not any(holds(a, b) for b in boxes)]


class _BoardIndex:
    """Names of a board scene to boxes in its units (µm): pads, parts, tracks, arcs, vias and nets."""

    def __init__(self, scene: dict[str, Any]) -> None:
        self.names: dict[str, tuple[Box, str | None]] = {}
        self.zones = [str(z) for z in cast("list[Any]", scene.get("zones", []))]
        zones = set(self.zones)
        for pad in cast("list[dict[str, Any]]", scene.get("pads", [])):
            x, y = pad["x"], pad["y"]
            self.names.setdefault(str(pad["label"]), ([x, y, x, y], None))
        for comp in cast("list[dict[str, Any]]", scene.get("comps", [])):
            if comp.get("bbox"):
                self.names.setdefault(str(comp["ref"]), (list(comp["bbox"]), None))
        nets = cast("list[str]", scene.get("nets", []))
        net_boxes: dict[int, Box] = {}
        for prim in cast("list[list[Any]]", scene.get("prims", [])):
            box = _prim_box(prim)
            if box is None:
                continue
            label = str(prim[5])
            if (
                label.startswith(("track ", "arc ", "via ")) and not label.endswith("hole")
            ) or label in zones:
                found = self.names.get(label)
                self.names[label] = (_grow(found[0] if found else None, box), prim[0])
            if isinstance(prim[3], int) and prim[3] >= 0:
                net_boxes[prim[3]] = _grow(net_boxes.get(prim[3]), box)
        for k, box in net_boxes.items():
            if k < len(nets) and nets[k]:
                self.names.setdefault(nets[k], (box, None))

    def find(self, name: str) -> tuple[Box, str | None] | None:
        located = _LOCATOR.match(name)
        if located and located["kind"] == "zone":
            k = int(located["k"])
            name = self.zones[k] if k < len(self.zones) else ""
        elif located:
            name = f"{_LABEL[located['kind']]} {int(located['k']) + 1}"
        return self.names.get(name)


class _SheetIndex:
    """Names of a sheet scene to boxes in its units: its parts by reference, and their pins (``REF-PIN``)."""

    def __init__(self, scene: dict[str, Any]) -> None:
        self.names: dict[str, tuple[Box, str | None]] = {}
        comps = cast("list[dict[str, Any]]", scene.get("comps", []))
        for obj in cast("list[dict[str, Any]]", scene.get("objects", [])):
            ci, box = int(obj.get("comp", -1)), cast("Box | None", obj.get("b"))
            if obj.get("k") != "comp" or not box or not 0 <= ci < len(comps):
                continue
            ref = str(comps[ci].get("ref", ""))
            if ref:
                found = self.names.get(ref)
                self.names[ref] = (_grow(found[0] if found else None, box), None)

    def find(self, name: str) -> tuple[Box, str | None] | None:
        found = self.names.get(name)
        if found is None and "-" in name:
            found = self.names.get(name.rsplit("-", 1)[0])  # a pin: the box of its part
        return found


def _sheet_matches(path: str, document: str) -> bool:
    """Whether the ERC sheet path ``path`` names the sheet ``document``: ``/`` for the root sheet (a document
    of the project's stem), else its last segment against the document's stem, ignoring case."""
    segments = [s for s in path.split("/") if s]
    stem = document.rsplit(".", 1)[0].casefold()
    return not segments or segments[-1].casefold() == stem


def overlay(reply: dict[str, Any], scene: dict[str, Any], *, root_sheet: bool = True) -> dict[str, Any]:
    """The findings of the ``check`` reply placed on ``scene`` (module docstring): ``findings`` sorted by
    severity then code, ``counts`` per severity, ``placed`` and ``notes``. ``root_sheet`` says whether a sheet
    scene is the project's root sheet (ERC findings of path ``/``)."""
    sheet = scene.get("kind") == "schematic"
    index: _BoardIndex | _SheetIndex = _SheetIndex(scene) if sheet else _BoardIndex(scene)
    meta = cast("dict[str, Any]", scene.get("meta", {}))
    document = str(meta.get("name", ""))
    to_units = UM_PER_MM if not sheet or meta.get("backend") == "kicad" else None  # a KiCad sheet is in µm
    stages: dict[str, dict[str, Any]] = {}
    for s in cast("list[Any]", cast("dict[str, Any]", reply.get("result") or {}).get("stages", [])):
        if isinstance(s, dict):
            stage = cast("dict[str, Any]", s)
            stages[str(stage.get("name"))] = stage
    default = _label(reply.get("evidence"))
    findings: list[dict[str, Any]] = []
    for raw in cast("list[Any]", reply["issues"]):
        if not isinstance(raw, dict):
            continue
        item = cast("dict[str, Any]", raw)
        code, message = str(item.get("code", "")), str(item.get("message", ""))
        where = str(item.get("where", ""))
        stage = _stage(code)
        level = _label(stages.get(stage, {}).get("evidence")) or default
        at: list[float] | None = None
        box: Box | None = None
        layer: str | None = None
        elsewhere = stage in (BOARD_STAGES if sheet else SHEET_STAGES)  # a finding of the other document kind
        said = None if elsewhere else _MESSAGE_AT.search(message)
        if said and not sheet:
            at = [float(said["x"]) * UM_PER_MM, float(said["y"]) * UM_PER_MM]
            layer = said["layer"]
        named: list[Box] = []
        parts = [] if elsewhere else [p.strip() for p in where.split(", ") if p.strip()]
        for part in parts:
            point = _AT.match(part)
            if point:
                on_sheet = bool(point["sheet"])
                if on_sheet != sheet or to_units is None:
                    elsewhere = elsewhere or on_sheet != sheet
                    continue
                root = not [s for s in point["sheet"].split("/") if s]
                if on_sheet and not (_sheet_matches(point["sheet"], document) and (root_sheet or not root)):
                    elsewhere = True
                    continue
                p = [float(point["x"]) * to_units, float(point["y"]) * to_units]
                at = at or p
                box = _grow(box, [p[0], p[1], p[0], p[1]])
                continue
            found = index.find(part)
            if found is not None:
                named.append(found[0])
                layer = layer or found[1]
        for kept in _innermost(named):
            box = _grow(box, kept)
        if at is not None:
            box = _grow(box, [at[0], at[1], at[0], at[1]])
        elif box is not None and not elsewhere:
            at = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
        elif elsewhere:
            box = None
        findings.append(
            {
                "code": code,
                "severity": str(item.get("severity", "info")),
                "message": message,
                "where": where,
                "stage": stage,
                "evidence": level,
                "layer": layer,
                "at": at,
                "box": box,
            }
        )
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 3), f["code"]))
    counts = {severity: sum(1 for f in findings if f["severity"] == severity) for severity in SEVERITY_ORDER}
    notes: list[str] = []
    drc = cast("dict[str, Any]", stages.get("drc.kicad", {}).get("summary") or {})
    if drc.get("limits"):
        notes.append(
            "KiCad's DRC report was capped for some rules: their counts are lower bounds "
            "(check.report-limit)."
        )
    placed = sum(1 for f in findings if f["at"] is not None)
    if placed < len(findings):
        notes.append(f"{len(findings) - placed} finding(s) have no position on this document: listed only.")
    return {"findings": findings, "counts": counts, "placed": placed, "notes": notes}


def summary(placed: dict[str, Any]) -> dict[str, Any]:
    """``result.check`` of ``fenolite view``: the counts per severity and how many findings were placed."""
    return {**placed["counts"], "total": len(placed["findings"]), "placed": placed["placed"]}


__all__ = ["BOARD_STAGES", "SEVERITY_ORDER", "SHEET_STAGES", "STAGE_OF", "overlay", "read_reply", "summary"]
