# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0070 (capability kicad-oracle, "Hierarchy and wire facts are probed" and
"Hierarchical schematics pass the oracles"): the ``sch-hier-*`` and ``sch-wire-*`` rows of
``_probes.PROBES``.

The fact probes run on sheets written here by hand for Fenolite, with the smallest token set both majors
load, so they measure KiCad and not Fenolite's writer: a root that names a child in ``sheets/``, which
names a grandchild, each with one resistor of the authored CC0 mini library; and a flat sheet with two
resistors joined by one wire. The oracle probes run on projects that ``build`` wrote.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _erc
import _gencases as gen
import _gendesigns
from _buildhelp import ROOT, build

from fenolite.backends.kicad import netlist as netlistmod
from fenolite.backends.kicad import sch, sch_netlist, schlayout
from fenolite.backends.kicad.cli import NETLIST
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind
from fenolite.core.coords import Point
from fenolite.dsl import Design
from fenolite.lens.build import BuildOutput

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
PROJECT = "probe"
ROOT_FILE = f"{PROJECT}.kicad_sch"
R1_AT = Point(50_800_000, 50_800_000)
R2_AT = Point(76_200_000, 50_800_000)
R3_AT = Point(63_500_000, 76_200_000)
BOX_AT = Point(101_600_000, 50_800_000)
SEED = _gendesigns.MODULE_SEED
COUNT = _gendesigns.COUNT
LIBRARY = "lib_symbol_issues"
ACCEPTANCE = ROOT / "tests" / "data" / "lens" / "acceptance" / "design.py"


def major() -> int:
    return gen.major()


# -- hand-written sheets


@cache
def r_pins() -> Mapping[str, Point]:
    """The library positions of the two pins of ``Mini_R``."""
    (definition,) = sch.read_schematic(gen.hand_sheet(10, [gen.mini("Mini_R")], [])).lib_symbols
    return {pin.number: pin.position for pin in definition.pins}


def pin_at(origin: Point, number: str) -> Point:
    return schlayout.pin_point(origin, r_pins()[number])


def _symbol(sheet: str, ref: str, at: Point, path: str) -> str:
    font, hidden = gen.FONT, gen.HIDDEN
    x, y = gen.mm(at.x), gen.mm(at.y)
    pins = " ".join(f'(pin "{n}" (uuid "{gen.uid(sheet, ref, "pin", n)}"))' for n in ("1", "2"))
    return (
        f'(symbol (lib_id "Mini:Mini_R") (at {x} {y} 0) (unit 1) (exclude_from_sim no) (in_bom yes) '
        f'(on_board yes) (dnp no) (uuid "{gen.uid(sheet, ref)}") '
        f'(property "Reference" "{ref}" (at {x} {y} 0) {font}) '
        f'(property "Value" "v" (at {x} {y} 0) {hidden}) '
        f'(property "Footprint" "" (at {x} {y} 0) {hidden}) '
        f'(property "Datasheet" "" (at {x} {y} 0) {hidden}) '
        f"{pins} "
        f'(instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit 1)))))'
    )


def _label(sheet: str, index: int, text: str, at: Point) -> str:
    return (
        f'(global_label "{text}" (shape passive) (at {gen.mm(at.x)} {gen.mm(at.y)} 0) '
        f'(effects (font (size 1.27 1.27)) (justify left)) (uuid "{gen.uid(sheet, "label", index)}"))'
    )


def _wire(sheet: str, index: int, start: Point, end: Point) -> str:
    return (
        f"(wire (pts (xy {gen.mm(start.x)} {gen.mm(start.y)}) (xy {gen.mm(end.x)} {gen.mm(end.y)})) "
        f'(stroke (width 0) (type default)) (uuid "{gen.uid(sheet, "wire", index)}"))'
    )


