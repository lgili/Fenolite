# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design with a board, lowered to the Altium writers' inputs and written (capability altium-pcb-writer,
"Imported boards are written from the model"; capability backend-protocol, "Altium write of a model";
change c0090). Every document here is one of Fenolite's own samples, or is written in the test."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _altium_built import EXAMPLES, build_altium_example

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.roundtrip import RT_A2_SCOPE
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks.diff import diff_designs
from fenolite.checks.equivalence import compare_designs
from fenolite.checks.equivalence.model import Tolerances
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
