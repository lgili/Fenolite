# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design with a board, lowered to the Altium writers' inputs and written (capability altium-pcb-writer,
"Imported boards are written from the model"; capability backend-protocol, "Altium write of a model";
change c0090). Every document here is one of Fenolite's own samples, or is written in the test."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import _altium_records as rec
import pytest
from _altium_built import EXAMPLES, build_altium_example

from fenolite.backends.altium import lower, pcbdoc, pcbrecords
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ArcRecord
from fenolite.backends.altium.roundtrip import RT_A2_SCOPE
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks.diff import diff_designs
from fenolite.checks.equivalence import compare_designs
from fenolite.checks.equivalence.model import Tolerances
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.lens import altium_copper
from fenolite.lens.altium import corner_ratios, write_model
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
SAMPLES = ROOT / "tests" / "data" / "altium"
DOCUMENTS = ("blink/blink.PcbDoc", "routed/routed.PcbDoc", "board6/board6.PcbDoc")
KICAD_ROUTED = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
KICAD_BLINK = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t10" / "blink.kicad_pcb"
WRITTEN_UNIT = Tolerances(length_nm=2)
"""A length is written in units of 2.54 nm: two lengths within 2 nm are equal (``RT_A2_SCOPE``)."""


def _read(path: Path) -> Design:
    return AltiumBackend().read(path).design


def _reading_of(written: lower.ProjectWrite, folder: Path, suffix: str = ".PcbDoc") -> Design:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in written.files.items():
        (folder / name).write_bytes(data)
    (document,) = [name for name in written.files if name.endswith(suffix)]
    return _read(folder / document)


def test_kinds_are_those_of_the_build() -> None:
    """The write of a model accounts for the kinds that a build accounts for, and for a few more."""
    assert lower.KINDS == altium_copper.KINDS
    assert not set(lower.KINDS) & set(lower.MORE_KINDS)
    assert lower.LOSS_KINDS <= set(lower.KINDS) | set(lower.MORE_KINDS)


@pytest.mark.parametrize("document", DOCUMENTS)
def test_own_document_is_written_from_its_model(document: str, tmp_path: Path) -> None:
    """A model read from one of Fenolite's own PCB documents is written, and the reading of what was
    written equals it inside the written scope. The project holds the PCB document, a schematic that is
    generated from the circuit, its library and the project file."""
    first = _read(SAMPLES / document)
    written = AltiumBackend().write(first)
    name = Path(document).stem
    assert sorted(written.files) == [
        f"{name}.{suffix}" for suffix in ("PcbDoc", "PrjPcb", "SchDoc", "SchLib")
    ]
    second = _reading_of(written, tmp_path)
    assert diff_designs(first, second, scope=RT_A2_SCOPE).changes == ()
    board = first.board
    assert board is not None and written.inputs.pcb is not None
    assert written.inputs.written["footprint"] == len(board.footprints)
    assert written.inputs.written["pad"] == sum(len(fp.pads) for fp in board.footprints)
    assert written.inputs.written["track"] == len(board.tracks)
    assert written.inputs.written["via"] == len(board.vias)
    assert not set(written.inputs.not_lowered) & lower.LOSS_KINDS


def test_write_is_deterministic_and_reads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two writes of equal designs give equal bytes, and the write opens no file: the placements, pads,
    copper, zones, rules, stack and classes come from the model."""
    first = _read(SAMPLES / "routed" / "routed.PcbDoc")
    again = _read(SAMPLES / "routed" / "routed.PcbDoc")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the write of a model reads no file")

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", refuse)
        patch.setattr(Path, "read_bytes", refuse)
        patch.setattr(Path, "read_text", refuse)
        one, other = lower.write_design(first), lower.write_design(again)
    assert dict(one.files) == dict(other.files) and one.issues == other.issues


def test_native_unique_ids_are_reused(tmp_path: Path) -> None:
    """The unique ids that the first reading keeps as native ids are the unique ids of the written
    components, so Altium's link between a component and its schematic part survives a rewrite."""
    source = SAMPLES / "routed" / "routed.PcbDoc"
    before = read_pcbdoc(source.read_bytes(), file=source.name).components
    written = AltiumBackend().write(_read(source))
    after = read_pcbdoc(written.files["routed.PcbDoc"], file="routed.PcbDoc").components
    assert len(before) == len(after) == 3
    assert [c.unique_id for c in after] == [c.unique_id for c in before]
    assert [c.source_unique_id for c in after] == [c.source_unique_id for c in before]
    links = [str(c.source_unique_id).rpartition("\\")[2] for c in before]
    assert all(c.unique_id and c.source_unique_id for c in before)
    # the generated schematic names the same ids: the link is kept on both sides
    schematic = AltiumBackend().read(_write_all(written, tmp_path) / "routed.SchDoc").design
    natives = [c.native_ids["altium"] for c in schematic.circuit.components]
    assert len(links) == 3 and all(any(link in native for native in natives) for link in links)


