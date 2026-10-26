# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Structured composition diagnostics remain stable and identify exact units."""

import json

import pytest

from fenolite.schematic.composition import Box, Primitive, Unit, compose_sheet
from fenolite.schematic.intent import CompositionIntent
from fenolite.schematic.report import REPORT_FILE, artifacts, preview_file, report


def plan():
    body = Box(0, 0, 2_540_000, 2_540_000)
    unit = Unit(
        "U1#1",
        "U1",
        1,
        "sample.SchDoc",
        "U1",
        "value",
        body,
        (),
        (Primitive("rectangle", ((0, 0), (2_540_000, 2_540_000))),),
    )
    return compose_sheet(
        (unit,), CompositionIntent(), sheet=unit.sheet, region=Box(0, 0, 100_000_000, 100_000_000)
    )


def test_report_and_artifacts_are_deterministic_and_baseline_scoped():
    composed = plan()
    files = artifacts((composed,))
    assert files == artifacts((composed,))
    value = json.loads(files[REPORT_FILE])
    assert value["origin"] == "generated-baseline"
    assert value["evidence"]["native_review"] == "unmeasured"
    unit = value["sheets"][0]["placements"][0]
    assert unit["unit"] == "U1#1" and unit["origin"] == list(composed.placements[0].origin)
    assert report((composed,), replayed=(composed.sheet,))["replayed_sheets"] == [composed.sheet]


def test_preview_paths_are_safe():
    for name in ("../sheet", "a/b", "a\\b", "a:b", "..", ""):
        with pytest.raises(ValueError):
            preview_file(name)
