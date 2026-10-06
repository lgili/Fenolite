# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Cases of change c0064 (capability kicad-oracle, "Assembly tables agree with kicad-cli" and "BOM export
through the package runner"): the ``pos-rows``, ``bom-csv-*`` and ``bom-model-*`` rows of ``_probes.PROBES``.

The placement table of ``fenolite.exports.placement`` under the default template, with DNP parts kept, is
compared with the rows of ``pcb export pos --format csv --units mm --side both`` (``H-K-POS-ROWS``) on
four subjects: the authored board, the blink built for the running major (its ``D1`` is on the bottom),
that blink with its three parts turned to 270°, 180° and 270°, and that blink with ``R1`` marked DNP and
``U1`` left out of position files. The moves and flags are made up for these cases.

The bill of materials is exported with ``KicadCli.export_bom`` from schematics that ``build`` wrote for the
running major (``H-K-BOM-CSV``): the *bill* design, which is the blink with a second resistor of the same
value, a made-up user property ``Bin`` on both resistors and the second one marked DNP; the *units* design
of c0061, whose ``U2`` has three units; and the bill design with ``R1`` taken off the bill in the
schematic. The parts ``kicad-cli`` lists are then compared with the parts of the built model
(``H-K-BOM-MODEL``).
"""

from __future__ import annotations

import csv
import dataclasses
import io
import tempfile
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

import _lenscases as lc
import _placecases as pc
from _boards import FIXTURE
from _buildhelp import BLINK, BLINK_DIR, resolver
from _schbuild import built_units, design_of

from fenolite.backends.kicad import bom as kicad_bom
from fenolite.backends.kicad.cli import BOM, CliRun, KicadCli
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import footprint_ref, move_footprint
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.units import parse_angle, parse_length
from fenolite.dsl import placements, to_model
from fenolite.exports import bom, placement
from fenolite.exports.assembly import DEFAULT, FULL_TURN, PlacementTemplate, format_length
from fenolite.lens.build import BuildOutput, build_design
from fenolite.model.board import FootprintAttribute
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
Files = dict[str, str | bytes]
HEADER = ["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"]
TURNS: Mapping[str, int] = {"U1": 270_000_000, "D1": 270_000_000, "R1": 180_000_000}
"""The turned blink: ``U1`` (top) and ``D1`` (bottom) at 270°, ``R1`` at 180°."""
FLAGS: Mapping[str, FootprintAttribute] = {"R1": "dnp", "U1": "exclude_from_pos_files"}
"""The flagged blink: one part marked DNP and one left out of position files."""
SUBJECTS = ("fixture", "blink", "turned", "flagged")
KEEP_DNP: PlacementTemplate = dataclasses.replace(DEFAULT.placement, exclude_dnp=False)
"""The default template with DNP parts kept, which is what ``pcb export pos`` lists without an option."""


def runner() -> KicadCli:
    from _probes import runner as probes_runner  # _probes imports this module

    return probes_runner()


def major() -> int:
    return runner().major()


@cache
def flagged_files(target: int) -> Files:
    """The built blink of ``target`` with the attributes of ``FLAGS`` added to its footprints."""
    files = dict(lc.built_files(target))
    design = read_board(lc.text_of(files), file=lc.BOARD)
    assert design.board is not None
    footprints = tuple(
        dataclasses.replace(fp, attributes=(*fp.attributes, FLAGS[ref]))
        if (ref := footprint_ref(design, fp)) in FLAGS
        else fp
        for fp in design.board.footprints
    )
    flagged = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    files[lc.BOARD] = write_board(flagged, target=target).text
    return files


@cache
def turned_files(target: int) -> Files:
    """The built blink of ``target`` with the rotations of ``TURNS``."""
    files = dict(lc.built_files(target))
    design = read_board(lc.text_of(files), file=lc.BOARD)
    known = pc.definitions(design, target)
    for ref, rotation in TURNS.items():
        footprint = pc.by_ref(design)[ref]
        design = move_footprint(design, footprint.id, rotation=rotation, definitions=known, force=True)
    files[lc.BOARD] = write_board(design, target=target).text
    return files


@cache
def subject(name: str) -> tuple[Design, str]:
    """``(the design Fenolite reads, the position CSV kicad-cli writes)`` for one subject."""
    if name == "fixture":
        return read_board(FIXTURE), runner().export_pos_csv(FIXTURE)
    target = major()
    files = {"blink": lc.built_files, "turned": turned_files, "flagged": flagged_files}[name](target)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for rel, data in files.items():
            path = folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        design = read_board(folder / lc.BOARD)
    return design, pc.pos_text(files)


def kicad_rows(text: str) -> list[dict[str, str]]:
    """The rows of a position CSV as ``kicad-cli`` spells them, keyed by its header."""
    reader = csv.DictReader(io.StringIO(text))
    assert reader.fieldnames == HEADER, reader.fieldnames
    return [{key: value.strip() for key, value in row.items()} for row in reader]


def model_rows(design: Design) -> tuple[tuple[placement.PlacedRow, ...], tuple[tuple[str, ...], ...]]:
    """The placed rows of ``design`` under the default template with DNP kept, and their cells."""
    rows = placement.apply(placement.rows_from_model(design), KEEP_DNP, outline=board_outline(design))
    return rows, placement.table(rows, KEEP_DNP)


def row_problems(name: str) -> list[str]:
    """What differs between Fenolite's placement table and KiCad's position file for one subject."""
    design, text = subject(name)
    exported = {row["Ref"]: row for row in kicad_rows(text)}
    rows, cells = model_rows(design)
    problems: list[str] = []
    if sorted(exported) != sorted(row.ref for row in rows):
        problems.append(f"{name}: KiCad lists {sorted(exported)}, Fenolite {sorted(r.ref for r in rows)}")
    for row, cell in zip(rows, cells, strict=True):
        found = exported.get(row.ref)
        if found is None:
            continue
        ref, value, package, x, y, rotation, side = cell
        kicad_x = parse_length(found["PosX"], default_unit="mm")
        kicad_y = parse_length(found["PosY"], default_unit="mm")
        kicad_turn = parse_angle(found["Rot"], default_unit="deg") % FULL_TURN
        wanted = (
            found["Ref"],
            found["Val"],
            found["Package"],
            format_length(kicad_x, "mm", KEEP_DNP.decimals),
            format_length(kicad_y, "mm", KEEP_DNP.decimals),
            found["Side"],
        )
        if (ref, value, package, x, y, side) != wanted:
            problems.append(f"{name} {row.ref}: Fenolite {cell}, KiCad {tuple(found.values())}")
        if abs(row.x - kicad_x) >= 1_000 or abs(row.y - kicad_y) >= 1_000:
            problems.append(f"{name} {row.ref}: off by a micrometre or more")
        if row.rotation != kicad_turn or parse_angle(rotation, default_unit="deg") != kicad_turn:
            problems.append(f"{name} {row.ref}: rotation {rotation}, KiCad {found['Rot']}")
    return problems


def spelled_rotations(name: str) -> dict[str, tuple[str, str]]:
    """``reference → (the rotation Fenolite prints, the rotation KiCad prints)`` for one subject."""
    design, text = subject(name)
    exported = {row["Ref"]: row["Rot"] for row in kicad_rows(text)}
    rows, cells = model_rows(design)
    column = [c.field for c in KEEP_DNP.columns].index("rotation")
    return {row.ref: (cell[column], exported[row.ref]) for row, cell in zip(rows, cells, strict=True)}


def pos_rows_outcome() -> str:
    return "equal" if not any(row_problems(name) for name in SUBJECTS) else "different"


# --- the bill of materials (H-K-BOM-CSV, H-K-BOM-MODEL) -------------------------------------------

BIN = "Bin"
"""A user property made up for these cases."""
BILL_R1 = ('value="330")', f'value="330", properties={{"{BIN}": "A7"}})')
BILL_EXTRA = f"""
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="330", properties={{"{BIN}": "A7"}})
design.add(r2)
connect(led_drv, r2[1])
connect(led_a, r2[2])
r2.place(mm(32), mm(14))
"""
DNP_REF = "R2"
OFF_BILL_REF = "R1"
UNKNOWN_FIELD = "Shelf"
"""A field that no symbol of the cases has."""
PROBE_FIELDS = kicad_bom.bom_fields((BIN, UNKNOWN_FIELD))
MODEL_FIELDS = kicad_bom.bom_fields((BIN, "fenolite.path"))
"""The fields of the model comparison: a user property and the property every built component has."""
BOM_DESIGNS = ("bill", "units")


@cache
def bom_output(name: str, target: int) -> BuildOutput:
    """The build of the bill design (the blink with ``R2``, ``Bin`` and a DNP mark) or of the units design."""
    if name == "units":
        return built_units(target)
    text = BLINK.read_text(encoding="utf-8")
    assert BILL_R1[0] in text
    design = design_of(text.replace(*BILL_R1) + BILL_EXTRA)
    model = to_model(design)
    components = tuple(dataclasses.replace(c, dnp=c.ref == DNP_REF) for c in model.circuit.components)
    model = dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, components=components))
    output = build_design(
        model,
        placements(design),
        name=design.name,
        copper=design.copper,  # type: ignore[arg-type]
        resolver=resolver(target, BLINK_DIR, None, None),
        target=target,
    )
    assert output.files, [i.message for i in output.issues if i.severity == "error"]
    return output


def schematic_name(name: str) -> str:
    files = bom_output(name, major()).files
    return next(rel for rel in files if rel.endswith(".kicad_sch") and "/" not in rel)  # the root sheet


def off_bill(text: str, ref: str) -> str:
    """The schematic ``text`` with the symbol ``ref`` marked as not in the bill of materials."""
    root = parse(text)
    children: list[Node | Atom] = []
    hits = 0
    for child in root.children:
        if isinstance(child, Node) and child.name == "symbol":
            names = {p.atoms()[0].value: p.atoms()[1].value for p in child.nodes("property")}
            if names.get("Reference") == ref:
                flag = child.find("in_bom")
                assert flag is not None
                parts = list(child.children)
                parts[parts.index(flag)] = parse("(in_bom no)")
                child = child.with_children(parts)
                hits += 1
        children.append(child)
    assert hits >= 1, ref
    return dumps(root.with_children(children))


def write_project(name: str, folder: Path, *, without: str = "", cache: bool = False) -> Path:
    """The built files of ``name`` under ``folder`` (``.fenolite/`` only with ``cache``), with the symbol
    ``without`` taken off the bill in the schematic; returns the schematic's path."""
    schematic = schematic_name(name)
    for rel, data in bom_output(name, major()).files.items():
        if rel.startswith(".fenolite/") and not cache:
            continue
        if rel == schematic and without:
            data = off_bill(data.decode("utf-8"), without).encode("utf-8")
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return folder / schematic