def _box(sheet: str, name: str, file: str, path: str, page: str) -> str:
    """A sheet symbol without pins, named ``name``, whose file is written as ``file``."""
    x, y = gen.mm(BOX_AT.x), gen.mm(BOX_AT.y)
    return (
        f"(sheet (at {x} {y}) (size 25.4 12.7) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) "
        f'(stroke (width 0) (type solid)) (fill (color 0 0 0 0.0)) (uuid "{gen.uid(sheet, "sheet", name)}") '
        f'(property "Sheetname" "{name}" (at {x} {gen.mm(BOX_AT.y - 1_270_000)} 0) '
        f"(effects (font (size 1.27 1.27)) (justify left))) "
        f'(property "Sheetfile" "{file}" (at {x} {gen.mm(BOX_AT.y + 13_970_000)} 0) '
        f"(effects (font (size 1.27 1.27)) (justify left))) "
        f'(instances (project "{PROJECT}" (path "{path}" (page "{page}")))))'
    )


def _sheet(target: int, sheet: str, items: Sequence[str], *, root: bool) -> str:
    out = [
        f"(kicad_sch (version {FORMAT_VERSIONS[FileKind.SCHEMATIC][target]}) "
        f'(generator "fenolite-tests") (generator_version "{target}.0") (uuid "{gen.uid(sheet, "root")}") '
        '(paper "A4")',
        f"(lib_symbols {gen.mini('Mini_R')})",
        *items,
        '(sheet_instances (path "/" (page "1"))))' if root else ")",
    ]
    return dumps(parse("\n".join(out)))


@dataclass(frozen=True)
class Tree:
    """The files of a hand-written hierarchy and the uuids of its two sheet symbols."""

    files: Mapping[str, str]
    a: str
    b: str


def _resistor(sheet: str, ref: str, path: str) -> list[str]:
    """``ref`` with the global labels ``VCC`` on pin 1 and ``SIG`` on pin 2."""
    return [
        _label(sheet, 1, "VCC", pin_at(R1_AT, "1")),
        _label(sheet, 2, "SIG", pin_at(R1_AT, "2")),
        _symbol(sheet, ref, R1_AT, path),
    ]


def tree(target: int, *, b_file: str) -> Tree:
    """A root with ``R1`` that names ``sheets/a.kicad_sch`` (``R2``), which names its child as ``b_file``
    (``R3`` in ``sheets/b.kicad_sch``). No sheet symbol has a pin: the nets are the global labels."""
    top = f"/{gen.uid('top', 'root')}"
    a, b = gen.uid("top", "sheet", "a"), gen.uid("a", "sheet", "b")
    files = {
        ROOT_FILE: _sheet(
            target,
            "top",
            [*_resistor("top", "R1", top), _box("top", "a", "sheets/a.kicad_sch", top, "2")],
            root=True,
        ),
        "sheets/a.kicad_sch": _sheet(
            target,
            "a",
            [*_resistor("a", "R2", f"{top}/{a}"), _box("a", "b", b_file, f"{top}/{a}", "3")],
            root=False,
        ),
        "sheets/b.kicad_sch": _sheet(target, "b", _resistor("b", "R3", f"{top}/{a}/{b}"), root=False),
    }
    return Tree(files, a, b)


@dataclass(frozen=True)
class Export:
    """``sch export netlist`` of a hand-written project: the exit code, per reference the ``names`` and
    ``tstamps`` of its sheet path, and per net its (reference, pin) pairs."""

    returncode: int | None
    sheets: Mapping[str, tuple[str, str]]
    nets: Mapping[str, frozenset[tuple[str, str]]]
    components: tuple[Node, ...] = ()
    text: str = ""


def _text(node: Node | None, head: str) -> str:
    found = node.find(head) if node is not None else None
    atoms = found.atoms() if found is not None else ()
    return atoms[0].value if atoms else ""


