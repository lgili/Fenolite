# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The variants of a project file (``read/variants.py``, change c0186). The sections are authored here."""

from __future__ import annotations

from fenolite.backends.altium.read.variants import ALTERNATE, FITTED, NOT_FITTED, read_variants

TEXT = """[Design]
Version=1.0

[ProjectVariant1]
Description=Lite
UniqueID=ABCDEFGH
VariationCount=3
Variation1=Designator=R1|UniqueId=\\RUIDAAAA|Kind=1|AlternatePart=
Variation2=Designator=C1|UniqueId=\\RUIDBBBB|Kind=2|AlternatePart=C0603
Variation3=Designator=U1|UniqueId=\\RUIDCCCC|Kind=7|AlternatePart=
ParamVariationCount=1
ParamVariation1=ParameterName=Value|VariantValue=22n
ParamDesignator1=D1

[ProjectVariant2]
Description=Full
"""


def test_variant_kinds_and_parameters() -> None:
    lite, full = read_variants(TEXT.encode())
    assert (lite.name, lite.unique_id, full.name, full.variations) == ("Lite", "ABCDEFGH", "Full", ())
    assert [v.kind for v in lite.variations] == [NOT_FITTED, ALTERNATE, 7]
    assert lite.unknown_kinds == 1 and not lite.variations[0].fitted and lite.variations[1].fitted
    assert dict(lite.variations[1].fields)["AlternatePart"] == "C0603"
    assert lite.variation("X?", "\\RUIDBBBB") is lite.variations[1]
    assert lite.variation("R1") is lite.variations[0]
    assert lite.parameters == {"D1": {"Value": "22n"}} and FITTED == 0
