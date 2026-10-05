# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The netlist guard of a build with a schematic (capability design-dsl, "Schematic netlist guard in a
build"; change c0063): the generated sheet is read back without a tool and must mean the circuit."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import replace

import pytest
from _buildhelp import blink, build, codes
from _schbuild import blink_unmarked, built_units, units_design

from fenolite.backends.kicad import schgen, schlayout
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.core.coords import Point
from fenolite.dsl import Net, Part, connect
from fenolite.lens.build import BUILD_ISSUE_CODES, BuildOutput, schematic_netlist_issue
from fenolite.model.schematic import SchematicSheet

CODE = "build.schematic-netlist-differs"
Change = Callable[[SchematicSheet], SchematicSheet]


def pin_points(sheet: SchematicSheet, ref: str) -> dict[str, Point]:
    """Pin number → connection point of the first unit of ``ref``."""
    instance = next(s for s in sheet.symbols if s.ref == ref)
    definition = next(d for d in sheet.lib_symbols if d.lib_id == instance.lib_ref)
    return {
        pin.number: schlayout.pin_point(instance.position, pin.position)
        for pin in definition.pins_of(instance.unit, instance.body_style)
    }


def swapped_labels(sheet: SchematicSheet) -> SchematicSheet:
    """The defect of the scenario: the labels of the two pins of ``R1`` change places."""
    points = pin_points(sheet, "R1")
    other = {points["1"]: points["2"], points["2"]: points["1"]}
    labels = tuple(
        replace(label, position=other.get(label.position, label.position)) for label in sheet.labels
    )
    assert labels != sheet.labels
    return replace(sheet, labels=labels)


def label_on_the_other_pin(sheet: SchematicSheet) -> SchematicSheet:
    """The label of ``R1`` pin 2 lies on pin 1, beside the label of that pin."""
    points = pin_points(sheet, "R1")
    labels = tuple(
        replace(label, position=points["1"]) if label.position == points["2"] else label
        for label in sheet.labels
    )
    return replace(sheet, labels=labels)


def without_label(sheet: SchematicSheet) -> SchematicSheet:
    """``R1`` pin 2 loses its label, so the sheet leaves it open."""
    point = pin_points(sheet, "R1")["2"]
    return replace(sheet, labels=tuple(label for label in sheet.labels if label.position != point))


def patched(monkeypatch: pytest.MonkeyPatch, change: Change) -> None:
    real = schgen.generate_schematic

    def defective(*args: object, **kwargs: object) -> GeneratedSchematic:
        generated = real(*args, **kwargs)  # type: ignore[arg-type]
        return replace(generated, sheet=change(generated.sheet))

    monkeypatch.setattr(schgen, "generate_schematic", defective)


@pytest.mark.parametrize("target", [9, 10])
def test_examples_pass_the_guard(target: int) -> None:
    for output, name in ((build(blink(), target), "blink"), (built_units(target), "units")):
        assert CODE not in codes(output)
        assert f"{name}.kicad_sch" in output.files
    assert "blink.kicad_sch" in build(blink_unmarked(), target).files


def test_generator_defect_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    patched(monkeypatch, swapped_labels)
    output = build(blink())
    assert output.files == {}
    assert output.schematic is None
    (found,) = [issue for issue in output.issues if issue.code == CODE]
    assert found.severity == "error"
    assert "LED_A" in found.message or "LED_DRV" in found.message
    assert "R1-1" in found.message or "R1-2" in found.message
    assert found.where in ("R1-1", "R1-2")
    assert "more)" in found.message, "both pins of R1 and both nets differ"


def test_two_labels_on_one_pin_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    patched(monkeypatch, label_on_the_other_pin)
    output = build(blink())
    assert output.files == {}
    (found,) = [issue for issue in output.issues if issue.code == CODE]
    assert "two-names" in found.message and found.where == "blink.kicad_sch"


def test_missing_label_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    patched(monkeypatch, without_label)
    output = build(blink())
    assert output.files == {}
    (found,) = [issue for issue in output.issues if issue.code == CODE]
    assert "LED_A" in found.message


def test_skipped_schematic_runs_no_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    patched(monkeypatch, swapped_labels)
    output = build(blink(), schematic="skip")
    assert CODE not in codes(output)
    assert "blink.kicad_pcb" in output.files and "blink.kicad_sch" not in output.files


def test_hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the guard runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    output = build(blink())
    assert "blink.kicad_sch" in output.files and CODE not in codes(output)


def test_code_is_a_build_code() -> None:
    assert BUILD_ISSUE_CODES[CODE] == "error"


# -- the comparison itself


def generated_of(name: str) -> tuple[BuildOutput, GeneratedSchematic]:
    output = build(blink()) if name == "blink" else built_units()
    assert output.schematic is not None
    return output, output.schematic


def test_agreement_gives_no_issue() -> None:
    for name in ("blink", "units"):
        output, generated = generated_of(name)
        assert schematic_netlist_issue(output.design, generated, name) is None


def test_wrong_variant_is_caught() -> None:
    """The mapped LED embedded without its pin-pad map: the label of pin 1 names pad 1, not pad 2."""
    output, generated = generated_of("units")
    plain = next(d for d in generated.sheet.lib_symbols if d.name.startswith("Mini_LED"))
    pins = tuple(replace(pin, number={"1": "2", "2": "1"}[pin.number]) for pin in plain.pins)
    definitions = tuple(replace(d, pins=pins) if d is plain else d for d in generated.sheet.lib_symbols)
    defective = replace(generated, sheet=replace(generated.sheet, lib_symbols=definitions))
    found = schematic_netlist_issue(output.design, defective, "units")
    assert found is not None and "D1-" in found.message


def test_two_nets_under_one_stored_name_are_caught() -> None:
    """A net named with ``{slash}`` and one named with ``/`` are one net for KiCad."""
    design = units_design()
    extra = Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    design.add(extra)
    connect(Net("mod{slash}LED_A"), extra[1])
    output = build(design)
    assert output.files == {}
    assert CODE in codes(output)


def test_pin_without_a_known_name_only_needs_its_own_net() -> None:
    output, generated = generated_of("blink")
    pad_nets = {key: value for key, value in generated.pad_nets.items() if key[1] != "2"}
    assert len(pad_nets) == len(generated.pad_nets) - 1
    assert schematic_netlist_issue(output.design, replace(generated, pad_nets=pad_nets), "blink") is None


def test_pad_net_under_another_name_is_caught() -> None:
    output, generated = generated_of("blink")
    key = next(k for k in generated.pad_nets if k[1] == "2")
    defective = replace(generated, pad_nets={**generated.pad_nets, key: "unconnected-(U1-OTHER-Pad2)"})
    found = schematic_netlist_issue(output.design, defective, "blink")
    assert found is not None and "U1-2" in found.message
