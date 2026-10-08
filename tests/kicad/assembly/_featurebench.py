# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assembly and test benches of the oracle (capability kicad-oracle: "Assembly and test pad properties
are probed", "Assembly and test features pass the oracle", "Test-point report agrees with IPC-D-356";
change c0118; hypotheses ``H-K-PAD-FABPROP``, ``-LIB``, ``H-K-FIDUCIAL-FORM``, ``H-K-FIDUCIAL-KEEPOUT`` and
``H-K-TESTPOINT-D356``).

Three subjects, all with authored round sizes:

- the *marks* bench: a created two-layer board written by ``write_board`` with one footprint per pad mark,
  whose ``(property pad_prop_…)`` children are added by token edit, so that the facts do not depend on the
  writer under test; the *written* bench sets the same marks through the model;
- the *features* bench, written through the model API: a fiducial of two unnumbered pads on each side, a
  keep-out octagon around the top one, and four test pads (top, bottom, through-hole, and a top pad
  without a mask layer), each on its own net;
- the *library* subjects: the blink built with the authored parts of ``_asmfeatures`` (their vendored
  footprint files carry the marks), and the plain blink with a mark added to a placed library copy.

The features bench holds the footprints that the script calls of the change (``design.fiducial()``,
``design.test_point()``, ``design.tooling_hole()``) generate, less the courtyard, which a placed footprint
cannot hold in the model. Building the bench from a script with those calls (``_asmfeatures.CALLS``), and
the probes ``asm-tooling-drill`` and ``asm-features-pos``, are task 3.6, owed to a run with ``kicad-cli``.

