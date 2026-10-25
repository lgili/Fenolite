# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Assembly variants of an Altium project (capability variant-view, scenario "An authored variant"; change
c0186). The variant is authored in the test and resolved on Fenolite's own `blink` sheet."""

from __future__ import annotations

from pathlib import Path

from _variants import variant_text

from fenolite.backends.altium.read.variants import NOT_FITTED, read_variants
from fenolite.cli.cmd_view import scene_of
from fenolite.view.variants import counts, variant_states

BLINK = Path(__file__).resolve().parents[3] / "tests" / "data" / "altium" / "blink"


def test_authored_variant() -> None:
    sheet = scene_of(BLINK / "blink.SchDoc")
    r1 = next(c for c in sheet["comps"] if c["ref"] == "R1")
    (variant,) = read_variants(variant_text(r1["uid"]).encode())
    assert variant.name == "Lite" and variant.variations[0].kind == NOT_FITTED
    states = variant_states((variant,), {"blink.SchDoc": sheet})["Lite"]
    assert states["R1"]["kind"] == "not fitted"  # matched by its unique id, not its old designator R?
    assert states["D1"]["params"] == {"Value": "22n"} and states["D1"]["kind"] == "fitted"
    refs = [c["ref"] for c in sheet["comps"]]
    assert counts(states, refs) == {"fitted": len(refs) - 1, "not_fitted": 1}


def test_project_without_variants() -> None:
    assert read_variants((BLINK / "blink.PrjPcb").read_bytes()) == ()
