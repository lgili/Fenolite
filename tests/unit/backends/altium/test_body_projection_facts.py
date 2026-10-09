# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independently authored signed-height probes; no private geometry."""

from fractions import Fraction

import _altium_records as rec
import pytest

from fenolite.backends.altium.read.bodies import encode, read_bodies


@pytest.mark.parametrize("projection", [0, 1, 73])
def test_signed_bounds_and_opaque_projection_are_not_clamped(projection: int) -> None:
    data = rec.body_bytes(
        fields={"STANDOFFHEIGHT": "-12mil", "OVERALLHEIGHT": "36mil", "BODYPROJECTION": str(projection)}
    )
    (body,) = read_bodies(data)
    assert body.standoff_height == Fraction(-120_000)
    assert body.overall_height == Fraction(360_000)
    assert body.body_projection == projection
    assert encode((body,)) == data
