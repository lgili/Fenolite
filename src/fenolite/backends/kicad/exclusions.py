# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DRC exclusions written into a KiCad project (change c0209; ``docs/formats/kicad/drc.md``, "Written
exclusions"; ``H-K-DRC-EXCLUSION``).

KiCad applies a stored exclusion only when its type, its marker position in nm and its two uuids in order
equal those of a violation (``H-K-DRC-EXCL``). The report gives neither: an item's ``pos`` is the item's
own position, not the marker's (a missing connection is marked at the end of the ratsnest line), and the
order of the two uuids in the key is not the order of the report. So a key is found by trial: the
anchors of the two items (report positions, track and arc ends, via, pad and footprint positions, zone
corners) each give a key in both orders, all of them are stored with a probe comment in the project of a
copy, and the comment that ``pcb drc`` puts on the entry names the key that applies. The exclusion is
then written at that position in both orders, because KiCad does not keep the order of the two items,
and a last run on a copy confirms it.
"""

from __future__ import annotations

import tempfile
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, cast

from fenolite.backends.base import NIL_UUID, DrcReport, DrcViolation, ProjectSet
from fenolite.backends.kicad import _json
from fenolite.backends.kicad.cli import DrcRun, KicadCli
from fenolite.backends.kicad.frame import board_pads
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.pro import (
    EXCLUSION_POINTER,
    project_exclusions,
    read_project_text,
    write_project_text,
)
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.KICAD_VERIFIED, oracle="kicad-cli", hypotheses=("H-K-DRC-EXCLUSION",))
"""A written exclusion is confirmed by a ``pcb drc`` run on a copy before it is planned."""
PROBE = "fenolite-probe"
"""The comment prefix of the trial keys: ``fenolite-probe:<index>``."""
MAX_ANCHORS = 128
"""At most this many candidate positions per exclusion (two keys each)."""


def exclusion_key(kind: str, position: Point, first: str, second: str = NIL_UUID) -> str:
    """The stored key ``<type>|<x>|<y>|<uuid>|<uuid>`` (``project.md``, "Stored exclusions")."""
    return f"{kind}|{position.x}|{position.y}|{first.lower()}|{second.lower()}"


def mirrored_keys(kind: str, position: Point, first: str, second: str = NIL_UUID) -> tuple[str, ...]:
    """The keys of one exclusion in both orders of its two items; one key for an entry of one item."""
    keys = [exclusion_key(kind, position, first, second)]
    if second.lower() != NIL_UUID and second.lower() != first.lower():
        keys.append(exclusion_key(kind, position, second, first))
    return tuple(keys)


def _uuids(entry: DrcViolation) -> tuple[str, str]:
    found = [item.uuid.lower() for item in entry.items][:2]
    return (found[0] if found else NIL_UUID, found[1] if len(found) > 1 else NIL_UUID)


def anchors(design: Design | None, entry: DrcViolation) -> tuple[Point, ...]:
    """The positions a marker of ``entry`` may sit at, in a stable order and without repeats: the report
    positions of its items, then the anchors of the board entities whose KiCad uuid it names."""
    wanted = {item.uuid.lower() for item in entry.items}
    found: list[Point] = [item.position for item in entry.items]
    board = None if design is None else design.board
    if design is not None and board is not None:
        for track in board.tracks:
            if kicad_uuid(track).lower() in wanted:
                found += [track.start, track.end]
        for arc in board.arcs:
            if kicad_uuid(arc).lower() in wanted:
                found += [arc.start, arc.mid, arc.end]
        for via in board.vias:
            if kicad_uuid(via).lower() in wanted:
                found.append(via.position)
        pads = {pad.id: pad for footprint in board.footprints for pad in footprint.pads}
        for placed in board_pads(design):
            pad = pads.get(placed.pad_id)
            if pad is not None and kicad_uuid(pad).lower() in wanted:
                found.append(placed.position)
        for footprint in board.footprints:
            if kicad_uuid(footprint).lower() in wanted:
                found.append(footprint.position)
        for area in (*board.zones, *board.keepouts):
            if kicad_uuid(area).lower() in wanted:
                found += list(area.outline)
    return tuple(dict.fromkeys(found))[:MAX_ANCHORS]


def stored_keys(text: str | None) -> tuple[str, ...]:
    """The keys of ``drc_exclusions`` in a project text, either form, in file order."""
    if text is None:
        return ()
    raw = _json.get(read_project_text(text), EXCLUSION_POINTER)
    keys: list[str] = []
    for entry in cast(list[Any], raw) if isinstance(raw, list) else []:
        key: Any = entry
        if isinstance(entry, list):
            pair = cast(list[Any], entry)
            key = pair[0] if pair else None
        if isinstance(key, str):
            keys.append(key)
    return tuple(keys)


def stored_position(text: str | None, entry: DrcViolation) -> Point | None:
    """The position of the first stored exclusion of ``entry``'s type that names its items in either order:
    the marker position of an entry the project already excludes; ``None`` when none is stored."""
    if text is None:
        return None
    wanted = set(_uuids(entry))
    for stored in project_exclusions(read_project_text(text)):
        if stored.type == entry.type and {uuid.lower() for uuid in stored.uuids} == wanted:
            return stored.position
    return None


def add_exclusions(text: str | None, entries: Sequence[tuple[str, str]]) -> str:
    """``text`` (``None``: no project file, ``{}``) with each ``(key, comment)`` of ``entries`` appended to
    ``board.design_settings.drc_exclusions`` in the pair form, a key already stored left out. Every other
    key keeps its place and spelling (``_json``)."""
    data = read_project_text(text if text is not None else "{}")
    node: dict[str, Any] = data
    for part in EXCLUSION_POINTER.strip("/").split("/")[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = cast(dict[str, Any], child)
    current = node.get("drc_exclusions")
    listed: list[Any] = cast(list[Any], current) if isinstance(current, list) else []
    have = set(stored_keys(text))
    for key, comment in entries:
        if key not in have:
            listed.append([key, comment])
            have.add(key)
    node["drc_exclusions"] = listed
    return write_project_text(data)


def same_entry(a: DrcViolation, b: DrcViolation) -> bool:
    """Whether two entries have one type and name one set of items (the order is not kept)."""
    return a.type == b.type and set(_uuids(a)) == set(_uuids(b))


def _entries(report: DrcReport) -> tuple[DrcViolation, ...]:
    return (*report.violations, *report.unconnected_items, *report.schematic_parity)


def run_with_project(cli: KicadCli, project: ProjectSet, text: str | None) -> DrcRun:
    """``pcb drc`` on a copy of ``project`` whose project file holds ``text`` (the board's own project
    file when ``text`` is ``None``)."""
    if text is None:
        others = {name: path for name, path in project.files.items() if name != project.board}
        return cli.drc(project.files[project.board], files=others)
    name = Path(project.board).with_suffix(".kicad_pro").as_posix()
    with tempfile.TemporaryDirectory(prefix="fenolite-excl-") as tmp:
        written = Path(tmp) / Path(name).name
        written.write_text(text, encoding="utf-8")
        others: dict[str, Path] = {n: p for n, p in project.files.items() if n not in (project.board, name)}
        others[name] = written
        return cli.drc(project.files[project.board], files=others)


def locate(
    cli: KicadCli, project: ProjectSet, entry: DrcViolation, candidates: Iterable[Point], text: str | None
) -> Point | None:
    """The marker position of ``entry``: one ``pcb drc`` run on a copy whose project is ``text`` plus a
    probe key per candidate and order, read back by the probe comment the excluded entry carries."""
    kind = entry.type
    first, second = _uuids(entry)
    points = tuple(candidates)
    probes: list[tuple[str, str]] = []
    for index, point in enumerate(points):
        probes += [(key, f"{PROBE}:{index}") for key in mirrored_keys(kind, point, first, second)]
    run = run_with_project(cli, project, add_exclusions(text, probes))
    report = run.report
    if report is None:
        return None
    for found in _entries(report):
        if same_entry(found, entry) and found.excluded and found.comment.startswith(f"{PROBE}:"):
            index = found.comment.removeprefix(f"{PROBE}:")
            if index.isdigit() and int(index) < len(points):
                return points[int(index)]
    return None


def confirmed(report: DrcReport | None, entry: DrcViolation, comment: str) -> bool:
    """Whether ``report`` marks ``entry`` excluded with ``comment``."""
    if report is None:
        return False
    return any(
        same_entry(found, entry) and found.excluded and found.comment == comment for found in _entries(report)
    )


def item_uuids(entry: DrcViolation) -> tuple[str, str]:
    """The two uuids of ``entry`` in report order, lower case, the nil uuid for a missing second item."""
    return _uuids(entry)


def project_name(project: ProjectSet) -> str:
    """The name of the board's project file in the copy set (it may not exist yet)."""
    return Path(project.board).with_suffix(".kicad_pro").as_posix()


def project_text(project: ProjectSet) -> str | None:
    """The text of the board's project file, ``None`` when the set has none."""
    path = project.files.get(project_name(project))
    return None if path is None else path.read_text(encoding="utf-8")


__all__ = [
    "EVIDENCE",
    "MAX_ANCHORS",
    "PROBE",
    "add_exclusions",
    "anchors",
    "confirmed",
    "exclusion_key",
    "item_uuids",
    "locate",
    "mirrored_keys",
    "project_name",
    "project_text",
    "run_with_project",
    "same_entry",
    "stored_keys",
    "stored_position",
]
