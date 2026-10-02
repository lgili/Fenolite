# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Blink variants of the preservation tests (change c0019)."""

from __future__ import annotations

from fenolite.dsl import Design


def without_r1(design: Design) -> Design:
    """``design`` (the blink) with ``R1`` removed; its pins leave every net with it, because ``to_model``
    reads net members from the added parts' connections."""
    r1 = design.parts.pop("R1")
    design.children = [c for c in design.children if c is not r1]
    return design


__all__ = ["without_r1"]
