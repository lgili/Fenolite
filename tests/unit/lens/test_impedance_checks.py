# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Impedance targets in a build (capability design-dsl, "Impedance targets in a build"; change c0105)."""

from __future__ import annotations

import dataclasses

from _buildhelp import build
from _zdesign import zdesign

from fenolite.core.errors import Issue
from fenolite.dsl import to_model
from fenolite.lens.build import BUILD_ISSUE_CODES, BuildOutput, impedance_checks

CODES = (
    "build.impedance-layer",
    "build.impedance-shadowed",
    "build.impedance-class-width",
    "build.impedance-gap-clearance",
    "build.impedance-stackup",
    "build.impedance-rules-only",
)


def _of(output: BuildOutput | list[Issue], code: str) -> list[Issue]:
    issues = output.issues if isinstance(output, BuildOutput) else output
    return [i for i in issues if i.code == code]


def test_codes_join_the_build_set() -> None:
    assert {code: BUILD_ISSUE_CODES[code] for code in CODES} == {
        "build.impedance-layer": "error",
        "build.impedance-shadowed": "warning",
        "build.impedance-class-width": "warning",
        "build.impedance-gap-clearance": "warning",
        "build.impedance-stackup": "warning",
        "build.impedance-rules-only": "info",
    }


def test_design_without_targets_gives_none() -> None:
    output = build(zdesign(se50=False, usb90=False, stackup=None), target=10)
    assert not [i for i in output.issues if i.code in CODES]


def test_layer_not_on_the_board() -> None:
    output = build(zdesign(copper=2, usb90=False, stackup=None), target=10)
    found = _of(output, "build.impedance-layer")
    assert len(found) == 2 and "In1.Cu" in found[0].message and "In2.Cu" in found[1].message
    assert output.files == {}


def test_class_minimum_does_not_shadow() -> None:
    output = build(zdesign(usb90=False, extra='design.rules.minimum(track_width=mm(0.2), netclass="SE50")\n'))
    assert not _of(output, "build.impedance-shadowed")
    dru = output.files["blink.kicad_dru"].decode("utf-8")
    assert dru.index('"fenolite_1_min_track_width_se50"') < dru.index('"fenolite_1_track_width_se50_f_cu"')
    assert dru.index('"fenolite_1_min_track_width_se50"') < dru.index('"fenolite_1_track_width_se50_b_cu"')


def test_a_later_rule_shadows_the_target() -> None:
    extra = (
        "from fenolite.dsl import select\n"
        'design.rules.rule("wide", "track_width", where=select.netclass("SE50"), min=mm(0.3), priority=1)\n'
    )
    found = _of(build(zdesign(usb90=False, extra=extra)), "build.impedance-shadowed")
    assert len(found) == 2
    assert all("wide" in i.message and "SE50" in i.message for i in found)
    assert {"F.Cu", "B.Cu"} == {layer for i in found for layer in ("F.Cu", "B.Cu") if layer in i.message}


def test_area_rule_does_not_shadow() -> None:
    extra = (
        "from fenolite.dsl import select\n"
        'design.rule_area("neck", outline=((mm(1), mm(1)), (mm(5), mm(1)), (mm(5), mm(5))), '
        'layers=("F.Cu",))\n'
        'design.rules.rule("wneck", "track_width", where=select.netclass("SE50") & select.area("neck"), '
        "min=mm(0.1), priority=1)\n"
    )
    assert not _of(build(zdesign(usb90=False, extra=extra)), "build.impedance-shadowed")


def test_kicad_9_build() -> None:
    output = build(zdesign(se50=False), target=9)
    assert len(_of(output, "build.impedance-rules-only")) == 1
    (gap,) = _of(output, "build.impedance-gap-clearance")
    assert "USB90" in gap.message and "0.15 mm" in gap.message and "0.2 mm" in gap.message
    assert not _of(output, "build.impedance-stackup")
    assert "tuning_profiles" not in output.files["blink.kicad_pro"].decode("utf-8")


def test_kicad_10_gives_no_gap_clearance() -> None:
    output = build(zdesign(se50=False), target=10)
    assert not _of(output, "build.impedance-gap-clearance") and not _of(output, "build.impedance-rules-only")


def test_stackup_not_marked() -> None:
    found = _of(build(zdesign(usb90=False, stackup=False)), "build.impedance-stackup")
    assert len(found) == 1
    assert "SE50" in found[0].message and "impedance_controlled" in found[0].message + found[0].hint


def test_no_stackup() -> None:
    found = _of(build(zdesign(usb90=False, stackup=None)), "build.impedance-stackup")
    assert len(found) == 1 and "no stack-up" in found[0].message


def test_class_width_differs() -> None:
    script = zdesign(usb90=False)
    script.rules.netclasses["SE50"] = dataclasses.replace(
        script.rules.netclasses["SE50"], track_width=300_000
    )
    found = _of(impedance_checks(to_model(script), target=10), "build.impedance-class-width")
    assert len(found) == 2 and "0.3 mm" in found[0].message and "0.35 mm" in found[0].message


def test_checks_change_nothing() -> None:
    model = to_model(zdesign())
    before = model
    impedance_checks(model, target=9)
    assert model == before
