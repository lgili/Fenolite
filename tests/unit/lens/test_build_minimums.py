# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Script rule minimums in builds (capability design-dsl, "Rule minimums in the DSL"; altium-build, "Rule
minimums in an Altium build"; change c0054)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from _altium import blink as altium_blink
from _altium import blink_resolver, blink_tree, example, example_resolver
from _buildhelp import blink, build

from fenolite.backends.kicad.dru import read_rules
from fenolite.core.errors import Issue
from fenolite.dsl import Design, mm, placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.preserve import ExistingProject, prepare

DRU = "blink.kicad_dru"


def with_minimums(design: Design, width: str = "0.25mm") -> Design:
    design.rules.minimum(clearance=mm(0.15), track_width=width)
    design.rules.minimum(clearance=mm(0.2), track_width=mm(0.5), netclass="PWR")
    return design


def test_built_rules_and_minimums() -> None:
    output = build(with_minimums(blink()), 10)
    assert not [i for i in output.issues if i.severity == "error"]
    text = output.files[DRU].decode("utf-8")
    lowered = read_rules(text).rules
    assert [r.name for r in lowered] == [
        "fenolite_0_min_clearance",
        "fenolite_0_min_track_width",
        "fenolite_1_min_clearance_pwr",
        "fenolite_1_min_track_width_pwr",
    ]
    assert text.count("(condition \"A.NetClass == 'PWR'\")") == 2
    assert "(constraint track_width (min 0.5mm))" in text
    setup = json.loads(output.files["blink.kicad_pro"])["board"]["design_settings"]["rules"]
    assert (setup["min_clearance"], setup["min_track_width"]) == (0.15, 0.25)
    model = json.loads(output.files[".fenolite/rules.json"])
    assert sorted(r["name"] for r in model["rules"]) == [
        "min_clearance",
        "min_clearance_PWR",
        "min_track_width",
        "min_track_width_PWR",
    ]


def test_target_9_holds_the_same_rules() -> None:
    assert build(with_minimums(blink()), 9).files[DRU] == build(with_minimums(blink()), 10).files[DRU]


def test_unchanged_without_minimums() -> None:
    output = build(blink(), 10)
    assert output.files[DRU] == b"(version 1)\n"
    assert json.loads(output.files[".fenolite/rules.json"]).get("rules", []) == []


def test_a_shadowed_class_clearance_is_reported() -> None:
    design = blink()  # class PWR has a clearance of 0.2 mm
    design.rules.minimum(clearance=mm(0.15))
    assert "kicad.project.class-shadowed" in [i.code for i in build(design, 10).issues]
    design.rules.minimum(clearance=mm(0.2), netclass="PWR")
    assert "kicad.project.class-shadowed" not in [i.code for i in build(design, 10).issues]


def test_rebuild_replaces_the_minimums() -> None:
    def script(width: str) -> Design:
        design = blink()
        design.rules.minimum(track_width=width)
        return design

    first = build(script("0.25mm"), 10)
    by_hand = first.files[DRU].decode("utf-8") + "(rule mine\n\t(constraint clearance (min 0.3mm))\n)\n"
    design = script("0.3mm")
    existing = ExistingProject(
        board=first.files["blink.kicad_pcb"].decode("utf-8"),
        project=first.files["blink.kicad_pro"].decode("utf-8"),
        rules=by_hand,
    )
    ready = prepare(to_model(design), placements(design), existing, name="blink")
    second = build(design, 10, prepared=ready, placements_override=ready.placements)
    text = second.files[DRU].decode("utf-8")
    assert text.count("fenolite_0_min_track_width") == 1 and "(min 0.3mm)" in text and "0.25mm" not in text
    assert [r.name for r in read_rules(text).rules] == ["fenolite_0_min_track_width", "mine"]
    setup = json.loads(second.files["blink.kicad_pro"])["board"]["design_settings"]["rules"]
    assert setup["min_track_width"] == 0.3


def _altium(document: bool, minimums: bool) -> tuple[dict[str, bytes], tuple[Issue, ...]]:
    """The Altium build of the blink with its PCB document, or of the KiCad-sourced sample (given a class
    ``PWR``) without one; ``minimums`` adds a board and a class minimum."""
    design = altium_blink() if document else example()
    if not document:
        design.rules.netclass("PWR", track_width=mm(0.4))
    if minimums:
        design.rules.minimum(clearance=mm(0.15))
        design.rules.minimum(track_width=mm(0.5), netclass="PWR")
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        if document:
            output = build_altium(
                to_model(design),
                name=design.name,
                placed=tuple(placements(design)),
                placements=placements(design),
                resolver=blink_resolver(root, blink_tree(root)),
            )
        else:
            output = build_altium(to_model(design), name=design.name, resolver=example_resolver(root))
    assert output.files, [i.message for i in output.issues]
    assert any(name.endswith(".PcbDoc") for name in output.files) is document
    return dict(output.files), output.issues


@pytest.mark.parametrize("document", [False, True])
def test_altium_reports_minimums_and_writes_the_same_files(document: bool) -> None:
    plain_files, plain_issues = _altium(document, minimums=False)
    files, issues = _altium(document, minimums=True)
    (info,) = [i for i in issues if i.where == "design-rules"]
    assert (info.code, info.severity) == ("altium.not-lowered", "info")
    assert "min_clearance, min_track_width_PWR" in info.message
    assert b"min_track_width_PWR" in files.pop(".fenolite/rules.json")
    assert b"min_" not in plain_files.pop(".fenolite/rules.json")
    assert files == plain_files  # the model keeps the rules; no written file holds them
    assert [i for i in issues if i is not info] == list(plain_issues)
    assert not [i for i in plain_issues if i.where == "design-rules"]