@cache
def exported(name: str, fields: tuple[str, ...], without: str = "") -> CliRun:
    """``KicadCli.export_bom`` on the built schematic of ``name``, with the rest of the project next to it."""
    with tempfile.TemporaryDirectory() as tmp:
        schematic = write_project(name, Path(tmp), without=without)
        others = {p.name: p for p in Path(tmp).iterdir() if p.name != schematic.name}
        return runner().export_bom(schematic, fields=fields, files=others)


def bom_text(name: str, fields: tuple[str, ...] = PROBE_FIELDS, without: str = "") -> str:
    run = exported(name, fields, without)
    assert run.ok and BOM in run.outputs, run.stderr
    return run.outputs[BOM].decode("utf-8")


def raw_rows(text: str) -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(text, newline="")) if row]


def kicad_parts(name: str, fields: tuple[str, ...] = MODEL_FIELDS) -> tuple[bom.BomPart, ...]:
    """The parts ``kicad-cli`` lists for a built design, read with the product's reader."""
    return bom.parts_from_kicad(kicad_bom.read_bom_csv(bom_text(name, fields), fields=fields))


def model_parts(name: str) -> tuple[bom.BomPart, ...]:
    """The parts of the ``.fenolite/`` model that the build of ``name`` wrote."""
    with tempfile.TemporaryDirectory() as tmp:
        write_project(name, Path(tmp), cache=True)
        return bom.parts_from_model(load_dir(Path(tmp) / ".fenolite"))


