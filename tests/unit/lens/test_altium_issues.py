# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium build's closed table of issue codes (capability altium-build, "Altium build issue codes";
change c0032; ``altium.schematic-too-large`` of change c0033, "Altium schematic format option").

Each case below is a sample variant and the codes its build must report; ``test_closed_set`` runs every
case and checks that the codes produced are exactly the table's, with the table's severities.
"""

from __future__ import annotations

import dataclasses
import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from _altium import (
    EXAMPLE_DIR,
    blink,
    blink_resolver,
    blink_tree,
    example,
    example_resolver,
    hier,
    sample,
)
from _altium_job import grown_paper_issues, kept_project_issues

import fenolite.lens.altium as lens_altium
from fenolite.backends.altium import cfb
from fenolite.core.errors import Issue
from fenolite.dsl import Design, DiffPair, Net, Part, connect, mm, no_connect, placements, to_model
from fenolite.lens.altium import ALTIUM_ISSUE_CODES, build_altium
from fenolite.model.design import Design as ModelDesign

PASS_THROUGH = ("model.", "build.layout-exists", "altium.sheet.")
"""Codes of other tables that a build reports as they are; ``altium.sheet.*`` are the sheet template
codes of ``read.sheet.ISSUE_CODES``, which a drawing sheet gives (change c0087)."""


def _lib_id(d: Design) -> None:
    d.parts["J1"].lib_id = "HDR2"


def _footprint_form(d: Design) -> None:
    d.parts["R2"].footprint = "R0603"


def _text(d: Design) -> None:
    d.parts["power/C1"].value = "10µF"


def _comment_reference(d: Design) -> None:
    d.parts["R2"].value = "=Value"


def _net_pipe(d: Design) -> None:
    d.add(Net("A|B"))


def _case(d: Design) -> None:
    connect(Net("gnd"), d.parts["U2"]["5"], d.parts["R2"]["3"])


def _no_footprint(d: Design) -> None:
    d.parts["led/D1"].footprint = None


def _not_lowered(d: Design) -> None:
    d.board(mm(50), mm(30))
    d.parts["J1"].place(mm(5), mm(5))
    d.rules.netclass("PWR", clearance=mm(0.3), nets=(d.nets["VIN"], d.nets["GND"]))
    d.add(DiffPair(d.nets["EN"], d.nets["LED_DRV"]))


def _custom_sheet(d: Design) -> None:
    a, b = Net("BIG_A"), Net("BIG_B")
    for n in range(1, 701):
        part = Part(f"X{n}", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
        d.add(part)
        connect(a, part[1])
        connect(b, part[2])


def _nothing(d: Design) -> None:
    return None


def _library_case(d: Design) -> None:
    d.parts["J1"].lib_id = "fenolitesample.schlib:HDR2"


def _long_lib_ref(d: Design) -> None:
    d.parts["J1"].lib_id = "FenoliteSample.SchLib:" + "HEADER_" * 6


@contextmanager
def _same_unique_ids() -> Iterator[None]:
    original = lens_altium.unique_id
    lens_altium.unique_id = lambda key: "AAAAAAAA"  # type: ignore[assignment]
    try:
        yield
    finally:
        lens_altium.unique_id = original  # type: ignore[assignment]


CASES: dict[str, tuple[Callable[[Design], None], dict[str, object], set[str]]] = {
    "lib-id": (_lib_id, {}, {"altium.lib-id-form"}),
    "footprint-form": (_footprint_form, {}, {"altium.footprint-form"}),
    "non-ascii": (_text, {}, {"altium.text-unwritable"}),
    "comment-reference": (_comment_reference, {}, {"altium.text-unwritable"}),
    "net-pipe": (_net_pipe, {}, {"altium.text-unwritable"}),
    "case": (_case, {}, {"altium.name-case-collision"}),
    "no-footprint": (
        _no_footprint,
        {},
        {
            "altium.no-footprint",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "not-lowered": (
        _not_lowered,
        {"placed": ("J1",)},
        {
            "altium.not-lowered",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "project-kept": (
        _nothing,
        {"project_exists": True},
        {
            "altium.project-kept",
            "altium.schlib-not-in-project",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "custom-sheet": (
        _custom_sheet,
        {},
        {
            "altium.sheet-custom",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "clean": (_nothing, {}, {"altium.generic-symbols", "altium.schlib-generic", "altium.pcbdoc-not-written"}),
    "library-case": (_library_case, {}, {"altium.symbol-name-collision", "altium.schlib-generic"}),
    "section-key": (
        _long_lib_ref,
        {},
        {
            "altium.section-key",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
}


KICAD_CASES: dict[str, tuple[tuple[str, str], tuple[str, str], set[str]]] = {
    "kicad-clean": (
        ("", ""),
        ("", ""),
        {"altium.symbol-simplified", "altium.footprint-unresolved", "altium.pcbdoc-not-written"},
    ),
    "unknown-pin": (
        ("u1[8]", 'u1["XYZ"]'),
        ("", ""),
        {"altium.unknown-pin", "altium.symbol-simplified"},
    ),
    "off-grid": (
        ("", ""),
        ("(at 0 3.81 270)", "(at 0.001 3.81 270)"),
        {"altium.symbol-off-grid", "altium.symbol-simplified"},
    ),
    "lossy": (
        ("", ""),
        (
            "(pin passive line\n\t\t\t\t(at 2.54 -7.62 90)",
            "(pin no_connect non_logic\n\t\t\t\t(at 2.54 -7.62 90)",
        ),
        {
            "altium.pin-lossy",
            "altium.symbol-simplified",
            "altium.footprint-unresolved",
            "altium.pcbdoc-not-written",
        },
    ),
    "pin-text-too-long": (
        ("", ""),
        ('"CLK"', '"' + "C" * 256 + '"'),
        {"altium.pin-text-too-long", "altium.symbol-simplified"},
    ),
    "description": (
        ("", ""),
        ("Resistor drawn upright", "Résistance"),
        {"altium.text-unwritable", "altium.symbol-simplified"},
    ),
}
"""KiCad-example variants (change c0034): (script change, library change, codes)."""


def run_kicad_case(name: str) -> tuple[Issue, ...]:
    (old, new), (lib_old, lib_new), _ = KICAD_CASES[name]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        copy = root / "example"
        shutil.copytree(EXAMPLE_DIR, copy)
        if lib_old:
            library = copy / "FenoliteDemo.kicad_sym"
            text = library.read_text(encoding="utf-8")
            assert lib_old in text, lib_old
            library.write_text(text.replace(lib_old, lib_new), encoding="utf-8")
        design = example(old, new) if old else example()
        resolver = example_resolver(root, project_dir=copy)
        return build_altium(to_model(design), name=design.name, resolver=resolver).issues


@pytest.mark.parametrize("name", sorted(KICAD_CASES))
def test_kicad_case(name: str) -> None:
    issues = run_kicad_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == KICAD_CASES[name][2], [i.code for i in issues]


def run_case(name: str) -> tuple[Issue, ...]:
    change, kwargs, _ = CASES[name]
    design = sample()
    change(design)
    return build_altium(to_model(design), name=design.name, **kwargs).issues  # type: ignore[arg-type]


@contextmanager
def _no_fat_sector() -> Iterator[None]:
    original = cfb.MAX_FAT_SECTORS
    cfb.MAX_FAT_SECTORS = 0
    try:
        yield
    finally:
        cfb.MAX_FAT_SECTORS = original


def run_too_large_case(form: str = "binary") -> tuple[Issue, ...]:
    with _no_fat_sector():
        design = sample()
        output = build_altium(to_model(design), name=design.name, form=form)  # type: ignore[arg-type]
        assert output.files == {}
        expected = "altium.schematic-too-large" if form == "binary" else "altium.library-too-large"
        assert expected in {i.code for i in output.issues}
        return output.issues


def run_unique_id_case() -> tuple[Issue, ...]:
    with _same_unique_ids():
        design = sample()
        return build_altium(to_model(design), name=design.name).issues


TRAPEZOID = ("Mini_R_0603", '(pad "1" smd roundrect', '(pad "1" smd trapezoid')
OTHER_ROW = (
    '(descr "Authored CC0 mini library"))',
    '(descr "Authored CC0 mini library"))\n\t(lib (name "Other") (type "KiCad") '
    '(uri "${KIPRJMOD}/../../tests/data/libs/Mini.pretty") (options "") (descr ""))',
)
SECOND_R = (
    "design.add(u1, r1, d1)",
    'r2 = Part("R2", "Mini:Mini_R", footprint="Other:Mini_R_0603", value="1k")\ndesign.add(u1, r1, d1, r2)',
)
BLINK_CODES = {"altium.symbol-simplified", "altium.primitive-dropped", "altium.footprint-extras-dropped"}
NOT_PLANNED = {"altium.not-lowered", "altium.pcbdoc-not-written"}
"""Without the PCB document the net class of the blink sample is reported as kept in the model only."""
PCB_CASES: dict[str, tuple[dict[str, object], set[str]]] = {
    "blink": ({}, BLINK_CODES),
    "blink-kept": (
        {"project_exists": True},
        BLINK_CODES | {"altium.project-kept", "altium.schlib-not-in-project", "altium.pcb-not-in-project"},
    ),
    "blink-unplaced": (
        {"script": ("r1.place(mm(32), mm(9))", "")},
        BLINK_CODES | {"altium.pcb-staged"},
    ),
    "blink-unsupported": (
        {"footprint": TRAPEZOID},
        BLINK_CODES | NOT_PLANNED | {"altium.footprint-unsupported"},
    ),
    "blink-collision": (
        {"fp_table": OTHER_ROW, "script": SECOND_R},
        BLINK_CODES | NOT_PLANNED | {"altium.footprint-name-collision"},
    ),
}
"""Blink variants (change c0035): tree edits and build arguments, and the codes the build reports."""


def run_pcb_case(name: str) -> tuple[Issue, ...]:
    edits, _ = PCB_CASES[name]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        project = blink_tree(
            root,
            fp_table=edits.get("fp_table", ("", "")),  # type: ignore[arg-type]
            footprint=edits.get("footprint", ("", "", "")),  # type: ignore[arg-type]
        )
        script = edits.get("script", ("", ""))
        design = blink(*script)  # type: ignore[misc]
        kwargs = {k: v for k, v in edits.items() if k == "project_exists"}
        return build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(root, project),
            **kwargs,  # type: ignore[arg-type]
        ).issues


def run_pcb_too_large() -> tuple[Issue, ...]:
    import fenolite.backends.altium.project as altium_project

    original = altium_project.write_pcblib

    def refuse(footprints: object, **_kwargs: object) -> bytes:
        raise cfb.CompoundTooLarge("patched")

    altium_project.write_pcblib = refuse  # type: ignore[assignment]
    try:
        with tempfile.TemporaryDirectory() as folder:
            design = blink()
            output = build_altium(to_model(design), name=design.name, resolver=blink_resolver(Path(folder)))
    finally:
        altium_project.write_pcblib = original  # type: ignore[assignment]
    assert output.files == {}
    return output.issues


def _copper_layer(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    return model, {"copper": 2}


def _copper_stack(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    return model, {"copper": 3}


def _copper_board(model: ModelDesign, **changes: object) -> ModelDesign:
    assert model.board is not None
    return dataclasses.replace(model, board=dataclasses.replace(model.board, **changes))  # type: ignore[arg-type]


def _via_blind(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    assert model.board is not None
    first, *rest = model.board.vias
    micro = dataclasses.replace(first, via_type="micro", layers=("F.Cu", "In1.Cu"))
    spans = dataclasses.replace(rest[0], layers=("F.Cu", "F.Cu"))
    return _copper_board(model, vias=(micro, spans, *rest[1:])), {}


def _copper_invalid(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    assert model.board is not None
    a, b, *tracks = model.board.tracks
    (via, *vias), (arc,) = model.board.vias, model.board.arcs
    return _copper_board(
        model,
        tracks=(
            dataclasses.replace(a, end=a.start),
            dataclasses.replace(b, width=0),
            *tracks,
        ),
        vias=(dataclasses.replace(via, drill=via.diameter), *vias),
        arcs=(dataclasses.replace(arc, mid=arc.start),),
    ), {}


def _zone_opaque(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    assert model.board is not None
    (zone,) = model.board.zones
    opaque = dataclasses.replace(zone, outline=())
    nowhere = dataclasses.replace(zone, id="zon_00000000-0000-4000-8000-000000000002", layers=())
    return _copper_board(model, zones=(opaque, nowhere)), {}


def _plane_copper(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    """The sample's track on ``In1.Cu``, an arc moved there and a ``VIN`` zone on the ``GND`` plane."""
    assert model.board is not None
    (arc,), (zone,) = model.board.arcs, model.board.zones
    vin = next(net.id for net in model.circuit.nets if net.name == "VIN")
    other = dataclasses.replace(
        zone, id="zon_00000000-0000-4000-8000-000000000003", net_id=vin, layers=("In1.Cu",)
    )
    board = _copper_board(model, arcs=(dataclasses.replace(arc, layer="In1.Cu"),), zones=(zone, other))
    return board, {"planes": {"In1.Cu": "GND"}}


