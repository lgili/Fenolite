# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored circuits verify native output without depending on vendor libraries."""

from dataclasses import replace

import pytest
from _altium import dual_symbol, hier_model, sample_model

from fenolite.backends.altium.altsym import from_symbol_def
from fenolite.backends.altium.composition import compose_project, frame_boxes
from fenolite.backends.altium.hierarchy import plan_sheets
from fenolite.backends.altium.project import write_project
from fenolite.backends.altium.read import sch
from fenolite.backends.altium.schdoc import schdoc_records
from fenolite.backends.altium.schdot import SheetFrame
from fenolite.backends.altium.verification import verify
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Net, Part, connect, to_model
from fenolite.lens.altium import generic_pins, sheet_frames
from fenolite.model.presentation import DrawingSheet, SheetFrameRef, SheetSetup
from fenolite.schematic.composition import CompositionError, validate_plan
from fenolite.schematic.intent import BlockIntent, CompositionIntent


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_native_composition_preserves_complete_electrical_identity(form):
    model = sample_model()
    before = write_project(model, name="sample", form=form)
    after = write_project(model, name="sample", form=form, composition=CompositionIntent())
    verify({"sample.SchDoc": before["sample.SchDoc"]}, {"sample.SchDoc": after["sample.SchDoc"]})
    assert before["sample.SchDoc"] != after["sample.SchDoc"]
    assert before["FenoliteSample.SchLib"] == after["FenoliteSample.SchLib"]
    document = sch.read_schematic(after["sample.SchDoc"], file="sample.SchDoc")
    assert not document.issues
    assert len(document.components()) == len(model.circuit.components)


def test_plan_geometry_and_legacy_bytes_are_stable():
    model = sample_model()
    legacy = write_project(model, name="sample")
    assert legacy == write_project(model, name="sample", composition=None)
    planned = plan_sheets(model, name="sample", sheets="flat", form="binary")
    composed = compose_project(planned, model, CompositionIntent())
    assert composed == compose_project(planned, model, CompositionIntent())
    plan = composed.top.plan.composition
    assert plan is not None
    validate_plan(plan)
    assert len(plan.placements) == len(planned.top.plan.parts)
    blocks = (BlockIntent("input", ("J1",), "Input"), BlockIntent("driver", ("R2", "U2"), "Driver"))
    intent = CompositionIntent(blocks=blocks)
    other = replace(
        intent, blocks=(replace(blocks[1], members=tuple(reversed(blocks[1].members))), blocks[0])
    )
    assert write_project(model, name="sample", composition=intent) == write_project(
        model, name="sample", composition=other
    )


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_multiunit_symbol_and_hierarchy_keep_all_identities(form):
    d = Design("dual")
    u = Part("U1", "Demo.SchLib:DUAL", footprint="Demo.PcbLib:DEVICE")
    d.add(u)
    for number in range(1, 9):
        connect(Net(f"N{number}"), u[number])
    model = generic_pins(to_model(d))
    symbols = {"Demo.SchLib:DUAL": from_symbol_def(dual_symbol(), lib_ref="DUAL", footprint=None)}
    old = write_project(model, name="dual", form=form, symbols=symbols)
    new = write_project(model, name="dual", form=form, symbols=symbols, composition=CompositionIntent())
    verify({"dual.SchDoc": old["dual.SchDoc"]}, {"dual.SchDoc": new["dual.SchDoc"]})
    assert len(sch.read_schematic(new["dual.SchDoc"], file="dual.SchDoc").components()) == 2
    hierarchy = hier_model()
    old = write_project(hierarchy, name="hier", sheets="modules", form=form)
    new = write_project(hierarchy, name="hier", sheets="modules", form=form, composition=CompositionIntent())
    verify(
        {k: v for k, v in old.items() if k.endswith(".SchDoc")},
        {k: v for k, v in new.items() if k.endswith(".SchDoc")},
    )


