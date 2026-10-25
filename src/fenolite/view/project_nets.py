# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project nets on the sheets of an Altium project (capability project-connectivity-view, change c0185).

A sheet's scene (c0177) holds the nets of that sheet alone. The Altium backend's read of the project compiles
the nets across its sheets (ports, sheet entries, power ports, net labels and harnesses, as ``build`` and
``check`` see them); this module maps each local net of a sheet to its project net by pin membership, so the
two never disagree:

* ``pin_nets(design)``: every pin (``REF-PIN``) to the name of its project net;
* ``project_index(design, sheets)``: per project net, its pins and the sheets it appears on, from the scenes
  of the project's sheets (document name to scene);
* ``annotate(scene, ...)``: a copy of a sheet scene whose nets carry ``project`` (the project net's name),
  ``project_pins`` and ``sheets``. A local net without a pin takes the project net of its own name, when there
  is one; a local net that maps to none keeps its own name;
* ``sheet_params(scene, sheets)`` (change c0187): a copy of a board scene whose parts carry the parameters of
  their schematic part, matched by the last segment of the board part's ``SOURCEUNIQUEID``.

Standard library only.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, cast

from fenolite.model.design import Design


def pin_nets(design: Design) -> dict[str, str]:
    """Every pin of the project's circuit, as ``REF-PIN``, to the name of its net."""
    refs = {c.id: c.ref for c in design.circuit.components}
    out: dict[str, str] = {}
    for net in design.circuit.nets:
        for member in net.members:
            ref = refs.get(member.component_id)
            if ref:
                out[f"{ref}-{member.pin}"] = net.name
    return out


def _local(net: dict[str, Any], pins: dict[str, str], names: set[str]) -> str | None:
    for pin in cast("list[str]", net.get("pins", [])):
        if pin in pins:
            return pins[pin]
    name = net.get("name")
    return name if isinstance(name, str) and name in names else None


def project_index(design: Design, sheets: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per project net: its pins (sorted) and the names of the sheets it appears on."""
    pins = pin_nets(design)
    names = {net.name for net in design.circuit.nets}
    members: dict[str, list[str]] = defaultdict(list)
    for pin, name in pins.items():
        members[name].append(pin)
    on: dict[str, set[str]] = defaultdict(set)
    for sheet, scene in sheets.items():
        for net in cast("list[dict[str, Any]]", scene.get("nets", [])):
            found = _local(net, pins, names)
            if found is not None:
                on[found].add(sheet)
    return {
        name: {"pins": sorted(members.get(name, [])), "sheets": sorted(on.get(name, set()))}
        for name in sorted(names)
    }


def annotate(scene: dict[str, Any], design: Design, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A copy of the sheet ``scene`` whose nets carry their project net (module docstring)."""
    pins = pin_nets(design)
    names = set(index)
    nets: list[dict[str, Any]] = []
    for net in cast("list[dict[str, Any]]", scene.get("nets", [])):
        found = _local(net, pins, names)
        if found is None:
            nets.append(net)
            continue
        nets.append(
            net | {"project": found, "project_pins": index[found]["pins"], "sheets": index[found]["sheets"]}
        )
    meta = dict(cast("dict[str, Any]", scene["meta"]))
    meta["counts"] = dict(cast("dict[str, Any]", meta.get("counts", {}))) | {"project_nets": len(index)}
    return scene | {"nets": nets, "meta": meta}


def sheet_params(scene: dict[str, Any], sheets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """A copy of the board ``scene`` whose parts take the parameters of their schematic part (module
    docstring); a board parameter of the same name stays. ``scene`` itself when no part matches."""
    by_uid: dict[str, dict[str, Any]] = {}
    for sheet in sheets.values():
        for comp in cast("list[dict[str, Any]]", sheet.get("comps", [])):
            if comp.get("uid"):
                by_uid.setdefault(str(comp["uid"]), comp)
    comps: list[dict[str, Any]] = []
    matched = 0
    for comp in cast("list[dict[str, Any]]", scene.get("comps", [])):
        segments = [s for s in str(comp.get("uid", "")).split("\\") if s]
        found = by_uid.get(segments[-1]) if segments else None
        if found is None:
            comps.append(comp)
            continue
        matched += 1
        extra = {"Comment": found.get("comment", ""), "Description": found.get("description", "")}
        params = {k: str(v) for k, v in (extra | dict(found.get("params", {}))).items() if v}
        comps.append(comp | {"params": params | dict(comp.get("params", {}))})
    return scene | {"comps": comps} if matched else scene


__all__ = ["annotate", "pin_nets", "project_index", "sheet_params"]