def _plane_unknown(model: ModelDesign) -> tuple[ModelDesign, dict[str, object]]:
    return model, {"planes": {"In1.Cu": "NOPE", "F.Cu": "GND"}}


COPPER_PARTS = ("tracks", "arc", "vias", "inner", "zones", "class")
COPPER_CASES: dict[
    str, tuple[Callable[[ModelDesign], tuple[ModelDesign, dict[str, object]]], dict[str, int]]
] = {
    "layer": (_copper_layer, {"altium.copper-layer": 3}),
    "zone": (_zone_opaque, {"altium.zone-unsupported": 2}),
    "plane": (_plane_copper, {"altium.plane-copper": 3}),
    "plane-net": (_plane_unknown, {"altium.copper-stack": 2}),
    "stack": (_copper_stack, {"altium.copper-layer": 3}),  # c0085: an odd count gives the default stack
    "via": (_via_blind, {"altium.via-unsupported": 1, "altium.copper-invalid": 1}),  # c0085: a micro via
    "invalid": (_copper_invalid, {"altium.copper-invalid": 4}),
}
"""Routed-sample variants (change c0038, "Copper issue codes"): the copper codes and their counts."""


def run_copper_case(name: str) -> tuple[Issue, ...]:
    from _altium_copper import routed_build, routed_model

    edit, _ = COPPER_CASES[name]
    model, kwargs = edit(routed_model(COPPER_PARTS))
    with tempfile.TemporaryDirectory() as folder:
        output = routed_build(Path(folder), model, **kwargs)
    assert output.files == {}, name
    return output.issues