def test_fixed_metric_template_is_quantized_without_growing_and_overflow_refuses():
    d = Design("single")
    p = Part("U1", "Demo.SchLib:ONE", footprint="Demo.PcbLib:DEVICE")
    d.add(p)
    connect(Net("SIGNAL"), p[1])
    model = generic_pins(to_model(d))
    assert model.board is not None
    model = replace(model, board=replace(model.board, sheet=SheetFrameRef(paper="A4")))
    planned = plan_sheets(model, name="sample", sheets="flat", form="ascii")
    template = DrawingSheet(
        id=derived_id("wks", "composition", "authored"),
        name="authored",
        setup=SheetSetup(
            (1_000_000, 1_000_000), 100_000, 100_000, 10_000_000, 10_000_000, 10_000_000, 10_000_000
        ),
    )
    frames, info = sheet_frames(model, planned, template, [], composition=True)
    native = compose_project(planned, model, CompositionIntent(), frames)
    assert native.top.plan.size.width * 25_400 <= 297_000_000
    assert native.top.plan.size.height * 25_400 <= 210_000_000
    assert info["pages"]
    issues = []
    written = write_project(
        model, name="sample", frames=frames, composition=CompositionIntent(), issues=issues
    )
    assert written["sample.SchDoc"]
    assert not any(i.code == "altium.sheet-custom" for i in issues)
    tiny = replace(
        model,
        board=replace(model.board, sheet=SheetFrameRef(paper="custom", width=25_400_000, height=25_400_000)),
    )
    with pytest.raises(CompositionError, match="block envelope"):
        compose_project(planned, tiny, CompositionIntent())


def test_readback_refuses_a_defective_emitted_net():
    original = write_project(sample_model(), name="sample", form="ascii")["sample.SchDoc"]
    broken = original.replace(b"LED_DRV", b"CHANGED_NET")
    with pytest.raises(CompositionError) as caught:
        verify({"sample.SchDoc": original}, {"sample.SchDoc": broken})
    assert caught.value.issues[0].code == "composition.connectivity-changed"


def test_rotated_cached_geometry_and_fields_match_native_plan():
    model = sample_model()
    native = compose_project(
        plan_sheets(model, name="sample", sheets="flat", form="ascii"), model, CompositionIntent()
    ).top.plan
    rotated = [p for p in native.parts if p.rotation]
    assert rotated, "the authored passive branches exercise a quarter turn"
    rows = [dict(r) for r in schdoc_records(native)]
    for placed in rotated:
        index, component = next(
            (i, row)
            for i, row in enumerate(rows)
            if row.get("RECORD") == "1" and row.get("UNIQUEID") == placed.spec.part_id(placed.part)
        )
        assert component["ORIENTATION"] == str(placed.rotation)
        children = [r for r in rows if r.get("OWNERINDEX") == str(index)]
        for rectangle in (r for r in children if r["RECORD"] == "14"):
            assert int(rectangle["LOCATION.X"]) <= int(rectangle["CORNER.X"])
            assert int(rectangle["LOCATION.Y"]) <= int(rectangle["CORNER.Y"])
        fields = [r for r in children if r["RECORD"] in ("34", "41") and r.get("ISHIDDEN") != "T"]
        assert all(r.get("ORIENTATION", "0") == "0" for r in fields)
        for original in placed.spec.body.pins:
            emitted = next(
                r for r in children if r["RECORD"] == "2" and r["DESIGNATOR"] == original.designator
            )
            assert int(emitted["PINCONGLOMERATE"]) & 3 == (original.direction + placed.rotation) % 4


def test_unbounded_template_refuses_and_parameter_font_bounds_are_conservative():
    size = plan_sheets(sample_model(), name="sample", sheets="flat", form="ascii").top.plan.size
    text = (("RECORD", "4"), ("FONTID", "2"), ("TEXT", "=Title"), ("LOCATION.X", "10"), ("LOCATION.Y", "10"))
    parameter = (("RECORD", "41"), ("NAME", "Title"), ("TEXT", "Long title" * 5), ("ISHIDDEN", "T"))
    frame = SheetFrame(size.width // 10, size.height // 10, ((40, False, False),), (text, parameter))
    (box,) = frame_boxes(frame, size)
    assert box.width > 50 * 200 * 25_400
    with pytest.raises(CompositionError, match="unresolved template text"):
        frame_boxes(replace(frame, records=(text,)), size)
    with pytest.raises(CompositionError, match="unbounded frame record"):
        frame_boxes(replace(frame, records=((("RECORD", "30"),),)), size)