def _write_all(written: lower.ProjectWrite, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in written.files.items():
        (folder / name).write_bytes(data)
    return folder


def test_items_outside_the_written_scope_are_counted_once_per_kind() -> None:
    """board6 holds texts and graphics on a mechanical layer, which no record of the writer carries: each
    kind is counted, its entities are named, and one ``altium.not-lowered`` reports the kind."""
    first = _read(SAMPLES / "board6" / "board6.PcbDoc")
    issues: list[Issue] = []
    inputs = lower.from_design(first, issues=issues)
    assert inputs.counts() == {"text": 2, "graphic": 6}
    board = first.board
    assert board is not None
    assert set(inputs.not_lowered["text"]) <= {text.id for text in board.texts}
    assert set(inputs.not_lowered["graphic"]) <= {graphic.id for graphic in board.graphics}
    assert [(i.code, i.severity, i.where) for i in issues] == [
        ("altium.not-lowered", "info", "text"),
        ("altium.not-lowered", "info", "graphic"),
    ]
    assert "2 text item(s)" in issues[0].message and "Mech.13" in issues[0].message
    assert inputs.written["text"] + 2 == len(board.texts)


def test_a_loss_of_copper_needs_allow_lossy(tmp_path: Path) -> None:
    """A pad that no pad record holds (a custom shape) is a loss of the board that is made: the write is
    refused with ``FEN-7001`` unless ``allow_lossy``, and then the pad is counted and left out."""
    first = _read(SAMPLES / "blink" / "blink.PcbDoc")
    board = first.board
    assert board is not None
    footprint = board.footprints[0]
    odd = dataclasses.replace(footprint.pads[0], shape="custom")
    changed = dataclasses.replace(footprint, pads=(odd, *footprint.pads[1:]))
    design = dataclasses.replace(
        first, board=dataclasses.replace(board, footprints=(changed, *board.footprints[1:]))
    )
    with pytest.raises(lower.LossyWriteError) as refused:
        AltiumBackend().write(design)
    assert refused.value.cli_code == "FEN-7001"
    assert [(i.code, i.severity, i.where) for i in refused.value.issues] == [
        ("altium.not-lowered", "warning", "pad")
    ]
    written = AltiumBackend().write(design, allow_lossy=True)
    assert written.inputs.counts() == {"pad": 1} and written.inputs.not_lowered["pad"] == (odd.id,)
    second = _reading_of(written, tmp_path)
    assert second.board is not None
    assert sum(len(fp.pads) for fp in second.board.footprints) == 35
    with pytest.raises(ValueError, match="one form"):
        AltiumBackend().write(first, target=10)


@pytest.mark.parametrize("board", [KICAD_ROUTED, KICAD_BLINK], ids=["two_layer", "blink"])
def test_kicad_board_written_as_altium_documents(board: Path, tmp_path: Path) -> None:
    """Scenarios "A KiCad board written as Altium documents" and "Footprints without a library": a routed
    KiCad board is read with the KiCad backend (no footprint library is present or read), written, and the
    reading of the written PCB document is equal to it at the levels 1 to 5 of ``equivalent``, in the
    relative frame and within the written unit."""
    first = KicadBackend().read(board).design
    assert first.board is not None and first.board.tracks and first.board.vias
    written = write_model(first)
    assert not [found for found in written.issues if found.severity != "info"]
    document = read_pcbdoc(written.files[f"{board.stem}.PcbDoc"], file="x.PcbDoc")
    assert len(document.components) == len(first.board.footprints)
    assert len(document.pads) == sum(len(fp.pads) for fp in first.board.footprints)
    second = _reading_of(written, tmp_path)
    report = compare_designs(first, second, level=5, tolerances=WRITTEN_UNIT, frame="relative")
    assert report.equivalent and report.differences == ()
    assert [level.level for level in report.levels] == [1, 2, 3, 4, 5]
    assert all(level.compared > 0 for level in report.levels)


def test_rounded_pads_of_a_kicad_board_need_the_lens() -> None:
    """The model holds no corner ratio: a pad read from an Altium document carries its percentage, and a
    pad read from a KiCad board keeps the ratio in KiCad's bag, which the lens reads. Without it the
    backend's write refuses the rounded rectangles instead of guessing a ratio."""
    first = KicadBackend().read(KICAD_BLINK).design
    ratios = corner_ratios(first)
    assert first.board is not None
    rounded = [pad for fp in first.board.footprints for pad in fp.pads if pad.shape == "roundrect"]
    assert rounded and set(ratios) == {pad.id for pad in rounded}
    with pytest.raises(lower.LossyWriteError) as refused:
        AltiumBackend().write(first)
    assert [found.where for found in refused.value.issues] == ["pad"]
    assert "corner ratio" in refused.value.issues[0].message


def test_build_agrees(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Build and write agree": the model that a build stores is written with ``write``, and the
    PCB document of the build and the one of the write read to equal models inside the written scope. The
    two files are not equal byte for byte: a build writes library footprints with their graphics, which
    a footprint of the model does not hold."""
    code, folder, error = build_altium_example(monkeypatch, tmp_path, EXAMPLES / "blink_routed" / "design.py")
    assert code == 0, error
    stored = load_dir(folder / ".fenolite")
    assert stored.board is not None and stored.board.footprints and stored.board.tracks
    built = _read(folder / "blink_routed.PcbDoc")
    written = write_model(stored)  # the pads come from KiCad footprints: the lens knows their corners
    rewritten = _reading_of(written, tmp_path / "rewritten")
    assert diff_designs(built, rewritten, scope=RT_A2_SCOPE).changes == ()
    aligned = AltiumBackend().in_model_frame(stored, rewritten)
    pcb_kinds = {k: v for k, v in RT_A2_SCOPE.fields.items() if k not in ("component", "net", "no_connect")}
    scope = dataclasses.replace(RT_A2_SCOPE, fields=pcb_kinds)
    assert diff_designs(stored, aligned, scope=scope).changes == ()
    assert written.files["blink_routed.PcbDoc"] != (folder / "blink_routed.PcbDoc").read_bytes()


def test_circuit_items_of_repeated_sheets_are_counted() -> None:
    """Change c0083 gave imported components a pin-to-pad map and modules their channel: the generated
    schematic is one sheet of generic symbols, so a write counts each map, each module and each channel
    as not written, with one info per kind, and none of them is a loss that refuses the write."""
    (project,) = sorted((SAMPLES / "hier").glob("*.PrjPcb"))
    first = _read(project)
    assert first.circuit.modules
    component = first.circuit.components[0]
    mapped = dataclasses.replace(component, pin_pad_map=(("1", "1"),))
    circuit = dataclasses.replace(first.circuit, components=(mapped, *first.circuit.components[1:]))
    issues: list[Issue] = []
    inputs = lower.from_design(dataclasses.replace(first, circuit=circuit), issues=issues)
    assert inputs.not_lowered["pin-pad-map"] == (component.id,)
    assert set(inputs.not_lowered["module"]) == {module.id for module in first.circuit.modules}
    assert "channel" not in inputs.not_lowered  # the sample repeats no sheet
    found = {i.where: i.severity for i in issues if i.where in ("pin-pad-map", "module")}
    assert found == {"pin-pad-map": "info", "module": "info"}
    assert not {"pin-pad-map", "module", "channel"} & lower.LOSS_KINDS


# --- arcs keep their record (change c0127) ---------------------------------------------------------------

CENTRE = (1_000_000, 2_000_000)
"""Authored arcs of 100 units radius (0.254 µm): from 30 to 35 degrees the three points give a record
with another centre and a radius of 93 units, and from 0 to 1 degree they lie on one line."""


def _with_arcs() -> Design:
    """The reading of the routed sample with three authored arc records read into it: two on copper and
    one on the bottom overlay."""
    records = [
        rec.arc(CENTRE, 100, 30.0, 35.0),
        rec.arc(CENTRE, 100, 0.0, 1.0),
        rec.arc(CENTRE, 100, 30.0, 35.0, layer=34),
    ]
    authored = import_board(rec.document(rec.board((1, 32)), arcs=records), file="a.PcbDoc", sha256=rec.SHA)
    assert authored.board is not None
    (drawn,) = [g for g in authored.board.graphics if g.kind == "arc"]
    first = _read(SAMPLES / "routed" / "routed.PcbDoc")
    assert first.board is not None
    board = dataclasses.replace(
        first.board, arcs=authored.board.arcs, graphics=(*first.board.graphics, drawn)
    )
    return dataclasses.replace(first, board=board)


def _arc_records(data: bytes) -> list[tuple[int, int, int, float, float]]:
    """The free arc records of a PCB document (those of no component), sorted."""
    arcs = [a for a in read_pcbdoc(data, file="routed.PcbDoc").arcs if isinstance(a, ArcRecord)]
    free = [a for a in arcs if a.prefix.component is None]
    return sorted((a.cx, a.cy, a.radius, a.start_angle, a.end_angle) for a in free)


def test_kept_arc_is_written_from_its_record(tmp_path: Path) -> None:
    """Scenario "Arc written from its record": an arc that was read is written with the centre, radius
    and angles of its record, also when its three points lie on one line, and the second reading holds
    the points of the first. Derived from the points, the first arc would get another centre."""
    first = _with_arcs()
    board = first.board
    assert board is not None and len(board.arcs) == 2
    bent, flat = board.arcs
    (drawn,) = [g for g in board.graphics if g.kind == "arc"]
    derived = rec_geometry(bent.start, bent.mid, bent.end)
    assert (derived.cx, derived.cy, derived.radius) == (1_000_163, 2_000_103, 93)
    with pytest.raises(ValueError, match="collinear"):
        rec_geometry(flat.start, flat.mid, flat.end)
    written = AltiumBackend().write(first)
    spec = written.inputs.pcb
    assert spec is not None and set(spec.arc_records) == {bent.id, flat.id, drawn.id}
    assert written.inputs.written["arc"] == 2 and "arc" not in written.inputs.not_lowered
    assert _arc_records(written.files["routed.PcbDoc"]) == [
        (*CENTRE, 100, 0.0, 1.0),
        (*CENTRE, 100, 30.0, 35.0),
        (*CENTRE, 100, 30.0, 35.0),
    ]
    second = _reading_of(written, tmp_path)
    assert second.board is not None
    assert {(a.start, a.mid, a.end) for a in second.board.arcs} == {
        (a.start, a.mid, a.end) for a in board.arcs
    }
    assert diff_designs(first, second, scope=RT_A2_SCOPE).changes == ()
    assert [g.points for g in second.board.graphics if g.kind == "arc"] == [drawn.points]


def rec_geometry(start: Point, mid: Point, end: Point) -> pcbrecords.ArcGeometry:
    """The record that the writer derives from three points of a board read from a document."""
    frame = pcbdoc.Frame.document()
    return pcbrecords.arc_from_points(frame(start), frame(mid), frame(end))


def test_stale_arc_record_is_ignored() -> None:
    """Scenario "Stale record ignored": an arc that was moved in the model keeps its bag, which no longer
    says its points; it is written from its points, without an issue. Within the tolerance of the written
    scope the record is still used."""
    first = _with_arcs()
    board = first.board
    assert board is not None
    bent, flat = board.arcs

    def shifted(by: int) -> Design:
        moved = dataclasses.replace(
            bent,
            start=Point(bent.start.x + by, bent.start.y),
            mid=Point(bent.mid.x + by, bent.mid.y),
            end=Point(bent.end.x + by, bent.end.y),
        )
        return dataclasses.replace(first, board=dataclasses.replace(board, arcs=(moved, flat)))

    issues: list[Issue] = []
    inputs = lower.from_design(shifted(1_000), issues=issues)
    assert inputs.pcb is not None and bent.id not in inputs.pcb.arc_records
    assert flat.id in inputs.pcb.arc_records and inputs.written["arc"] == 2
    assert not [i for i in issues if i.where == "arc"]
    data = pcbdoc.write_pcbdoc(inputs.pcb, filename="routed.PcbDoc")
    want = rec_geometry(Point(bent.start.x + 1_000, bent.start.y), Point(bent.mid.x + 1_000, bent.mid.y),
                        Point(bent.end.x + 1_000, bent.end.y))  # fmt: skip
    assert (want.cx, want.cy, want.radius, want.start, want.end) in _arc_records(data)
    assert _arc_records(data).count((*CENTRE, 100, 30.0, 35.0)) == 1  # the graphic, which was not moved
    near = lower.from_design(shifted(lower.ARC_TOLERANCE), issues=[])
    far = lower.from_design(shifted(lower.ARC_TOLERANCE + 1), issues=[])
    assert near.pcb is not None and far.pcb is not None
    assert bent.id in near.pcb.arc_records and bent.id not in far.pcb.arc_records
    assert lower.ARC_TOLERANCE == RT_A2_SCOPE.length_tolerance


@pytest.mark.parametrize(
    "pair",
    [
        None,
        "",
        "1000000,2000000,100,0x1.e000000000000p+4",
        "1000000,2000000,100,30,35,0",
        "1000000,2000000,1e2,0x1.e000000000000p+4,0x1.1800000000000p+5",
        "1000000,2000000,100,thirty,0x1.1800000000000p+5",
        "1000000,2000000,0,0x1.e000000000000p+4,0x1.1800000000000p+5",
        "1000000,2000000,-100,0x1.e000000000000p+4,0x1.1800000000000p+5",
        "4294967296,2000000,100,0x1.e000000000000p+4,0x1.1800000000000p+5",
        "1000000,2000000,100,nan,0x1.1800000000000p+5",
        "1000000,2000000,100,0x1.e000000000000p+4,inf",
        "1000000,2000000,100,0x1.e000000000000p+4,0x1.e000000000000p+4",
        "1000000,2000000,100,0x1.1800000000000p+5,0x1.e000000000000p+4",
        "1000000,2000000,110,0x1.e000000000000p+4,0x1.1800000000000p+5",
        "1000000,2000100,100,0x1.e000000000000p+4,0x1.1800000000000p+5",
    ],
)
def test_kept_arc_refuses_a_pair_that_does_not_say_the_points(pair: str | None) -> None:
    """``kept_arc`` gives ``None`` for a missing pair, a pair that does not parse, a radius that is not
    positive, a value outside 32 bits, an angle that is not finite, a full turn, the other part of the
    circle, another radius and another centre; and for a board that is written in another frame."""
    first = _with_arcs()
    assert first.board is not None
    bent = first.board.arcs[0]
    points = (bent.start, bent.mid, bent.end)
    frame = pcbdoc.Frame.document()
    kept = lower.kept_arc(bent, points, frame)
    assert kept == pcbrecords.ArcGeometry(*CENTRE, 100, 30.0, 35.0)
    assert lower.kept_arc(bent, points, pcbdoc.Frame(0, 0)) is None  # the frame of a build: moved by 1000 mil
    assert lower.kept_arc(bent, points[:2], frame) is None
    bag = bent.ext["altium"]
    payload = tuple(p for p in bag.payload if p[0] != lower.ARC_KEY)
    if pair is not None:
        payload += ((lower.ARC_KEY, pair),)
    changed = dataclasses.replace(
        bent, ext={"altium": dataclasses.replace(bag, payload=payload)} if payload else {}
    )
    assert lower.kept_arc(changed, points, frame) is None


def test_a_design_without_the_bag_is_written_as_before() -> None:
    """An arc with its pair is written with the record of the document it was read from, to the last bit
    of its angles; with every bag taken away the same arc is derived from its three points, as before
    change c0127, and its angles are then other doubles. A KiCad board holds no ``altium`` bag at all."""
    source = SAMPLES / "routed" / "routed.PcbDoc"
    first = _read(source)
    assert first.board is not None and first.board.arcs
    assert all(lower.ARC_KEY in lower.pairs_of(arc) for arc in first.board.arcs)
    arcs = tuple(dataclasses.replace(arc, ext={}) for arc in first.board.arcs)
    bare = dataclasses.replace(first, board=dataclasses.replace(first.board, arcs=arcs))
    with_bag, without = lower.from_design(first, issues=[]), lower.from_design(bare, issues=[])
    assert with_bag.pcb is not None and without.pcb is not None
    assert set(with_bag.pcb.arc_records) == {arc.id for arc in first.board.arcs}
    assert without.pcb.arc_records == {}
    original = _arc_records(source.read_bytes())
    kept = _arc_records(pcbdoc.write_pcbdoc(with_bag.pcb))
    derived = _arc_records(pcbdoc.write_pcbdoc(without.pcb))
    assert kept == original and derived != original
    assert [record[:3] for record in derived] == [record[:3] for record in original]
    kicad = KicadBackend().read(KICAD_ROUTED).design
    assert kicad.board is not None
    assert not any("altium" in entity.ext for entity in (*kicad.board.arcs, *kicad.board.graphics))


# --- a via with a drill equal to its diameter, in a rewrite only (change c0128) --------------------------


def _with_full_drill() -> tuple[Design, str, str]:
    """The reading of the routed sample with the drill of its first via set to the diameter and the drill
    of its second via set above the diameter; the ids of the two vias."""
    first = _read(SAMPLES / "routed" / "routed.PcbDoc")
    assert first.board is not None and len(first.board.vias) == 3
    full, above, other = first.board.vias
    vias = (
        dataclasses.replace(full, drill=full.diameter),
        dataclasses.replace(above, drill=above.diameter + 1),
        other,
    )
    return dataclasses.replace(first, board=dataclasses.replace(first.board, vias=vias)), full.id, above.id


def test_full_drill_is_written_in_a_rewrite_only(tmp_path: Path) -> None:
    """Scenario "Full drill in a rewrite only": without ``rewrite`` a via whose drill equals its diameter
    is left out and counted, as before change c0128; with it the via is written with a hole equal to its
    diameter and reads back so. A drill above the diameter is left out in both."""
    design, full, above = _with_full_drill()
    reason = "the drill is not below the diameter"
    issues: list[Issue] = []
    plain = lower.from_design(design, issues=issues)
    assert plain.not_lowered["via"] == (full, above) and plain.reasons["via"] == reason
    assert plain.written["via"] == 1 and plain.pcb is not None and not plain.pcb.allow_full_drill
    assert [(i.code, i.severity, i.where) for i in issues] == [("altium.not-lowered", "warning", "via")]
    issues = []
    again = lower.from_design(design, issues=issues, rewrite=True)
    assert again.not_lowered["via"] == (above,) and again.reasons["via"] == reason
    assert again.written["via"] == 2 and again.pcb is not None and again.pcb.allow_full_drill
    written = lower.write_design(design, allow_lossy=True, rewrite=True)
    records = read_pcbdoc(written.files["routed.PcbDoc"], file="routed.PcbDoc").vias
    assert sorted(v.hole == v.diameter for v in records) == [False, True]  # type: ignore[union-attr]
    second = _reading_of(written, tmp_path)
    assert second.board is not None and design.board is not None
    wanted = {(v.position, v.diameter, v.drill) for v in design.board.vias if v.id != above}
    assert {(v.position, v.diameter, v.drill) for v in second.board.vias} == wanted


def test_rewrite_is_the_callers_word() -> None:
    """Scenario "Rewrite is the caller's word": ``AltiumBackend.write`` refuses the loss of the via, counts
    it with ``allow_lossy``, and writes it with ``rewrite=True``. The argument changes nothing else: a
    design without such a via gives the same bytes with and without it. A board that was not read from an
    Altium document is refused, so a script's design or a KiCad design never gets the relaxed rule."""
    design, full, above = _with_full_drill()
    assert design.board is not None
    vias = tuple(v for v in design.board.vias if v.id != above)
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, vias=vias))
    with pytest.raises(lower.LossyWriteError) as refused:
        AltiumBackend().write(design)
    assert [(i.code, i.severity, i.where) for i in refused.value.issues] == [
        ("altium.not-lowered", "warning", "via")
    ]
    lossy = AltiumBackend().write(design, allow_lossy=True)
    assert lossy.inputs.not_lowered["via"] == (full,) and lossy.inputs.written["via"] == 1
    rewritten = AltiumBackend().write(design, rewrite=True)
    assert "via" not in rewritten.inputs.not_lowered and rewritten.inputs.written["via"] == 2
    assert not [i for i in rewritten.issues if i.where == "via"]
    sample = _read(SAMPLES / "routed" / "routed.PcbDoc")
    assert dict(AltiumBackend().write(sample).files) == dict(
        AltiumBackend().write(sample, rewrite=True).files
    )
    kicad = KicadBackend().read(KICAD_ROUTED).design
    with pytest.raises(ValueError, match="rewrite=True is for the reading of an Altium document"):
        lower.from_design(kicad, issues=[], rewrite=True)
    with pytest.raises(ValueError, match="rewrite=True is for the reading of an Altium document"):
        AltiumBackend().write(kicad, rewrite=True)
    schematic = _read(SAMPLES / "sample" / "altium_sample.SchDoc")
    assert schematic.board is None
    assert lower.from_design(schematic, issues=[], rewrite=True).pcb is None