def run_routed_sample() -> tuple[Issue, ...]:
    from _altium_copper import routed_build

    with tempfile.TemporaryDirectory() as folder:
        output = routed_build(Path(folder))
    assert "routed.PcbDoc" in output.files
    return output.issues


def run_source_cases() -> tuple[Issue, ...]:
    """The four codes of a copper source: a board that places ``R1`` elsewhere, one with a footprint the
    design lacks and copper on an unknown net, and a source given to a design without a board."""
    from _altium_copper import at, routed_build, routed_design, routed_kicad_design

    from fenolite.lens.altium import CopperSource

    script = to_model(routed_design())
    kicad = routed_kicad_design()
    assert kicad.board is not None
    refs = {c.id: c.ref for c in kicad.circuit.components}
    moved = tuple(
        dataclasses.replace(f, position=at(33, 9)) if refs[f.component_id] == "R1" else f
        for f in kicad.board.footprints
    )
    extra_net = dataclasses.replace(
        kicad.circuit.nets[0], id="net_00000000-0000-4000-8000-000000000009", name="EXTRA"
    )
    odd = dataclasses.replace(
        kicad,
        circuit=dataclasses.replace(kicad.circuit, nets=(*kicad.circuit.nets, extra_net)),
        board=dataclasses.replace(
            kicad.board,
            footprints=kicad.board.footprints[1:],
            tracks=(dataclasses.replace(kicad.board.tracks[0], net_id=extra_net.id), *kicad.board.tracks[1:]),
        ),
    )
    found: list[Issue] = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        placed = routed_build(
            root,
            script,
            copper_source=CopperSource(_copper_board(kicad, footprints=moved), "board", "b.kicad_pcb"),
        )
        assert "routed.PcbDoc" in placed.files
        found += placed.issues
        for source in (CopperSource(odd, "board", "b.kicad_pcb"),):
            refused = routed_build(root, script, copper_source=source)
            assert refused.files == {}
            found += refused.issues
        boardless = dataclasses.replace(script, board=None)
        refused = routed_build(root, boardless, copper_source=CopperSource(kicad, "script"))
        assert "routed.PcbDoc" not in refused.files
        found += refused.issues
        net_only = dataclasses.replace(
            odd, board=dataclasses.replace(odd.board, footprints=kicad.board.footprints)
        )  # type: ignore[arg-type]
        found += routed_build(root, script, copper_source=CopperSource(net_only, "script")).issues
    return tuple(found)


