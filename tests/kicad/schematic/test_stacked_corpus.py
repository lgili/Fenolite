# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stacked pins of third-party sheets against KiCad's netlist (capability kicad-oracle, "Stacked pins of
corpus sheets"; ``H-K-SCH-STACKED-OPEN``; change c0123).

Fenolite's own netlist reads the pins of one symbol instance that have one name and connect at one point
without a label as one net, named after the lowest of their numbers. On the sheets ``build`` writes that
is proved by the stacked design. This test asks the same of sheets Fenolite did not write: in every demo
project of the corpus that the running ``kicad-cli`` loads, each such stack must be one net of ``sch
export netlist``, with the name ``netnames.open_name`` gives.

What this proves and what it does not:

- No demo sheet is inside the grammar of the own netlist (each holds wires, local labels or sub-sheets), so
  the whole netlist of a third-party sheet is not compared here: only the rule for the stack is.
- The demo projects hold few such stacks. On KiCad 10.0.6 one project has them (``PINNED``); the other
  projects are skipped, and say so.
- An instance that is mirrored and turned by 90 or 270 degrees is left out (``left_out``): for such an
  instance two demo sheets connect the pins where "rotate, then mirror" puts them, and
  ``schlayout.pin_point`` mirrors first. That order is reported apart from this change (change c0137),
  and until it is settled the pin points of such an instance are not known well enough to find a stack.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path, PurePosixPath

import _erc
import _schcorpus
import _schprojects
import pytest
from _boards import census
from _corpus import manifest_items, require
from _probes import major, runner, version

from fenolite.backends.kicad import netnames, sch, schlayout
from fenolite.core.coords import Point
from fenolite.model.library import SymbolPin
from fenolite.model.schematic import SchematicSheet, SymbolInstance

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]
SECTION = "stacked-corpus"
ROOTS = sorted({r.id: r for m in (9, 10) for r in _schprojects.roots(m)}.values(), key=lambda r: r.id)
PINNED: dict[tuple[str, int], int] = {("kicad-demo-10-0-6-sch-017", 10): 10}
"""(project, major) → the stacks that the run must judge there, so that the test never passes on nothing:
measured on 10.0.6 on 2026-10-07. A project outside the table may be skipped for having no stack."""


def _on(point: Point, start: Point, end: Point) -> bool:
    if start.x == end.x == point.x:
        return min(start.y, end.y) <= point.y <= max(start.y, end.y)
    if start.y == end.y == point.y:
        return min(start.x, end.x) <= point.x <= max(start.x, end.x)
    return point in (start, end)