def export_of(files: Mapping[str, str | bytes], schematic: str = ROOT_FILE) -> Export:
    """The netlist that the running ``kicad-cli`` exports for ``schematic``, one of ``files``."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        entries = _erc.tops(files, folder)
        others = {name: path for name, path in entries.items() if name != schematic}
        run = gen.runner().export_netlist(folder / schematic, files=others)
    data = run.outputs.get(NETLIST)
    if data is None:
        return Export(run.returncode, {}, {})
    root = parse(data.decode("utf-8"))
    components = root.find("components")
    comps = tuple(components.nodes("comp")) if components is not None else ()
    sheets = {
        _text(comp, "ref"): (_text(comp.find("sheetpath"), "names"), _text(comp.find("sheetpath"), "tstamps"))
        for comp in comps
    }
    nets: dict[str, set[tuple[str, str]]] = {}
    found = root.find("nets")
    for net in found.nodes("net") if found is not None else ():
        nets.setdefault(_text(net, "name"), set()).update(
            (_text(node, "ref"), _text(node, "pin")) for node in net.nodes("node")
        )
    return Export(
        run.returncode,
        sheets,
        {name: frozenset(nodes) for name, nodes in nets.items()},
        comps,
        data.decode("utf-8"),
    )


def findings(report: _erc.Report) -> dict[str, int]:
    """The ERC violation types of a hand-written project, without ``lib_symbol_issues``: these sheets
    come without a symbol table, which is a fact of c0061 (``H-K-SCH-LIBTABLE``) and none of this change."""
    return {kind: count for kind, count in _erc.types(_erc.violations(report)).items() if kind != LIBRARY}


@cache
def tree_export(b_file: str) -> tuple[Tree, Export, _erc.Report]:
    made = tree(major(), b_file=b_file)
    return made, export_of(made.files), _erc.run_erc(gen.runner(), ROOT_FILE, made.files)


def file_parent_outcome() -> str:
    """``present`` when the grandchild named from its parent's folder is loaded, at ``/a/b/``."""
    _, export, _ = tree_export("b.kicad_sch")
    if export.returncode != 0 or "R1" not in export.sheets:
        return "inconclusive"
    return "present" if export.sheets.get("R3", ("", ""))[0] == "/a/b/" else "absent"


def file_project_outcome() -> str:
    """``absent`` when a grandchild named from the project folder is dropped without any finding."""
    _, export, report = tree_export("sheets/b.kicad_sch")
    if export.returncode != 0 or report.returncode != 0 or not report.loaded or "R2" not in export.sheets:
        return "inconclusive"
    if "R3" in export.sheets:
        return "present"
    return "absent" if not findings(report) else "different"


def global_outcome() -> str:
    """``equal`` when the global labels join the three sheets and the sheet paths are the uuid chains."""
    made, export, report = tree_export("b.kicad_sch")
    if export.returncode != 0 or not report.loaded:
        return "inconclusive"
    refs = ("R1", "R2", "R3")
    joined = all(
        export.nets.get(name) == frozenset((ref, pin) for ref in refs)
        for name, pin in (("VCC", "1"), ("SIG", "2"))
    )
    paths = (
        export.sheets.get("R2", ("", ""))[1] == f"/{made.a}/"
        and export.sheets.get("R3", ("", ""))[1] == f"/{made.a}/{made.b}/"
    )
    return "equal" if joined and paths and not findings(report) else "different"