def test_zone_on_a_missing_layer() -> None:
    """Scenario "Copper on a missing layer": the routed model built with ``copper=2``."""
    found = [i for i in run_copper_case("layer") if i.code == "altium.copper-layer"]
    assert sorted(i.message.split(":")[0].split(" at ")[0] for i in found) == [
        "track on In1.Cu",
        "track on In2.Cu",
        "zone on In1.Cu, B.Cu",
    ]
    assert all("In1.Cu is not a copper layer" in i.message or "In2.Cu is not" in i.message for i in found)


@pytest.mark.parametrize("name", sorted(COPPER_CASES))
def test_copper_case(name: str) -> None:
    """One issue per entity, an error each, with the entity id in ``where``; no file is written."""
    codes = ("altium.copper", "altium.via", "altium.zone-unsupported", "altium.plane-copper")
    issues = [i for i in run_copper_case(name) if i.code.startswith(codes)]
    counts: dict[str, int] = {}
    for found in issues:
        counts[found.code] = counts.get(found.code, 0) + 1
        assert found.severity == ALTIUM_ISSUE_CODES[found.code] and found.where
    assert counts == COPPER_CASES[name][1], [(i.code, i.where, i.message) for i in issues]


def test_copper_net_id_that_names_no_net() -> None:
    """The model's own validation stops a dangling net id first; the lowering still refuses it."""
    from _altium_copper import routed_model

    from fenolite.lens.altium_copper import lower_copper

    model = routed_model(COPPER_PARTS)
    assert model.board is not None
    first, *tracks = model.board.tracks
    lost = dataclasses.replace(first, net_id="net_00000000-0000-4000-8000-000000000000")
    plan = lower_copper(_copper_board(model, tracks=(lost, *tracks)), copper=4)
    (found,) = plan.issues
    assert found.code == "altium.copper-invalid" and found.where == first.id and plan.failed
    assert "names no net" in found.message and len(plan.tracks) == 4


