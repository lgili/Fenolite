# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The land constants ``lands/1`` (change c0260). Written by ``tools/calibrate_lands.py``; do not edit.

Calibrated values come from the cited manufacturer patterns of ``tests/data/packages/calibration``;
``pad_gap``, ``grid``, ``courtyard``, ``hole_clearance``, ``annular_ring``, ``paste_cell`` and
``paste_window`` are Fenolite's own choices
(``docs/formats/library/lands.md``). Every value is ``INFERRED``."""

from __future__ import annotations

from fenolite.catalog.footprints.lands import LandTable

TABLE = LandTable(version=1, hole_clearance=200_000, annular_ring=350_000)