def wire_sheet(target: int, *, middle: bool) -> str:
    """``R1`` and ``R2`` with their pins 1 joined by one wire that carries the global label ``MID`` at the
    ``R1`` end, and ``COMMON`` on every pin 2; with ``middle`` also ``R3``, whose pin 1 ends in the middle
    of the wire, without a junction."""
    top = f"/{gen.uid('wire', 'root')}"
    start, end = pin_at(R1_AT, "1"), pin_at(R2_AT, "1")
    assert start.y == end.y, "the two resistors share a row, so the wire is horizontal"
    items = [
        _wire("wire", 1, start, end),
        _label("wire", 1, "MID", start),
        _label("wire", 2, "COMMON", pin_at(R1_AT, "2")),
        _label("wire", 3, "COMMON", pin_at(R2_AT, "2")),
        _symbol("wire", "R1", R1_AT, top),
        _symbol("wire", "R2", R2_AT, top),
    ]
    if middle:
        # pin 1 of R3 lands on the wire, half-way between its ends
        origin = Point((start.x + end.x) // 2 - r_pins()["1"].x, start.y + r_pins()["1"].y)
        assert schlayout.pin_point(origin, r_pins()["1"]) == Point((start.x + end.x) // 2, start.y)
        items += [
            _label("wire", 4, "COMMON", schlayout.pin_point(origin, r_pins()["2"])),
            _symbol("wire", "R3", origin, top),
        ]
    return _sheet(target, "wire", items, root=True)


@cache
def wire_export(middle: bool) -> tuple[Export, _erc.Report]:
    files = {ROOT_FILE: wire_sheet(major(), middle=middle)}
    return export_of(files), _erc.run_erc(gen.runner(), ROOT_FILE, files)


def wire_ends_outcome() -> str:
    """``equal`` when the wire joins the pins at its two ends under the label's name, without a finding."""
    export, report = wire_export(False)
    if export.returncode != 0 or not report.loaded:
        return "inconclusive"
    joined = export.nets.get("MID") == frozenset({("R1", "1"), ("R2", "1")})
    return "equal" if joined and not findings(report) else "different"


def wire_middle_outcome() -> str:
    """``absent`` when a pin that ends in the middle of the wire is not on its net."""
    export, _ = wire_export(True)
    if export.returncode != 0 or export.nets.get("MID", frozenset()) < {("R1", "1"), ("R2", "1")}:
        return "inconclusive"
    return "present" if ("R3", "1") in export.nets["MID"] else "absent"


# -- built projects (H-K-SCH-HIER-PATH and the oracles)


def acceptance_design() -> Design:
    """The lens acceptance design of c0069: ``U1`` at the top and the modules ``power`` and ``io``."""
    scope: dict[str, object] = {"__name__": "design"}
    exec(compile(ACCEPTANCE.read_text(encoding="utf-8"), str(ACCEPTANCE), "exec"), scope)  # noqa: S102
    design = scope["design"]
    assert isinstance(design, Design)
    return design


@cache
def built_acceptance(target: int, layout: str = "readable") -> BuildOutput:
    return build(acceptance_design(), target=target, schematic_layout=layout)


@cache
def built_generated(index: int, target: int, layout: str = "readable") -> BuildOutput:
    return build(_gendesigns.design(SEED, index, modules=True), target=target, schematic_layout=layout)


def project_files(output: BuildOutput) -> dict[str, bytes]:
    """The files ``kicad-cli`` needs of a build: everything but the ``.fenolite`` cache."""
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def schematic_name(output: BuildOutput) -> str:
    assert output.schematic is not None
    return f"{output.schematic.sheet.name}.kicad_sch"


def own(output: BuildOutput) -> netlistmod.KicadNetlist:
    generated = output.schematic
    assert generated is not None
    return sch_netlist.own_netlist(generated.sheet, project=generated.sheet.name, children=generated.children)


def kicad_netlist(files: Mapping[str, bytes], schematic: str) -> tuple[netlistmod.KicadNetlist, Export]:
    export = export_of(files, schematic)
    assert export.returncode == 0 and export.text, "kicad-cli wrote no netlist"
    return netlistmod.read_netlist(export.text), export


def footprint_paths(output: BuildOutput) -> dict[str, str]:
    """Reference → the ``path`` of its footprint on the built board."""
    name = schematic_name(output).replace(".kicad_sch", ".kicad_pcb")
    design = read_board(output.files[name].decode("utf-8"), file=name)
    return {c.ref: c.path for c in design.circuit.components}


def netlist_paths(export: Export) -> dict[str, frozenset[str]]:
    """Reference → its sheet path ``tstamps`` joined with each of its own ``tstamps``: a part of several
    units lists the uuid of every unit's symbol, in an order that is KiCad's to choose."""
    found: dict[str, frozenset[str]] = {}
    for comp in export.components:
        stamps = comp.find("tstamps")
        own_stamps = [part for atom in (stamps.atoms() if stamps else ()) for part in atom.value.split()]
        sheet = _text(comp.find("sheetpath"), "tstamps")
        found[_text(comp, "ref")] = frozenset(f"{sheet}{stamp}" for stamp in own_stamps)
    return found


def problems(output: BuildOutput, flat: BuildOutput | None = None) -> list[str]:
    """Everything the oracles hold against a built project: ERC violations, parity findings, netlist
    differences and footprint paths that are not the netlist's.

    A design may leave pins open or a label alone, which ERC reports whatever the sheets look like. So
    with ``flat``, the same design built on one flat sheet (the form c0061 proved), ERC is judged by
    comparison: no violation type may be counted more often than on the flat sheet, which says that the
    sheets and the wires add no finding. (Equal counts cannot be asked: 9.0.9 reports one open pin of
    one generated design on the flat sheet and not on the readable one, with equal netlists.) Without
    ``flat`` there must be no violation at all. Only counts are compared: which pin or label KiCad names
    for a violation differs from run to run."""
    files = project_files(output)
    schematic = schematic_name(output)
    board = schematic.replace(".kicad_sch", ".kicad_pcb")
    found: list[str] = []
    kinds = erc_kinds(files, schematic)
    wanted = erc_kinds(project_files(flat), schematic_name(flat)) if flat is not None else {}
    more = {kind: count for kind, count in kinds.items() if count > wanted.get(kind, 0)}
    if more:
        found.append(f"erc: {more} of {kinds}, and the flat sheet has {wanted}")
    parity = _erc.run_parity(gen.runner(), board, files)
    found += [f"parity: {item.get('type')}: {item.get('description')}" for item in _erc.parity(parity)]
    theirs, export = kicad_netlist(files, schematic)
    found += [f"netlist: {line}" for line in netlistmod.differences(own(output), theirs)]
    ours = footprint_paths(output)
    for ref, paths in sorted(netlist_paths(export).items()):
        if ours.get(ref) not in paths:
            found.append(f"path: {ref}: the board has {ours.get(ref)!r}, the netlist gives {sorted(paths)}")
    return found


def edited_file(output: BuildOutput, name: str, old: str, new: str) -> dict[str, bytes]:
    """The project files of ``output`` with ``old`` replaced once by ``new`` in the file ``name``."""
    files = project_files(output)
    text = files[name].decode("utf-8")
    assert text.count(old) == 1, (name, old, text.count(old))
    files[name] = text.replace(old, new).encode("utf-8")
    return files


def without_first_wire(output: BuildOutput, name: str) -> dict[str, bytes]:
    """The project files of ``output`` without the first wire of the sheet file ``name``."""
    files = project_files(output)
    root = parse(files[name].decode("utf-8"))
    wires = root.nodes("wire")
    assert wires, f"{name} holds no wire"
    kept = [child for child in root.children if child is not wires[0]]
    files[name] = dumps(root.with_children(kept)).encode("utf-8")
    return files


def erc_kinds(files: Mapping[str, bytes], schematic: str) -> dict[str, int]:
    """The ERC violation types of a built project, counted; never the items, which KiCad names at will."""
    report = _erc.run_erc(gen.runner(), schematic, files)
    assert report.loaded, report.stderr
    return dict(_erc.types(_erc.violations(report)))


def acceptance_outcome() -> str:
    found = problems(built_acceptance(major()), built_acceptance(major(), "grid"))
    return "equal" if not found else "different"


@cache
def generated_problems(index: int) -> tuple[str, ...]:
    return tuple(problems(built_generated(index, major()), built_generated(index, major(), "grid")))


def generated_stats() -> tuple[int, int]:
    """The child sheets and the snapped satellites of the generated designs, summed."""
    outputs = [built_generated(index, major()) for index in range(COUNT)]
    sheets = sum(len(o.schematic.children) for o in outputs if o.schematic is not None)
    satellites = sum(o.schematic.satellites for o in outputs if o.schematic is not None)
    return sheets, satellites


def generated_outcome() -> str:
    for index in range(COUNT):
        if generated_problems(index):
            return "different"
    sheets, satellites = generated_stats()
    return "equal" if sheets and satellites else "inconclusive"


def hier_probes() -> Probes:
    both = (9, 10)
    return {
        "sch-hier-file-parent": (file_parent_outcome, both),
        "sch-hier-file-project": (file_project_outcome, both),
        "sch-hier-global": (global_outcome, both),
        "sch-wire-ends": (wire_ends_outcome, both),
        "sch-wire-middle": (wire_middle_outcome, both),
        "sch-hier-oracle-acceptance": (acceptance_outcome, both),
        "sch-hier-oracle-generated": (generated_outcome, both),
    }


__all__ = ["hier_probes"]