@pytest.mark.parametrize("name", sorted(PCB_CASES))
def test_pcb_case(name: str) -> None:
    issues = run_pcb_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == PCB_CASES[name][1], [i.code for i in issues]


def test_pcb_too_large() -> None:
    """``altium-build`` "PCB issue codes", "Too large refused"."""
    found = [i for i in run_pcb_too_large() if i.code == "altium.pcb-too-large"]
    assert len(found) == 1 and found[0].severity == "error" and found[0].where == "blink.PcbLib"


@pytest.mark.parametrize("name", sorted(CASES))
def test_case(name: str) -> None:
    issues = run_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == CASES[name][2], [i.code for i in issues]


def test_unique_id_collision() -> None:
    issues = run_unique_id_case()
    found = [i for i in issues if i.code == "altium.unique-id-collision"]
    assert len(found) == 10 and all(i.severity == "error" for i in found)
    assert sum("sheet symbol" in i.message for i in found) == 2, "the symbols of led and power (c0037)"
    assert sum("the port LED_DRV of led" in i.message for i in found) == 1


def run_c0087_cases() -> list[Issue]:
    """The two codes of change c0087: a kept project file that does not list the job, and a drawing
    sheet whose paper the layout does not fit (``tests/_altium_job.py`` holds the cases)."""
    return [*kept_project_issues(), *grown_paper_issues()]


def test_closed_set() -> None:
    produced: dict[str, set[str]] = {}
    for name in CASES:
        for found in run_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for name in KICAD_CASES:
        for found in run_kicad_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for name in PCB_CASES:
        for found in run_pcb_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for name in HIER_CASES:
        for found in run_hier_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for name in COPPER_CASES:
        for found in run_copper_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for found in (*run_routed_sample(), *run_source_cases()):
        produced.setdefault(found.code, set()).add(found.severity)
    for found in (
        *run_unique_id_case(),
        *run_too_large_case(),
        *run_too_large_case("ascii"),
        *run_pcb_too_large(),
    ):
        produced.setdefault(found.code, set()).add(found.severity)
    for found in run_c0087_cases():
        produced.setdefault(found.code, set()).add(found.severity)
    for code, severities in produced.items():
        if code.startswith(PASS_THROUGH):
            continue
        assert code in ALTIUM_ISSUE_CODES, code
        assert severities == {ALTIUM_ISSUE_CODES[code]}, (code, severities)
    assert set(ALTIUM_ISSUE_CODES) <= set(produced), set(ALTIUM_ISSUE_CODES) - set(produced)


def test_the_table() -> None:
    assert dict(ALTIUM_ISSUE_CODES) == {
        "altium.lib-id-form": "error",
        "altium.footprint-form": "error",
        "altium.text-unwritable": "error",
        "altium.name-case-collision": "error",
        "altium.unique-id-collision": "error",
        "altium.schematic-too-large": "error",
        "altium.library-too-large": "error",
        "altium.unknown-pin": "error",
        "altium.symbol-off-grid": "error",
        "altium.pin-text-too-long": "error",
        "altium.symbol-name-collision": "error",
        "altium.pcb-too-large": "error",
        "altium.sheet-name-collision": "error",
        "altium.harness-name": "error",
        "altium.harness-net-shared": "error",
        "altium.harness-power-net": "error",
        "altium.no-footprint": "warning",
        "altium.sheet-custom": "warning",
        "altium.pin-lossy": "warning",
        "altium.footprint-unresolved": "warning",
        "altium.footprint-unsupported": "warning",
        "altium.footprint-name-collision": "warning",
        "altium.sheet-paper": "warning",
        "altium.primitive-dropped": "warning",
        "altium.generic-symbols": "info",
        "altium.symbol-simplified": "info",
        "altium.section-key": "info",
        "altium.schlib-generic": "info",
        "altium.schlib-not-in-project": "info",
        "altium.not-lowered": "info",
        "altium.project-kept": "info",
        "altium.footprint-extras-dropped": "info",
        "altium.pcbdoc-not-written": "info",
        "altium.pcb-staged": "info",
        "altium.pcb-not-in-project": "info",
        "altium.sheets-not-in-project": "info",
        "altium.outjob-not-listed": "info",
        "altium.copper-stack": "error",
        "altium.copper-layer": "error",
        "altium.via-unsupported": "warning",
        "altium.copper-invalid": "error",
        "altium.zone-unsupported": "error",
        "altium.plane-copper": "error",
        "altium.copper-board-mismatch": "error",
        "altium.copper-net-missing": "error",
        "altium.copper-no-document": "error",
        "altium.zones-unpoured": "info",
        "altium.plane-zone-merged": "info",
        "altium.placement-from-board": "info",
    }


