# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The link of a PCB component to its schematic part (capability altium-edit, "A PCB component linked to its
schematic part"; change c0499, design D4).

Altium's Design » Update PCB matches a component to its part by ``SOURCEUNIQUEID``, the unique-id path of the
part (``connectivity.md``, "Component link"; ``H-A-IMP-LINK``). ``link`` writes that path and the four other
source keys from the part as the project reads (``adapter.netlist.resolve``, the hierarchy ``fenolite
import`` reads), sets ``CHANNELOFFSET`` past the components of the same hierarchical path, and adds the
designator to the component class of the part's sheet when ``Classes6`` holds one. A part whose footprint or
comment differs from the component's refuses: Update PCB would propose that change (``H-A-EDIT-LINK``).
"""

# evidence: see edit.session

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.ops import Comment, Refused, View
from fenolite.backends.altium.edit.state import State


def _assert(condition: bool, message: str, where: str) -> None:
    if not condition:
        raise Refused("altium.edit.assertion", message, where)


@dataclass(frozen=True, slots=True)
class ProjectPart:
    """One part of a project as the link needs it."""

    ref: str
    sheet: str
    path: str
    """The unique-id path, ``\\<sheet symbol id>…\\<part id>``."""
    hierarchy: str
    """``SOURCEHIERARCHICALPATH``: empty on the top sheet, else ``<top stem>\\<sheet symbol designator>…``."""
    cls: str
    """The name of the sheet's component class: its sheet symbol's designator, or the sheet's stem on top."""
    lib_reference: str
    library: str
    footprint: str
    comment: str


def project_parts(project: str | Path) -> list[ProjectPart]:
    """Every part of the project's sheets that has a unique-id path (a part of a ``Repeat`` channel has none),
    by the reader of ``fenolite import``."""
    from fenolite.backends.altium.adapter.netlist import NetOptions, SheetInput, resolve
    from fenolite.backends.altium.read.project import load_project
    from fenolite.backends.altium.read.sch import read_schematic

    loaded = load_project(project)
    sheets: list[SheetInput] = []
    for item in loaded.documents:
        if item.document.kind == "schematic" and item.present and item.file is not None:
            data = item.file.read_bytes()
            sheets.append(SheetInput(item.file.name, "", read_schematic(data, file=item.file.name)))
    resolved = resolve(sheets, NetOptions.from_project(loaded), [])
    top = next((i for i in resolved.instances if i.parent is None), None)
    top_stem = Path(resolved.sheets[top.sheet].input.file).stem if top is not None else ""
    out: list[ProjectPart] = []
    for instance in resolved.instances:
        if instance.repeated:
            continue
        sheet = resolved.sheets[instance.sheet]
        stem = Path(sheet.input.file).stem
        prefix = "".join(f"\\{uid}" for uid in instance.uids)
        hierarchy = "\\".join((top_stem, *instance.names)) if instance.names else ""
        for number, group in enumerate(sheet.groups):
            if not group.unique_ids:
                continue
            out.append(
                ProjectPart(
                    ref=resolved.refs.get((instance.index, number), group.ref),
                    sheet=sheet.input.file,
                    path=f"{prefix}\\{group.unique_ids[0]}",
                    hierarchy=hierarchy,
                    cls=instance.names[-1] if instance.names else stem,
                    lib_reference=group.first.lib_reference or "",
                    library=group.first.source_library or "",
                    footprint=group.lib_footprint_ref.rpartition(":")[2],  # the model name, record 45
                    comment=group.value,
                )
            )
    return out


def link(state: State, designator: str, parts: list[ProjectPart], part: str, sheet: str | None) -> None:
    """Write the source keys of the component ``designator`` from the one part ``part`` of ``parts`` (on the
    sheet file ``sheet`` when given), and add it to its sheet's component class."""
    found = [p for p in parts if p.ref == part and (sheet is None or p.sheet.lower() == sheet.lower())]
    _assert(len(found) == 1, f"{len(found)} parts of the project are named {part!r}, not one", "project")
    source = found[0]
    view = View(state)
    index = view.component(designator)
    record = view.components[index]
    pattern = record.get("PATTERN") or ""
    _assert(pattern == source.footprint, f"the part {part} names the footprint {source.footprint!r}, the "
            f"component {designator} is {pattern!r}: Update PCB would change it", "Components6")  # fmt: skip
    comment = view.shown(state.typed("Texts6")[view.component_text(Comment(designator))])  # type: ignore[arg-type]
    _assert(comment == source.comment, f"the part {part} has the comment {source.comment!r}, the component "
            f"{designator} {comment!r}: Update PCB would change it", "Components6")  # fmt: skip
    offsets = [
        int(c.get("CHANNELOFFSET") or "0")
        for n, c in enumerate(view.components)
        if n != index and (c.get("SOURCEHIERARCHICALPATH") or "") == source.hierarchy
        and (c.get("CHANNELOFFSET") or "").lstrip("-").isdigit()
    ]  # fmt: skip
    changes = {
        "SOURCEUNIQUEID": source.path,
        "SOURCEHIERARCHICALPATH": source.hierarchy,
        "SOURCEDESIGNATOR": source.ref,
        "SOURCELIBREFERENCE": source.lib_reference,
        "SOURCECOMPONENTLIBRARY": source.library,
        "CHANNELOFFSET": str(max(offsets, default=-1) + 1),
    }
    state.replace("Components6", index, rec.set_property(record.raw, changes))
    if not state.has("Classes6"):
        return
    for position, cls in enumerate(state.properties("Classes6")):
        if cls.get("KIND") != "1" or cls.get("NAME") != source.cls:
            continue
        held = [value for key, value in cls.fields if re.fullmatch(r"M\d+", key.upper())]
        if source.ref not in held:
            members = [(f"M{n}", value) for n, value in enumerate((*held, source.ref))]
            raw = rec.replace_run(cls.raw, lambda key: re.fullmatch(r"M\d+", key) is not None, members)
            state.replace("Classes6", position, raw)
        return


__all__ = ["ProjectPart", "link", "project_parts"]
