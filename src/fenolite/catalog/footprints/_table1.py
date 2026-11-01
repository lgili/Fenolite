# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The land constants ``lands/1`` (change c0260), written by ``tools/calibrate_lands.py``.

Do not edit. The goals and ball ratios are back-solved from the cited manufacturer patterns of
``tests/data/packages/calibration`` (lower median per class of at least three records,
rounded to 10 µm); ``pad_gap``, ``grid``, ``courtyard``, ``hole_clearance``, ``annular_ring``,
``paste_cell`` and ``paste_window`` are Fenolite's own choices
(``docs/formats/library/lands.md``). Every value is ``INFERRED``. No value is taken from
IPC-7351 tables or its calculator."""

from __future__ import annotations

from fractions import Fraction

from fenolite.catalog.footprints.lands import Goals, LandTable

TABLE = LandTable(
    version=1,
    goals={
        "chip": Goals(toe=300_000, heel=-100_000, side=30_000),
        "molded": Goals(toe=100_000, heel=-10_000, side=80_000),
        "gullwing": Goals(toe=380_000, heel=-190_000, side=50_000),
        "gullwing-fine": Goals(toe=350_000, heel=200_000, side=20_000),
        "nolead": Goals(toe=150_000, heel=-150_000, side=-30_000),
    },
    pad_gap=200_000,
    grid=10_000,
    courtyard=500_000,
    hole_clearance=200_000,
    annular_ring=350_000,
    paste_cell=2_000_000,
    ball_ratio={},
    paste_window=Fraction(4, 5),
    calibration={
        "chip": (
            "Chip0402_Vishay_CRCW",
            "Chip0603_Vishay_CRCW",
            "Chip0805_Vishay_CRCW",
            "Chip1206_Vishay_CRCW",
            "Chip1210_Vishay_CRCW",
            "Chip2010_Vishay_CRCW",
            "Chip2512_Vishay_CRCW",
        ),
        "gullwing": (
            "SC70_5_TI_DCK0005A",
            "SOIC14_TI_D0014A",
            "SOIC8_TI_D0008A",
            "SOIC8_onsemi_751_07",
            "SOT23_5_TI_DBV0005A",
            "TSSOP14_TI_PW0014A",
            "TSSOP8_TI_PW0008A",
            "VSSOP8_TI_DGK0008A",
        ),
        "gullwing-fine": (
            "LQFP48_TI_PT0048A",
            "LQFP80_TI_PN0080A",
            "SOT14_TI_DYY0014A",
            "VSSOP10_TI_DGS0010A",
        ),
        "molded": (
            "SOD123F_Diodes",
            "SOD123_Diodes",
            "SOD323_Diodes",
            "SOD523_Diodes",
        ),
        "nolead": (
            "QFN16_TI_RGT0016C",
            "QFN64_TI_RGC0064B",
            "SON6_TI_DRV0006A",
            "SON6_TI_DSF0006A",
        ),
    },
)