def test_too_large_refused() -> None:
    """With ``cfb.MAX_FAT_SECTORS`` patched to 0 the binary build gives no file. The ASCII schematic is not
    limited, but the libraries are always compound files, so the ASCII build gives
    ``altium.library-too-large`` instead (change c0034)."""
    found = [i for i in run_too_large_case() if i.code == "altium.schematic-too-large"]
    assert len(found) == 1 and found[0].severity == "error" and found[0].where == "altium_sample.SchDoc"
    assert "--altium-format ascii" in found[0].hint
    ascii_codes = {i.code for i in run_too_large_case("ascii")}
    assert "altium.schematic-too-large" not in ascii_codes and "altium.library-too-large" in ascii_codes


def test_not_lowered_names_each_kind() -> None:
    found = [i for i in run_case("not-lowered") if i.code == "altium.not-lowered"]
    assert [i.where for i in found] == ["board", "placements", "rules", "interfaces"]
    assert "J1" in found[1].message and "PWR" in found[2].message and "EN/LED_DRV" in found[3].message


def test_errors_write_nothing() -> None:
    for name in ("lib-id", "footprint-form", "non-ascii", "case"):
        design = sample()
        CASES[name][0](design)
        assert build_altium(to_model(design), name=design.name).files == {}


def test_model_issues_pass_through() -> None:
    design = sample()
    design.add(Part("Z1", "L.SchLib:RES", "L.PcbLib:R0603", "1k"))
    connect(Net("FLOATING"), design.parts["Z1"][1])
    codes = [i.code for i in build_altium(to_model(design), name=design.name).issues]
    assert "model.single-pin-net" in codes


def test_library_infos_name_the_libraries() -> None:
    (generic,) = [i for i in run_case("clean") if i.code == "altium.schlib-generic"]
    assert generic.where == "FenoliteSample.SchLib" and "stands in for a real library" in generic.message
    (listing,) = [i for i in run_case("project-kept") if i.code == "altium.schlib-not-in-project"]
    assert "FenoliteSample.SchLib" in listing.message
    (key,) = [i for i in run_case("section-key") if i.code == "altium.section-key"]
    assert "HEADER_HEADER_" in key.message


def test_generic_symbols_only_for_altium_links() -> None:
    assert "altium.generic-symbols" not in {i.code for i in run_kicad_case("kicad-clean")}
    (info,) = [i for i in run_case("clean") if i.code == "altium.generic-symbols"]
    assert info.message.startswith("8 component(s) of Altium links")


def test_off_grid_names_symbol_and_pin() -> None:
    (found,) = [i for i in run_kicad_case("off-grid") if i.code == "altium.symbol-off-grid"]
    assert "FenoliteDemo:R_V pin 1" in found.message and found.where == "FenoliteDemo:R_V"


# --- no-connect marks (change c0036) ----------------------------------------------------------------


def test_no_connect_designator_must_be_writable() -> None:
    design = sample()
    no_connect(design.parts["U2"]["a|b"])
    output = build_altium(to_model(design), name=design.name)
    assert output.files == {}
    found = [i for i in output.issues if i.code == "altium.text-unwritable"]
    assert found and all(i.severity == "error" for i in found)
    assert any(i.where == "U2" and "pin designator" in i.message for i in found)


def test_no_connect_adds_no_altium_code() -> None:
    """A marked pin on a net is ``model.no-connect-on-net``; the table of ``altium.*`` codes is unchanged."""
    assert not [code for code in ALTIUM_ISSUE_CODES if "no-connect" in code]
    design = sample()
    model = to_model(design)
    u2 = next(c for c in model.circuit.components if c.ref == "U2")
    member = next(m for n in model.circuit.nets for m in n.members if m.component_id == u2.id)
    circuit = dataclasses.replace(model.circuit, no_connects=(member,))
    output = build_altium(dataclasses.replace(model, circuit=circuit), name=design.name)
    assert output.files == {}
    (found,) = [i for i in output.issues if i.code == "model.no-connect-on-net"]
    assert found.severity == "error" and found.where == f"U2-{member.pin}"


