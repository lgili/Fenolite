# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0346: exact cyclic orientation is physical equivalence, never model/codec normalization."""

from __future__ import annotations

from dataclasses import replace

import pytest
from _cases import two_layer, with_footprint

from fenolite.checks.equivalence import compare_designs
from fenolite.checks.equivalence.model import EXACT, Tolerances
from fenolite.model import canonical
from fenolite.model.design import Design


def rotated(surface: str, angle: int) -> Design:
    source = two_layer()
    assert source.board is not None
    if surface == "board":
        text = replace(source.board.texts[0], rotation=angle)
        return replace(source, board=replace(source.board, texts=(text,)))
    if surface == "footprint-text":
        text = replace(source.board.texts[0], rotation=angle)
        return with_footprint(source, "R1", lambda fp: replace(fp, texts=(text,)))
    return with_footprint(
        source,
        "R1",
        lambda fp: replace(
            fp, fields=tuple(replace(f, rotation=angle) if f.name == "Reference" else f for f in fp.fields)
        ),
    )


@pytest.mark.parametrize("surface", ["board", "footprint-text", "field"])
@pytest.mark.parametrize("angles", [(0, 360_000_000), (-90_000_000, 270_000_000), (45_000_001, 405_000_001)])
def test_exact_cyclic_orientation_does_not_rewrite_model(surface: str, angles: tuple[int, int]) -> None:
    first, second = (rotated(surface, angle) for angle in angles)
    snapshots = canonical.dumps(first), canonical.dumps(second)
    assert snapshots[0] != snapshots[1]
    report = compare_designs(first, second, level=7, strict=True)
    assert report.levels[-1].differences == ()
    assert (canonical.dumps(first), canonical.dumps(second)) == snapshots


@pytest.mark.parametrize("surface", ["board", "footprint-text", "field"])
@pytest.mark.parametrize("other", [90_000_000, 180_000_000, 1])
def test_true_rotation_remains_a_difference_even_with_length_tolerance(surface: str, other: int) -> None:
    first, second = rotated(surface, 0), rotated(surface, other)
    report = compare_designs(
        first, second, level=7, strict=True, tolerances=Tolerances(length_nm=360_000_000)
    )
    assert [d.field for d in report.levels[-1].differences] == ["rotation"]


def test_only_angular_tolerance_applies_to_orientation() -> None:
    first, second = rotated("board", 0), rotated("board", 1)
    assert compare_designs(first, second, level=7, strict=True).levels[-1].differences
    assert (
        not compare_designs(first, second, level=7, strict=True, tolerances=Tolerances(angle_udeg=1))
        .levels[-1]
        .differences
    )


def test_noncyclic_and_generic_values_do_not_gain_orientation_semantics() -> None:
    from fenolite.checks.equivalence.rules import field_differences

    assert field_differences("authored", "probe", {"sweep": 0}, {"sweep": 360_000_000}, EXACT)
    assert field_differences("authored", "probe", {"rotation": 0}, {"rotation": 360_000_000}, EXACT)
    assert field_differences(
        "authored", "probe", {"sweep": 0}, {"sweep": 360_000_000}, EXACT, orientation_paths=("rotation",)
    )


@pytest.mark.parametrize("one,other", [(None, 0), (False, 0), (True, 1), (None, False)])
def test_orientation_metric_preserves_typed_presence(
    one: int | bool | None, other: int | bool | None
) -> None:
    from fenolite.checks.equivalence.rules import field_differences

    assert field_differences(
        "text-field", "probe", {"rotation": one}, {"rotation": other}, EXACT, orientation_paths=("rotation",)
    )


def test_angular_tolerance_cannot_make_noncyclic_sweep_equal() -> None:
    from fenolite.checks.equivalence.rules import field_differences

    assert field_differences(
        "authored", "probe", {"sweep": 0}, {"sweep": 360_000_000}, Tolerances(angle_udeg=360_000_000)
    )