What KiCad does is read from its outputs: the aperture function of a pad is the ``.AperFunction`` of the
aperture its flash uses in the copper plot; a mask opening is a flash in the mask plot.
"""

from __future__ import annotations

import dataclasses
import math
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction
from functools import cache
from pathlib import Path

import _lenscases as lc
from _asmfeatures import features_design
from _buildhelp import build

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad import frame
from fenolite.backends.kicad._fpmap import FAB_PROPERTY_TOKENS
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.ipcd356 import Ipcd356Record, read_ipcd356
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.dsl.assembly import clear_outline
from fenolite.exports import testpoints
from fenolite.model.board import (
    Board,
    FootprintAttribute,
    FootprintInstance,
    Keepout,
    Outline,
    Pad,
    PadFabProperty,
    PadKind,
    Side,
    Track,
    Zone,
)
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]
MAJORS: tuple[int, ...] = (10,)
"""The majors the probes of this module are recorded for. The 9.0.9 outcomes need a run inside the pinned
image (``FENOLITE_PROBES_WRITE=1``); until that run, ``docs/evidence/kicad/probes/9.0.9.json`` holds none
of them and the rows of ``docs/hypotheses.md`` stay ``INFERRED``."""
TEN_ONLY = frozenset({"pad-fabprop-resave", "asm-keepout-fill"})
"""The probes of KiCad 10 alone: ``pcb upgrade`` and the refill of zones are 10.0 commands."""
STEM = "featurebench"
PROJECT = "{}\n"
MM = 1_000_000
LIBRARY_TYPES = frozenset({"lib_footprint_issues", "lib_footprint_mismatch"})
"""What DRC says about a footprint whose library is not in a table: the model benches name no library."""
TOP, BOTTOM = ("F.Cu", "F.Mask"), ("B.Cu", "B.Mask")
THROUGH = ("F.Cu", "B.Cu", "F.Mask", "B.Mask")

FUNCTIONS: Mapping[PadFabProperty, str] = {
    "bga": "BGAPad,CuDef",
    "fiducial_global": "FiducialPad,Global",
    "fiducial_local": "FiducialPad,Local",
    "test_point": "TestPad",
    "heatsink": "HeatsinkPad",
    "castellated": "CastellatedPad",
    "mechanical": "SMDPad,CuDef",
    "press_fit": "ComponentPad",
}
"""The aperture function of the copper flash of a marked pad (``docs/formats/kicad/board.md``): ``mechanical``
on an SMD pad and ``press_fit`` on a through-hole pad keep the function of an unmarked pad."""
THROUGH_MARKS = frozenset({"castellated", "press_fit"})
"""The marks the marks bench puts on a plated through-hole pad; the others sit on an SMD pad."""
PADSTACK_MARKS: tuple[PadFabProperty, ...] = ("castellated", "mechanical")


def _id(prefix: str, name: str) -> str:
    return derived_id(prefix, "featurebench", name)


# --- boards ---------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Spot:
    """One footprint of a bench: a name, where it is, and its pads as ``(number, layers, size, kind,
    drill, net, mark)``."""

    name: str
    at: Point
    pads: tuple[tuple[str, tuple[str, ...], int, PadKind, int | None, str, PadFabProperty | None], ...]
    side: Side = "top"
    lib: str = "Bench:Pad"
    attributes: tuple[FootprintAttribute, ...] = ("smd",)


def _design(
    spots: Sequence[Spot],
    *,
    name: str,
    tracks: Sequence[tuple[Point, Point, str]] = (),
    keepouts: Sequence[Keepout] = (),
    zones: Sequence[tuple[str, str]] = (),
) -> Design:
    names = sorted({pad[5] for spot in spots for pad in spot.pads if pad[5]} | {t[2] for t in tracks})
    names = sorted(set(names) | {net for net, _ in zones})
    nets = {n: Net(id=_id("net", n), name=n) for n in names}
    footprints = tuple(
        FootprintInstance(
            id=_id("fp", f"{name}:{spot.name}"),
            component_id="",
            lib_ref=spot.lib,
            position=spot.at,
            side=spot.side,
            attributes=spot.attributes,
            pads=tuple(
                Pad(
                    id=_id("pad", f"{name}:{spot.name}:{k}"),
                    number=number,
                    shape="circle",
                    size=Size(size, size),
                    position=Point(0, 0),
                    kind=kind,
                    drill=drill,
                    layers=layers,
                    net_id=nets[net].id if net else None,
                    fab_property=mark,
                )
                for k, (number, layers, size, kind, drill, net, mark) in enumerate(spot.pads)
            ),
        )
        for spot in spots
    )
    corners = (Point(0, 0), Point(50 * MM, 0), Point(50 * MM, 30 * MM), Point(0, 30 * MM))
    board = Board(
        id=_id("brd", name),
        outline=Outline(id=_id("out", name), points=corners),
        layers=created_layers(2),
        footprints=footprints,
        tracks=tuple(
            Track(
                id=_id("trk", f"{name}:{k}"), start=a, end=b, width=200_000, layer="F.Cu", net_id=nets[n].id
            )
            for k, (a, b, n) in enumerate(tracks)
        ),
        keepouts=tuple(keepouts),
        zones=tuple(
            Zone(
                id=_id("zon", f"{name}:{layer}"),
                outline=tuple(
                    Point(p.x + (MM if p.x == 0 else -MM), p.y + (MM if p.y == 0 else -MM)) for p in corners
                ),
                name=f"{net}_POUR",
                layers=(layer,),
                net_id=nets[net].id,
            )
            for net, layer in zones
        ),
    )
    design = Design.new(STEM, seed=118)
    return dataclasses.replace(design, circuit=Circuit(nets=tuple(nets.values())), board=board)


def mark_spots(marks: Mapping[str, PadFabProperty | None], *, through: frozenset[str]) -> tuple[Spot, ...]:
    """One footprint per entry of ``marks``, 5 mm apart on a row; a name in ``through`` gets a plated
    through-hole pad (1.6 mm with a 0.8 mm drill), every other one an SMD pad of 1 mm."""
    spots: list[Spot] = []
    for k, (name, mark) in enumerate(marks.items()):
        at = Point((5 + 5 * k) * MM, 15 * MM)
        if name in through:
            pad = ("1", THROUGH, 1_600_000, "thru_hole", 800_000, f"N{k}", mark)
            spots.append(Spot(name, at, (pad,), attributes=("through_hole",)))  # type: ignore[arg-type]
        else:
            spots.append(Spot(name, at, (("1", TOP, MM, "smd", None, f"N{k}", mark),)))
    return tuple(spots)


ALL_MARKS: Mapping[str, PadFabProperty] = {value: value for value in FUNCTIONS}


def _with_tokens(text: str, tokens: Sequence[str | None]) -> str:
    """``text`` with ``(property <token>)`` put before the ``layers`` child of the first pad of each
    footprint, in file order (``None`` leaves a footprint as it is)."""
    root = parse(text)
    footprints = root.nodes("footprint")
    assert len(footprints) == len(tokens)
    replaced: dict[int, Node] = {}
    for footprint, token in zip(footprints, tokens, strict=True):
        if token is None:
            continue
        pad = footprint.nodes("pad")[0]
        children = list(pad.children)
        at = next(i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "layers")
        children[at:at] = parse(f"(x (property {token}))").nodes()
        marked = pad.with_children(children)
        replaced[id(footprint)] = footprint.with_children(
            [marked if c is pad else c for c in footprint.children]
        )
    return dumps(root.with_children([replaced.get(id(c), c) for c in root.children]), style="kicad")


@cache
def marks_text(target: int, marked: bool = True, *, written: bool = False) -> str:
    """The marks bench for ``target``: by token edit, or through the model with ``written``; ``press_fit``
    is left out for target 9, whose format has no such token."""
    marks = {k: v for k, v in ALL_MARKS.items() if target >= 10 or v != "press_fit"}
    if written:
        return write_board(
            _design(mark_spots(marks, through=THROUGH_MARKS), name="marks"), target=target
        ).text
    plain = write_board(
        _design(mark_spots(dict.fromkeys(marks), through=THROUGH_MARKS), name="marks"), target=target
    ).text
    return _with_tokens(plain, [FAB_PROPERTY_TOKENS[v] for v in marks.values()]) if marked else plain


@cache
def padstack_text(target: int) -> str:
    """``castellated`` and ``mechanical``, each on an SMD pad and on a through-hole pad."""
    marks: dict[str, PadFabProperty | None] = {
        f"{m}_{kind}": None for m in PADSTACK_MARKS for kind in ("smd", "tht")
    }
    through = frozenset(name for name in marks if name.endswith("_tht"))
    plain = write_board(_design(mark_spots(marks, through=through), name="padstack"), target=target).text
    return _with_tokens(plain, [FAB_PROPERTY_TOKENS[name.rsplit("_", 1)[0]] for name in marks])  # type: ignore[index]


COPPER, MASK, CLEAR = MM, 2 * MM, 3 * MM
"""The fiducials of the features bench: 1 mm of copper, a 2 mm mask opening, a 3 mm clear area."""
FID_TOP, FID_BOTTOM = Point(5 * MM, 5 * MM), Point(45 * MM, 25 * MM)
TEST_PADS: tuple[tuple[str, Point, tuple[str, ...], Side], ...] = (
    ("TP_TOP", Point(10 * MM, 15 * MM), TOP, "top"),
    ("TP_BOTTOM", Point(20 * MM, 15 * MM), BOTTOM, "bottom"),
    ("TP_THROUGH", Point(30 * MM, 15 * MM), THROUGH, "top"),
    ("TP_COVERED", Point(40 * MM, 15 * MM), ("F.Cu",), "top"),
)
ACCESS = ("top", "bottom", "both", "none")
"""The access the report gives the four test pads, in the order of ``TEST_PADS``."""


APOTHEM = -(-CLEAR // 2)


def _fiducial(name: str, at: Point, side: Side) -> Spot:
    copper, mask = (TOP, ("F.Mask",)) if side == "top" else (BOTTOM, ("B.Mask",))
    pads = (
        ("", copper, COPPER, "smd", None, "", "fiducial_global"),
        ("", mask, MASK, "smd", None, "", None),
    )
    return Spot(name, at, pads, side, f"Fenolite_Assembly:Fiducial_{name}", ("smd", "exclude_from_bom"))  # type: ignore[arg-type]


def feature_design(variant: str = "plain") -> Design:
    """The features bench. ``track`` adds a track through the keep-out of the top fiducial, 1.3 mm from its
    centre; ``pour`` adds a ``GND`` zone over the board on ``F.Cu``."""
    spots = [_fiducial("FID_TOP", FID_TOP, "top"), _fiducial("FID_BOTTOM", FID_BOTTOM, "bottom")]
    for k, (name, at, layers, side) in enumerate(TEST_PADS):
        through = layers == THROUGH
        pad = (
            "1", layers, 1_500_000, "thru_hole" if through else "smd", 500_000 if through else None,
            f"NET_{k}", "test_point",
        )  # fmt: skip
        spots.append(
            Spot(
                name,
                at,
                (pad,),
                side,
                "Fenolite_Assembly:TestPoint",
                ("exclude_from_pos_files", "exclude_from_bom"),
            )  # type: ignore[arg-type]
        )
    keepout = Keepout(
        id=_id("kpo", "clear_FID_TOP"),
        outline=clear_outline(FID_TOP.x, FID_TOP.y, CLEAR),
        layers=("F.Cu",),
        no_tracks=True,
        no_vias=True,
        no_copper_pour=True,
    )
    y = FID_TOP.y + 1_300_000
    tracks = [(Point(2 * MM, y), Point(8 * MM, y), "SIG")] if variant == "track" else []
    zones = [("GND", "F.Cu")] if variant == "pour" else []
    return _design(spots, name=f"features-{variant}", tracks=tracks, keepouts=(keepout,), zones=zones)


@cache
def feature_text(target: int, variant: str = "plain") -> str:
    return write_board(feature_design(variant), target=target).text


# --- kicad-cli runs -------------------------------------------------------------------------------


def _files(tmp: str, text: str) -> tuple[Path, dict[str, Path]]:
    board = Path(tmp) / f"{STEM}.kicad_pcb"
    board.write_text(text, encoding="utf-8", newline="\n")
    project = board.with_suffix(".kicad_pro")
    project.write_text(PROJECT, encoding="utf-8")
    return board, {project.name: project}


_APERTURE = re.compile(r"ADD(\d+)")
_SELECT = re.compile(r"(?:G54)?D(\d+)")
_FLASH = re.compile(r"(?:G0?[123])?(?:X([+-]?\d+))?(?:Y([+-]?\d+))?D0?([123])")
_CIRCLE = re.compile(r"ADD(\d+)C,([0-9.]+)")
Flash = tuple[int, int, str, str]


def flashes(text: str) -> list[Flash]:
    """``(x, y, aperture function, aperture template)`` of every flash of a Gerber plot, in nanometres in
    the plot's own axes (its Y values are the board's negated). The function is the ``.AperFunction``
    attribute in force when the aperture was defined, ``""`` without one; the template is the text after
    the aperture number (``C,1.000000`` for a 1 mm circle)."""
    commands = [c.strip().strip("%") for c in text.replace("\n", "").replace("\r", "").split("*")]
    if "FSLAX46Y46" not in commands or "MOMM" not in commands:
        raise ValueError("the helper reads only %FSLAX46Y46*% plots in millimetres")
    functions: dict[str, tuple[str, str]] = {}
    attribute, current = "", ""
    x = y = 0
    found: list[Flash] = []
    for command in commands:
        if command.startswith("TA.AperFunction,"):
            attribute = command.split(",", 1)[1]
        elif command == "TD" or command.startswith("TD.AperFunction"):
            attribute = ""
        elif (defined := _APERTURE.match(command)) is not None:
            functions[defined.group(1)] = (attribute, command[defined.end() :])
        elif (selected := _SELECT.fullmatch(command)) is not None and int(selected.group(1)) >= 10:
            current = selected.group(1)
        elif (operation := _FLASH.fullmatch(command)) is not None:
            x = int(operation.group(1)) if operation.group(1) is not None else x
            y = int(operation.group(2)) if operation.group(2) is not None else y
            if operation.group(3) == "3":
                found.append((x, y, *functions.get(current, ("", ""))))
    return found


def plot(cli: KicadCli, text: str, layer: str) -> list[Flash] | None:
    """The flashes of ``pcb export gerbers -l <layer>``; ``None`` when no plot was written."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        run = cli.export(
            ["pcb", "export", "gerbers", "-l", layer, "-o", "out/"], board, files=files, out="out"
        )
    wanted = f"{STEM}-{layer.replace('.', '_')}."
    data = next((d for name, d in run.outputs.items() if wanted in name), None)
    return None if data is None else flashes(data.decode("utf-8"))