# --- hierarchy issue codes (change c0037, "Hierarchy issue codes") -----------------------------------

CLEAN = {"altium.generic-symbols", "altium.schlib-generic", "altium.pcbdoc-not-written"}
SECOND_HARNESS = '\ndesign.add(Harness("DBG", {"CLK": spi_sck}))\n'
HIER_CASES: dict[str, tuple[dict[str, str], dict[str, object], set[str]]] = {
    "hier-flat": ({}, {}, CLEAN | {"altium.not-lowered"}),
    "hier-modules": ({}, {"sheets": "modules"}, CLEAN),
    "hier-ascii": ({}, {"sheets": "modules", "form": "ascii"}, CLEAN | {"altium.not-lowered"}),
    "hier-kept": (
        {},
        {"sheets": "modules", "project_exists": True},
        CLEAN | {"altium.project-kept", "altium.schlib-not-in-project", "altium.sheets-not-in-project"},
    ),
    "net-shared": ({"append": SECOND_HARNESS}, {}, {"altium.harness-net-shared", "altium.not-lowered"}),
    "net-twice": (
        {"text": '"CS": spi_cs}', "new": '"CS": spi_cs, "SEL": spi_cs}'},
        {"sheets": "modules"},
        {"altium.harness-net-shared"},
    ),
    "power-net": (
        {"text": '"CS": spi_cs}', "new": '"CS": spi_cs, "GND": gnd}'},
        {},
        {"altium.harness-power-net", "altium.not-lowered"},
    ),
    "entry-separator": (
        {"text": '"CS": spi_cs}', "new": '"CS,1": spi_cs}'},
        {},
        {"altium.harness-name", "altium.not-lowered"},
    ),
    "type-separator": (
        {"text": 'Harness("SPI",', "new": 'Harness("SPI=1",'},
        {"sheets": "modules"},
        {"altium.harness-name"},
    ),
    "type-is-a-net": (
        {"text": 'Harness("SPI",', "new": 'Harness("reset_n",'},
        {"sheets": "modules"},
        {"altium.harness-name"},
    ),
    "type-case": (
        {"append": '\ndesign.add(Harness("spi", {"X": reset_n}))\n'},
        {"sheets": "modules"},
        {"altium.harness-name"},
    ),
    "entry-case": (
        {"text": '"CS": spi_cs}', "new": '"CS": spi_cs, "cs": reset_n}'},
        {"sheets": "modules"},
        {"altium.harness-name"},
    ),
    "entry-unwritable": (
        {"text": '"CS": spi_cs}', "new": '"C|S": spi_cs}'},
        {"sheets": "modules"},
        {"altium.text-unwritable"},
    ),
    "module-case": (
        {"text": 'flash = Module("flash")', "new": 'flash = Module("MCU")'},
        {},
        {"altium.sheet-name-collision", "altium.not-lowered"},
    ),
}
"""Variants of the hierarchy sample (change c0037): script edits, build arguments, and the codes."""


def run_hier_case(name: str) -> tuple[Issue, ...]:
    edits, kwargs, _ = HIER_CASES[name]
    design = hier(edits.get("text", ""), edits.get("new", ""), append=edits.get("append", ""))
    return build_altium(to_model(design), name=design.name, **kwargs).issues  # type: ignore[arg-type]


@pytest.mark.parametrize("name", sorted(HIER_CASES))
def test_hier_case(name: str) -> None:
    issues = run_hier_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == HIER_CASES[name][2], [(i.code, i.message) for i in issues]


@pytest.mark.parametrize(
    "name", ["net-shared", "net-twice", "power-net", "entry-separator", "type-separator", "module-case"]
)
@pytest.mark.parametrize("sheets", ["flat", "modules"])
def test_hierarchy_errors_are_reported_in_both_modes(name: str, sheets: str) -> None:
    """Each error is reported in both modes, so a design is refused before its mode is switched."""
    edits, _, codes = HIER_CASES[name]
    design = hier(edits.get("text", ""), edits.get("new", ""), append=edits.get("append", ""))
    output = build_altium(to_model(design), name=design.name, sheets=sheets)  # type: ignore[arg-type]
    errors = {i.code for i in output.issues if i.severity == "error"}
    assert errors == codes - {"altium.not-lowered"} and output.files == {}