def left_out(instance: SymbolInstance) -> bool:
    """Mirrored and turned by 90 or 270 degrees: see the module text and change c0137."""
    return bool(instance.mirror) and (instance.rotation // 1_000_000) % 360 in (90, 270)


def stacks(sheet: SchematicSheet) -> list[tuple[SymbolInstance, list[SymbolPin], bool, int]]:
    """Each group of pins of one instance of ``sheet`` that have one name and connect at one point which
    nothing else touches (no label, no wire, no pin of another instance): the instance, the pins, whether
    a no-connect flag marks the point, and the unit count of the symbol. Hidden power inputs are left out:
    KiCad joins them by name. So is a point that an instance of ``left_out`` or of a symbol whose pins are
    not known here may touch: its origin is taken as such a point."""
    known = {definition.lib_id: definition for definition in sheet.lib_symbols}
    wires = [tuple(points) for points in sch.opaque_wires(sheet)]
    segments = [(a, b) for points in wires for a, b in zip(points, points[1:], strict=False)]
    labels = {label.position for label in sheet.labels}
    flags = {flag.position for flag in sheet.no_connects}
    at: dict[Point, list[tuple[SymbolInstance, SymbolPin, int]]] = defaultdict(list)
    unknown: set[Point] = set()
    for instance in sheet.symbols:
        definition = known.get(instance.lib_name or instance.lib_ref)
        if definition is None or definition.extends:
            # the pins of a derived symbol are not known here; a power symbol has its pin at its origin
            unknown.add(instance.position)
            continue
        if left_out(instance):
            continue
        frame = ((instance.rotation // 1_000_000) % 360, instance.mirror)
        for pin in definition.pins_of(instance.unit, instance.body_style):
            point = schlayout.pin_point(instance.position, pin.position, *frame)
            at[point].append((instance, pin, definition.unit_count))
    found: list[tuple[SymbolInstance, list[SymbolPin], bool, int]] = []
    for point, group in at.items():
        pins = [pin for _instance, pin, _count in group]
        if len(pins) < 2 or len({id(instance) for instance, _pin, _count in group}) != 1:
            continue
        if len({pin.name for pin in pins}) != 1 or len({pin.number for pin in pins}) != len(pins):
            continue
        if any(pin.hidden and pin.etype == "power_in" for pin in pins):
            continue
        if point in labels or point in unknown or any(_on(point, a, b) for a, b in segments):
            continue
        found.append((group[0][0], pins, point in flags, group[0][2]))
    return found


@pytest.mark.parametrize("row", ROOTS, ids=lambda r: r.id)
def test_stacks_of_a_demo_project(row: _schcorpus.SchRow, tmp_path: Path) -> None:
    running = major()
    if row.id not in {r.id for r in _schprojects.roots(running)}:
        pytest.skip(f"no project at tag {_schprojects.MAJOR_TAGS[running]}")
    require(next(i for i in manifest_items("sch") if i.id == row.id))
    if not _schprojects.loadable(row, running):
        pytest.skip(f"a sheet of the project is newer than KiCad {running} reads")
    root = _schprojects.project_folder(tmp_path, row, running)
    assert root is not None
    stem = PurePosixPath(row.path).stem
    files = [path for path in _schcorpus.project_files(root / f"{stem}.kicad_sch") if path.is_file()]
    candidates: list[tuple[str, int, int, str, list[str], bool]] = []
    for file in files:
        sheet = sch.read_schematic(file.read_text(encoding="utf-8"), file=file.name)
        for instance, pins, marked, units in stacks(sheet):
            uses = [use for use in instance.uses if use.project == stem]
            if len(uses) != 1 or not uses[0].ref or uses[0].ref.startswith("#"):
                continue  # a sheet used twice has one reference per use; a power symbol is no component
            numbers = [pin.number for pin in pins]
            candidates.append((uses[0].ref, instance.unit, units, pins[0].name, numbers, marked))
    pinned = PINNED.get((row.id, running))
    if not candidates:
        assert pinned is None, f"{row.id}: {pinned} stacks were judged here before, none is found"
        pytest.skip("the project holds no stack of same-named pins at a point that nothing else touches")
    others = {
        path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }
    nets = _erc.netlist(runner(), f"{stem}.kicad_sch", others)
    net_of = {node: name for name, nodes in nets.items() for node in nodes}
    judged = named = 0
    for ref, unit, units, pin_name, numbers, marked in candidates:
        if any((ref, number) not in net_of for number in numbers):
            continue  # the symbol is not on the board, or the reference is annotated otherwise
        judged += 1
        found = {net_of[(ref, number)] for number in numbers}
        assert len(found) == 1, f"{row.id} {ref} pins {numbers}: KiCad has them on the nets {sorted(found)}"
        (net,) = found
        assert nets[net] == {(ref, number) for number in numbers}, (row.id, ref, numbers, net)
        if netnames.proved(pin_name) and units <= 26:
            named += 1
            wanted = netnames.open_name(
                ref, unit=unit, unit_count=units, pin_name=pin_name, pads=numbers, marked=marked
            )
            assert net == wanted, f"{row.id} {ref} pins {numbers} (marked {marked}): {net} != {wanted}"
    if pinned is not None:
        assert judged == named == pinned, (row.id, judged, named, pinned)
    census(SECTION, row.id, {"major": running, "stacks": len(candidates), "judged": judged, "named": named})
    print(
        f"{row.id}: {len(candidates)} stack(s), {judged} judged, {named} with the name compared, {version()}"
    )
