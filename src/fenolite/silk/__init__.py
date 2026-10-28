# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Silkscreen layout (capability silkscreen-layout; changes c0212 and c0226): the ink of stroke texts
(``extents``), the search for designator places (``layout``) and its use on a KiCad board (``board``), and
the cut of silkscreen strokes at mask openings (``cut``, ``clip``). The command is ``fenolite silk``
(``docs/cli-contract.md``, "silk"; ``docs/assembly.md``, "Designators" and "Clipping")."""

from __future__ import annotations

from fenolite.silk.extents import Ink, InkBox, InkCache, TextKey, estimate, ink_box, ink_boxes

__all__ = ["Ink", "InkBox", "InkCache", "TextKey", "estimate", "ink_box", "ink_boxes"]