def test_net_in_two_harnesses_names_the_net_and_both_harnesses() -> None:
    (found,) = [i for i in run_hier_case("net-shared") if i.code == "altium.harness-net-shared"]
    assert all(text in found.message for text in ("SPI_SCK", "SPI", "DBG")) and found.where == "SPI_SCK"
    (twice,) = [i for i in run_hier_case("net-twice") if i.code == "altium.harness-net-shared"]
    assert "SPI_CS" in twice.message and "twice in the harness SPI" in twice.message


def test_power_net_in_a_harness_names_the_net() -> None:
    (found,) = [i for i in run_hier_case("power-net") if i.code == "altium.harness-power-net"]
    assert "GND" in found.message and found.where == "SPI"


def test_harness_name_issues_name_the_name() -> None:
    (entry,) = [i for i in run_hier_case("entry-separator") if i.code == "altium.harness-name"]
    assert "'CS,1'" in entry.message
    (kind,) = [i for i in run_hier_case("type-separator") if i.code == "altium.harness-name"]
    assert "'SPI=1'" in kind.message
    (net,) = [i for i in run_hier_case("type-is-a-net") if i.code == "altium.harness-name"]
    assert "'reset_n'" in net.message and "'RESET_N'" in net.message
    (case,) = [i for i in run_hier_case("type-case") if i.code == "altium.harness-name"]
    assert "'SPI'" in case.message and "'spi'" in case.message
    (entries,) = [i for i in run_hier_case("entry-case") if i.code == "altium.harness-name"]
    assert "'CS'" in entries.message and "'cs'" in entries.message
    (unwritable,) = [i for i in run_hier_case("entry-unwritable") if i.code == "altium.text-unwritable"]
    assert "'C|S'" in unwritable.message


def test_module_names_that_differ_in_case() -> None:
    (found,) = [i for i in run_hier_case("module-case") if i.code == "altium.sheet-name-collision"]
    assert "'MCU'" in found.message and "'mcu'" in found.message


def test_harness_not_lowered_names_the_harness_and_the_reason() -> None:
    (flat,) = [i for i in run_hier_case("hier-flat") if i.code == "altium.not-lowered"]
    assert flat.where == "harnesses" and "SPI" in flat.message and "--altium-sheets modules" in flat.hint
    (text,) = [i for i in run_hier_case("hier-ascii") if i.code == "altium.not-lowered"]
    assert "SPI" in text.message and "--altium-format binary" in text.hint
    design = hier(append='\ndesign.add(Harness("LOCAL", {"HOLD": flash_hold_n}))\n')
    issues = build_altium(to_model(design), name=design.name, sheets="modules").issues
    (local,) = [i for i in issues if i.code == "altium.not-lowered"]
    assert "LOCAL" in local.message and "SPI" not in local.message and "leaves" in local.message


def test_sheets_not_in_project_names_the_sheets_and_harness_files() -> None:
    (found,) = [i for i in run_hier_case("hier-kept") if i.code == "altium.sheets-not-in-project"]
    for file in (
        "altium_hier_flash.SchDoc",
        "altium_hier_mcu.SchDoc",
        "altium_hier_flash.Harness",
        "altium_hier_mcu.Harness",
    ):
        assert file in found.message
    assert found.where == "altium_hier.PrjPcb" and found.severity == "info"


def test_unique_id_collision_covers_sheet_symbols_and_ports() -> None:
    with _same_unique_ids():
        design = hier()
        output = build_altium(to_model(design), name=design.name, sheets="modules")
    found = [i for i in output.issues if i.code == "altium.unique-id-collision"]
    assert len(found) == 6 + 2 + 5 - 1 and output.files == {}
    assert sum("the sheet symbol" in i.message for i in found) == 2
    assert sum("the port" in i.message for i in found) == 5


# --- net class names in the schematic (change c0048) -------------------------------------------------


@pytest.mark.parametrize("name", ["=PWR", "P|WR", " PWR"])
def test_net_class_name_is_checked_without_a_pcb_document(name: str) -> None:
    """The schematic holds the class name as a parameter text, so the check does not wait for the PCB
    document ("Classes in an Altium build")."""
    from fenolite.dsl import Design, Net, Part, connect, to_model
    from fenolite.lens.altium import build_altium

    design = Design("classy")
    r1 = Part("R1", "Parts.SchLib:RES", footprint="Parts.PcbLib:R0603")
    first = Net("A")
    connect(first, r1[1])
    design.add(r1)
    design.rules.netclass(name, nets=(first,))
    output = build_altium(to_model(design), name=design.name)
    found = [i for i in output.issues if i.code == "altium.text-unwritable"]
    assert output.files == {} and len(found) == 1
    assert found[0].severity == "error" and f"net class name {name!r}" in found[0].message