def source_problems(name: str) -> list[str]:
    """What differs between the parts of the model and the parts ``kicad-cli`` lists, for the fields of
    ``MODEL_FIELDS``."""
    asked = set(MODEL_FIELDS[len(kicad_bom.BASE_FIELDS) :])
    from_kicad = {part.ref: part for part in kicad_parts(name)}
    from_model = {part.ref: part for part in model_parts(name)}
    problems: list[str] = []
    if sorted(from_kicad) != sorted(from_model):
        problems.append(f"{name}: KiCad lists {sorted(from_kicad)}, the model {sorted(from_model)}")
    for ref in sorted(set(from_kicad) & set(from_model)):
        theirs, mine = from_kicad[ref], from_model[ref]
        named = {key: value for key, value in mine.properties.items() if key in asked and value}
        same = (mine.value, mine.footprint, mine.dnp, mine.description, mine.datasheet, named) == (
            theirs.value, theirs.footprint, theirs.dnp, theirs.description, theirs.datasheet,
            dict(theirs.properties),
        )  # fmt: skip
        if not same:
            problems.append(f"{name} {ref}: the model has {mine}, KiCad {theirs}")
    return problems


def _outcome(holds: bool) -> str:
    return "equal" if holds else "different"


def header_outcome() -> str:
    """The header is the labels, which are the fields."""
    return _outcome(all(raw_rows(bom_text(name))[0] == list(PROBE_FIELDS) for name in BOM_DESIGNS))