def at(found: Sequence[Flash], centre: Point) -> list[Flash]:
    """The flashes at ``centre`` (board frame), to the micrometre."""
    return [f for f in found if abs(f[0] - centre.x) <= 1000 and abs(-f[1] - centre.y) <= 1000]


def drc(cli: KicadCli, text: str) -> DrcReport | None:
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        return cli.drc(board, files=files).report


def d356(cli: KicadCli, text: str) -> tuple[int, tuple[Ipcd356Record, ...]]:
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        export = read_ipcd356(cli.export_ipcd356(board, files=files))
    return export.unit_nm, export.records


def pos(cli: KicadCli, text: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        return cli.export_pos_csv(board, files=files)


def records_at(unit: int, records: Sequence[Ipcd356Record], centre: Point) -> list[Ipcd356Record]:
    """The pad records within two export units of ``centre`` (the export's Y is up)."""
    return [
        r
        for r in records
        if abs(r.x * unit - centre.x) <= 2 * unit and abs(-r.y * unit - centre.y) <= 2 * unit
    ]


def uuids(text: str) -> dict[str, set[str]]:
    """Per footprint of a bench text, in file order under its ``lib_ref`` and position: the uuids of the
    footprint and of its pads."""
    design = read_board(text)
    assert design.board is not None
    out: dict[str, set[str]] = {}
    for fp in design.board.footprints:
        key = f"{fp.lib_ref}@{fp.position.x},{fp.position.y}"
        out[key] = {v for e in (fp, *fp.pads) if (v := e.native_ids.get("kicad")) is not None}
    return out


def naming(report: DrcReport, wanted: set[str]) -> list[DrcViolation]:
    """The violations and unconnected items that name one of the uuids ``wanted``."""
    entries = (*report.violations, *report.unconnected_items)
    return [v for v in entries if any(item.uuid in wanted for item in v.items)]


# --- pad marks ------------------------------------------------------------------------------------


def mark_function(cli: KicadCli, value: PadFabProperty, target: int, *, written: bool = False) -> str | None:
    """The aperture function of the copper flash of the pad marked ``value`` on the marks bench."""
    found = plot(cli, marks_text(target, written=written), "F.Cu")
    if found is None:
        return None
    index = [v for v in ALL_MARKS.values() if target >= 10 or v != "press_fit"].index(value)
    here = at(found, Point((5 + 5 * index) * MM, 15 * MM))
    return here[0][2] if len(here) == 1 else None


def targets(cli: KicadCli) -> tuple[int, ...]:
    """The targets the running major loads."""
    return (9, 10) if cli.major() >= 10 else (9,)


def fabprop(cli: KicadCli, value: PadFabProperty) -> str:
    """``pad-fabprop-<value>``: on every target the running major loads, the copper flash of the marked
    pad has the function of ``FUNCTIONS``, from the token-edited bench and from the written one."""
    for target in targets(cli):
        if value == "press_fit" and target < 10:
            continue
        for written in (False, True):
            found = mark_function(cli, value, target, written=written)
            if found is None:
                return "inconclusive"
            if found != FUNCTIONS[value]:
                return "different"
    return "equal"


def _records(text: str) -> list[str]:
    return [line for line in text.splitlines() if line[:3] in ("317", "327")]


def outputs(cli: KicadCli) -> str:
    """``pad-fabprop-outputs``: the position file and the IPC-D-356 records with and without the marks."""
    for target in targets(cli):
        marked, plain = marks_text(target), marks_text(target, False)
        with tempfile.TemporaryDirectory() as tmp:
            board, files = _files(tmp, marked)
            netlist_marked = _records(cli.export_ipcd356(board, files=files))
        with tempfile.TemporaryDirectory() as tmp:
            board, files = _files(tmp, plain)
            netlist_plain = _records(cli.export_ipcd356(board, files=files))
        if not netlist_marked:
            return "inconclusive"
        if pos(cli, marked) != pos(cli, plain) or netlist_marked != netlist_plain:
            return "different"
    return "equal"


def padstack_names(cli: KicadCli, target: int) -> list[str] | None:
    """The spots of the padstack bench that a ``padstack`` violation names, in bench order."""
    text = padstack_text(target)
    report = drc(cli, text)
    if report is None:
        return None
    names = [f"{m}_{kind}" for m in PADSTACK_MARKS for kind in ("smd", "tht")]
    stacks = [v for v in (*report.violations, *report.unconnected_items) if v.type == "padstack"]
    out: list[str] = []
    for name, wanted in zip(names, uuids(text).values(), strict=True):
        if any(item.uuid in wanted for v in stacks for item in v.items):
            out.append(name)
    return out


def padstack(cli: KicadCli) -> str:
    """``pad-fabprop-padstack``: DRC reports ``padstack`` for the two marks on an SMD pad only."""
    for target in targets(cli):
        found = padstack_names(cli, target)
        if found is None:
            return "inconclusive"
        if found != [f"{m}_smd" for m in PADSTACK_MARKS]:
            return "different"
    return "equal"


def resave_keeps(cli: KicadCli) -> str:
    """``pad-fabprop-resave`` (10.0 only): ``pcb upgrade --force`` keeps every mark."""
    text = marks_text(10)
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        saved = parse(cli.upgrade_board(board, files=files).decode("utf-8"))
    found: dict[str, list[str]] = {}
    for fp in saved.nodes("footprint"):
        for pad in fp.nodes("pad"):
            net = pad.find("net")
            heads = [c.name for c in pad.nodes()]
            if net is None or not heads.index("size") < heads.index("property") < heads.index("layers"):
                return "different"  # KiCad writes the child after size or drill and before layers
            found[net.atoms()[-1].value] = [a.value for p in pad.nodes("property") for a in p.atoms()]
    # the re-save orders footprints its own way: each pad is found by its net (N<k>, in bench order)
    wanted = {f"N{k}": [FAB_PROPERTY_TOKENS[v]] for k, v in enumerate(ALL_MARKS.values())}
    return "equal" if found == wanted else "different"


# --- library copies -------------------------------------------------------------------------------


@cache
def authored_files(target: int) -> dict[str, str | bytes]:
    """The blink built with the authored test pad and fiducial marks of ``_asmfeatures``."""
    design = features_design()
    output = build(
        design,
        target,
        authored_footprints={k: v.definition for k, v in design.footprints.items()},
        authored_symbols={k: v.definition for k, v in design.symbols.items()},
    )
    return {rel: data for rel, data in output.files.items() if not rel.startswith(".fenolite/")}


def _mismatches(files: Mapping[str, str | bytes]) -> list[DrcViolation] | None:
    report = lc.drc(files)
    if report is None:
        return None
    return [v for v in (*report.violations, *report.unconnected_items) if v.type == "lib_footprint_mismatch"]


def lib_same(cli: KicadCli) -> str:
    """``pad-fabprop-lib-same``: no ``lib_footprint_mismatch`` for the authored parts, whose vendored
    footprint files carry the marks of their placed copies."""
    del cli
    for target in targets(lc.runner()):
        files = authored_files(target)
        text = lc.text_of(files)
        if text.count("(property pad_prop_") != 3:
            return "inconclusive"
        found = _mismatches(files)
        if found is None:
            return "inconclusive"
        if found:
            return "present"
    return "absent"


def lib_mismatch(cli: KicadCli) -> str:
    """``pad-fabprop-lib-mismatch``: a mark added to the placed copy of a library footprint, whose library
    pad has none, gives ``lib_footprint_mismatch`` for that footprint. The control is the plain build."""
    del cli
    for target in targets(lc.runner()):
        files = dict(lc.built_files(target))
        if _mismatches(files) != []:
            return "inconclusive"
        root = parse(lc.text_of(files))
        footprints = root.nodes("footprint")
        tokens: list[str | None] = [None] * len(footprints)
        tokens[0] = "pad_prop_testpoint"
        files[lc.BOARD] = _with_tokens(lc.text_of(files), tokens)
        found = _mismatches(files)
        if found is None:
            return "inconclusive"
        if len(found) != 1:
            return "absent" if not found else "inconclusive"
    return "present"


# --- features -------------------------------------------------------------------------------------


def _feature_keys(text: str) -> dict[str, set[str]]:
    return {key: ids for key, ids in uuids(text).items() if key.startswith("Fenolite_Assembly:")}


def fiducial_drc(cli: KicadCli) -> str:
    """``asm-fiducial-drc``: no violation names a fiducial or a test pad of the features bench, the
    library checks aside (the bench names no library)."""
    for target in targets(cli):
        text = feature_text(target)
        report = drc(cli, text)
        if report is None:
            return "inconclusive"
        wanted = set().union(*_feature_keys(text).values())
        if [v for v in naming(report, wanted) if v.type not in LIBRARY_TYPES]:
            return "present"
    return "absent"


def fiducial_mask(cli: KicadCli) -> str:
    """``asm-fiducial-mask``: the mask plot of each fiducial's side flashes a circle of the mask diameter
    at its centre."""
    for target in targets(cli):
        for layer, centre in (("F.Mask", FID_TOP), ("B.Mask", FID_BOTTOM)):
            found = plot(cli, feature_text(target), layer)
            if found is None:
                return "inconclusive"
            circles = {f[3] for f in at(found, centre)}
            if f"C,{MASK // MM}.000000" not in circles:
                return "different"
    return "equal"


def fiducial_d356(cli: KicadCli) -> str:
    """``asm-fiducial-d356``: each fiducial's copper pad is one ``327`` record on no net, covered on the
    other side only (``S2`` on the top, ``S1`` on the bottom)."""
    for target in targets(cli):
        unit, records = d356(cli, feature_text(target))
        for centre, side, covered in ((FID_TOP, "top", "bottom"), (FID_BOTTOM, "bottom", "top")):
            found = records_at(unit, records, centre)
            if len(found) != 1:
                return "different"
            record = found[0]
            if (record.code, record.net, record.side, record.covered) != ("327", "N/C", side, covered):
                return "different"
    return "equal"


def keepout_track(cli: KicadCli) -> str:
    """``asm-keepout-track``: a track through the keep-out gives ``items_not_allowed``, and nothing names
    the fiducial's pads; the control is the bench without the track."""
    for target in targets(cli):
        text = feature_text(target, "track")
        report, control = drc(cli, text), drc(cli, feature_text(target))
        if report is None or control is None:
            return "inconclusive"
        if any(v.type == "items_not_allowed" for v in control.violations):
            return "inconclusive"
        fiducial = next(ids for key, ids in _feature_keys(text).items() if "Fiducial_FID_TOP" in key)
        if [v for v in naming(report, fiducial) if v.type not in LIBRARY_TYPES]:
            return "inconclusive"
        if not any(v.type == "items_not_allowed" for v in report.violations):
            return "absent"
    return "present"


def _distance_squared(p: Point, a: Point, b: Point) -> Fraction:
    """The squared distance from ``p`` to the segment ``a``–``b``, exactly."""
    dx, dy = b.x - a.x, b.y - a.y
    length = dx * dx + dy * dy
    if length == 0:
        return Fraction((p.x - a.x) ** 2 + (p.y - a.y) ** 2)
    t = min(Fraction(1), max(Fraction(0), Fraction((p.x - a.x) * dx + (p.y - a.y) * dy, length)))
    x, y = a.x + t * dx, a.y + t * dy
    return (p.x - x) ** 2 + (p.y - y) ** 2


def _inside(p: Point, polygon: Sequence[Point]) -> bool:
    inside = False
    for a, b in zip(polygon, (*polygon[1:], polygon[0]), strict=True):
        if (a.y > p.y) != (b.y > p.y) and Fraction(p.x - a.x) < Fraction(
            (b.x - a.x) * (p.y - a.y), b.y - a.y
        ):
            inside = not inside
    return inside


def fill_gap(cli: KicadCli) -> int | None:
    """The smallest distance, in whole nanometres rounded down, from the top fiducial's centre to the
    refilled ``GND`` pour of the pour variant; ``-1`` when the fill covers the centre and ``None`` when
    the refill gave no fill."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, feature_text(10, "pour"))
        saved = cli.refill(board, files=files).board
    if saved is None:
        return None
    design = read_board(saved.decode("utf-8"))
    assert design.board is not None
    polygons = [fill.polygon for zone in design.board.zones for fill in zone.fills if fill.layer == "F.Cu"]
    if not polygons:
        return None
    if any(_inside(FID_TOP, polygon) for polygon in polygons):
        return -1
    nearest = min(
        _distance_squared(FID_TOP, a, b)
        for polygon in polygons
        for a, b in zip(polygon, (*polygon[1:], polygon[0]), strict=True)
    )
    return math.isqrt(int(nearest))


def keepout_fill(cli: KicadCli) -> str:
    """``asm-keepout-fill`` (10.0 only): no fill lies closer to the fiducial's centre than the apothem of
    its keep-out, less 1 µm."""
    gap = fill_gap(cli)
    if gap is None:
        return "inconclusive"
    return "equal" if gap >= APOTHEM - 1000 else "different"


# --- the report against IPC-D-356 -----------------------------------------------------------------


def report_problems(cli: KicadCli, target: int) -> list[str]:
    """What differs between the rows of ``exports.testpoints.report`` and the IPC-D-356 records of the
    features bench: one record per row within two export units, on its net, whose side less the sides of
    its mask code is the row's access."""
    text = feature_text(target)
    design = read_board(text)
    rows = testpoints.report(design, frame.board_pads(design)).test_points
    unit, records = d356(cli, text)
    problems: list[str] = []
    if len(rows) != len(TEST_PADS):
        problems.append(f"the report lists {len(rows)} test points, the bench holds {len(TEST_PADS)}")
    sides = {"top": {"top"}, "bottom": {"bottom"}, "both": {"top", "bottom"}, "none": set[str]()}
    for row in rows:
        found = records_at(unit, records, row.position)
        if len(found) != 1:
            problems.append(f"{row.net}: {len(found)} records at its position")
            continue
        record = found[0]
        if record.net != row.net:
            problems.append(f"{row.net}: the record is on {record.net!r}")
        copper = {name for name, layer in (("top", "F.Cu"), ("bottom", "B.Cu")) if _has(design, row, layer)}
        if sides.get(record.side) != copper:
            problems.append(f"{row.net}: side {record.side!r}, copper on {sorted(copper)}")
        left = copper - sides.get(record.covered or "", set())
        if left != sides[row.access]:
            problems.append(f"{row.net}: access {row.access!r}, the record leaves {sorted(left)} open")
    return problems


def _has(design: Design, row: testpoints.TestPointRow, layer: str) -> bool:
    assert design.board is not None
    return any(
        layer in pad.layers
        for fp in design.board.footprints
        if fp.position == row.position
        for pad in fp.pads
    )


def mask_codes(cli: KicadCli, target: int) -> list[tuple[str, str | None]]:
    """``(side, covered)`` of the record of each test pad of the features bench, in bench order."""
    unit, records = d356(cli, feature_text(target))
    out: list[tuple[str, str | None]] = []
    for _, centre, _, _ in TEST_PADS:
        (record,) = records_at(unit, records, centre)
        out.append((record.side, record.covered))
    return out


CODES: list[tuple[str, str | None]] = [
    ("top", "bottom"),
    ("bottom", "top"),
    ("both", "none"),
    ("top", "both"),
]
"""``A01 S2``, ``A02 S1``, ``A00 S0`` and ``A01 S3``: the records of the four test pads."""


def testpoint_d356(cli: KicadCli) -> str:
    """``asm-testpoint-d356``: the four records hold the codes of ``CODES`` and agree with the report."""
    for target in targets(cli):
        if mask_codes(cli, target) != CODES or report_problems(cli, target):
            return "different"
    return "equal"


def feature_probes(runner: Callable[[], KicadCli]) -> Probes:
    """The ``pad-fabprop-*`` and ``asm-*`` probes of the running ``kicad-cli`` (change c0118)."""
    probes: Probes = {
        f"pad-fabprop-{value}": (lambda v=value: fabprop(runner(), v), MAJORS) for value in FUNCTIONS
    }
    probes.update(
        {
            "pad-fabprop-outputs": (lambda: outputs(runner()), MAJORS),
            "pad-fabprop-padstack": (lambda: padstack(runner()), MAJORS),
            "pad-fabprop-resave": (lambda: resave_keeps(runner()), (10,)),
            "pad-fabprop-lib-mismatch": (lambda: lib_mismatch(runner()), MAJORS),
            "pad-fabprop-lib-same": (lambda: lib_same(runner()), MAJORS),
            "asm-fiducial-drc": (lambda: fiducial_drc(runner()), MAJORS),
            "asm-fiducial-mask": (lambda: fiducial_mask(runner()), MAJORS),
            "asm-fiducial-d356": (lambda: fiducial_d356(runner()), MAJORS),
            "asm-keepout-track": (lambda: keepout_track(runner()), MAJORS),
            "asm-keepout-fill": (lambda: keepout_fill(runner()), (10,)),
            "asm-testpoint-d356": (lambda: testpoint_d356(runner()), MAJORS),
        }
    )
    return probes


__all__ = [
    "TEN_ONLY",
    "ACCESS",
    "ALL_MARKS",
    "APOTHEM",
    "CODES",
    "FUNCTIONS",
    "MAJORS",
    "PADSTACK_MARKS",
    "TEST_PADS",
    "authored_files",
    "fabprop",
    "feature_design",
    "feature_probes",
    "feature_text",
    "fill_gap",
    "flashes",
    "mark_function",
    "marks_text",
    "mask_codes",
    "padstack_names",
    "report_problems",
    "targets",
]