def test_roundtrip_is_a_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    """``AltiumBackend.model_roundtrip`` writes with ``rewrite=True``: the trip of RT-A3 gives back a
    document that was read. No other caller of the write passes it."""
    seen: list[dict[str, object]] = []
    real = lower.write_design

    def spy(design: Design, **options: object) -> lower.ProjectWrite:
        seen.append(options)
        return real(design, **options)  # type: ignore[arg-type]

    monkeypatch.setattr(lower, "write_design", spy)
    trip = AltiumBackend().model_roundtrip(
        SAMPLES / "routed" / "routed.PcbDoc", compare=lambda a, b, s: diff_designs(a, b, scope=s)
    )
    assert trip.equal and seen == [{"allow_lossy": True, "rewrite": True, "bodies": "off"}]
    seen.clear()
    AltiumBackend().write(_read(SAMPLES / "routed" / "routed.PcbDoc"))
    write_model(KicadBackend().read(KICAD_ROUTED).design)
    assert [options.get("rewrite", False) for options in seen] == [False, False]


# --- a via without a pad shape on some layers is written with its pad and counted (change c0132) ---------


def test_pad_shape_layers_are_counted_not_written(tmp_path: Path) -> None:
    """Scenario "A via with removed pad shapes in a rewrite": the via is written as the ordinary record of
    321 bytes with a table of zeros, and counted under ``via-pad-shape``, which is no loss kind."""
    from fenolite.backends.altium.read.pcbprims import ViaRecord, via_pad_removed
    from fenolite.model.base import ExtBag

    first = _read(SAMPLES / "routed" / "routed.PcbDoc")
    assert first.board is not None
    bare, *others = first.board.vias
    held = bare.ext["altium"].payload if "altium" in bare.ext else ()
    assert not any("pad_removed" in lower.pairs_of(via) for via in first.board.vias)
    marked = dataclasses.replace(
        bare, ext={"altium": ExtBag(min_version=None, payload=(*held, ("pad_removed", "2,4,5")))}
    )
    design = dataclasses.replace(first, board=dataclasses.replace(first.board, vias=(marked, *others)))
    assert "via-pad-shape" in lower.MORE_KINDS and "via-pad-shape" not in lower.LOSS_KINDS
    issues: list[Issue] = []
    inputs = lower.from_design(design, issues=issues)
    assert inputs.not_lowered["via-pad-shape"] == (bare.id,) and "via" not in inputs.not_lowered
    assert inputs.written["via"] == len(first.board.vias)
    codes = [(i.code, i.severity, i.where) for i in issues if i.where == "via-pad-shape"]
    assert codes == [("altium.not-lowered", "info", "via-pad-shape")]
    written = lower.write_design(design)  # not refused: the via is written
    records = read_pcbdoc(written.files["routed.PcbDoc"], file="routed.PcbDoc").vias
    assert len(records) == len(first.board.vias)
    for record in records:
        assert isinstance(record, ViaRecord) and len(record.raw) == 326 and via_pad_removed(record) == ()
    assert written.files == lower.write_design(first).files  # the bytes of the write without the pair
    second = _reading_of(written, tmp_path)
    assert second.board is not None and [v.id for v in second.board.vias] == [v.id for v in first.board.vias]
    assert "via-pad-shape" not in lower.from_design(first, issues=[]).counts()