def rows_outcome() -> str:
    """One row per reference: the two resistors of one value are on two rows."""
    refs = [row[0] for row in raw_rows(bom_text("bill"))[1:]]
    return _outcome(sorted(refs) == ["D1", "R1", "R2", "U1"])


def units_outcome() -> str:
    """The three-unit ``U2`` is on one row."""
    refs = [row[0] for row in raw_rows(bom_text("units"))[1:]]
    return _outcome(sorted(refs) == ["D1", "R1", "U2"])


def dnp_outcome() -> str:
    """The DNP part has ``DNP`` in its cell, and every other part an empty cell."""
    column = PROBE_FIELDS.index(kicad_bom.DNP_FIELD)
    cells = {row[0]: row[column] for row in raw_rows(bom_text("bill"))[1:]}
    return _outcome(cells == {"D1": "", "R1": "", DNP_REF: "DNP", "U1": ""})


def left_out_outcome() -> str:
    """No power flag is listed, and a symbol taken off the bill is not listed either."""
    plain = [row[0] for row in raw_rows(bom_text("bill"))[1:]]
    edited = [row[0] for row in raw_rows(bom_text("bill", without=OFF_BILL_REF))[1:]]
    flags = [ref for ref in (*plain, *edited) if ref.startswith("#")]
    return _outcome(not flags and OFF_BILL_REF in plain and sorted(edited) == ["D1", "R2", "U1"])


def unknown_field_outcome() -> str:
    """A field that no symbol has is an empty column, and the run exits 0."""
    run = exported("bill", PROBE_FIELDS)
    column = PROBE_FIELDS.index(UNKNOWN_FIELD)
    cells = [row[column] for row in raw_rows(bom_text("bill"))[1:]]
    return _outcome(run.returncode == 0 and cells == [""] * 4)


def assembly_probes() -> Probes:
    both = (9, 10)
    return {
        "pos-rows": (pos_rows_outcome, both),
        "bom-csv-header": (header_outcome, both),
        "bom-csv-rows": (rows_outcome, both),
        "bom-csv-units": (units_outcome, both),
        "bom-csv-dnp": (dnp_outcome, both),
        "bom-csv-left-out": (left_out_outcome, both),
        "bom-csv-unknown-field": (unknown_field_outcome, both),
        "bom-model-blink": (lambda: _outcome(not source_problems("bill")), both),
        "bom-model-units": (lambda: _outcome(not source_problems("units")), both),
    }


__all__ = [
    "BIN",
    "BOM_DESIGNS",
    "DNP_REF",
    "FLAGS",
    "HEADER",
    "KEEP_DNP",
    "MODEL_FIELDS",
    "OFF_BILL_REF",
    "PROBE_FIELDS",
    "SUBJECTS",
    "TURNS",
    "UNKNOWN_FIELD",
    "assembly_probes",
    "bom_output",
    "bom_text",
    "exported",
    "kicad_parts",
    "kicad_rows",
    "model_parts",
    "model_rows",
    "off_bill",
    "pos_rows_outcome",
    "raw_rows",
    "row_problems",
    "schematic_name",
    "source_problems",
    "spelled_rotations",
    "subject",
    "write_project",
]
