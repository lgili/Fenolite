# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium project variant authored for Fenolite's tests (change c0186): keys from
``docs/formats/altium/project.md``, "Variants", values of the tests."""

from __future__ import annotations


def variant_text(uid: str) -> str:
    """A variant that does not fit R1 (named by its unique id under an old designator) and sets D1's
    value."""
    return (
        "[ProjectVariant1]\r\nUniqueID=0000\r\nDescription=Lite\r\nAllowFabrication=0\r\nParameterCount=0\r\n"
        f"VariationCount=1\r\nVariation1=Designator=R?|UniqueId=\\{uid}|Kind=1|AlternatePart= \r\n"
        "ParamVariationCount=1\r\nParamVariation1=ParameterName=Value|VariantValue=22n\r\nParamDesignator1=D1\r\n"
    )
