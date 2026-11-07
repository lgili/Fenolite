# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact generator constants, shared by selection and authored expectations.

S-0941 (UM10204) supplies the I2C limits. Existing c0254 facts are held once here;
no standards table is copied into a block. Irrational constants have rational enclosures.
"""

from collections.abc import Mapping
from fractions import Fraction
from types import MappingProxyType

PI = (Fraction("3.14159265358"), Fraction("3.14159265359"))
LN_7_3 = (Fraction("0.847297860387"), Fraction("0.847297860388"))
I2C_MODES: Mapping[str, tuple[Fraction, Fraction, Fraction]] = MappingProxyType(
    {
        "standard": (Fraction("0.4"), Fraction(3, 1000), Fraction(1000, 10**9)),
        "fast": (Fraction("0.4"), Fraction(3, 1000), Fraction(300, 10**9)),
        "fast-plus": (Fraction("0.4"), Fraction(20, 1000), Fraction(120, 10**9)),
    }
)


def i2c_limits(mode: str, capacitance_max: Fraction) -> tuple[Fraction, Fraction, Fraction]:
    """VOL, sink current and conservative maximum pull-up resistance, in V, A, ohms.

    The upper enclosure of ln(7/3) narrows the permitted rise-time window.
    The caller checks that the supply satisfies UM10204's VDD > 2 V premise.
    """
    if mode not in I2C_MODES:
        raise ValueError(f"unknown I2C mode {mode!r}")
    if capacitance_max <= 0:
        raise ValueError("bus capacitance must be positive")
    vol, iol, rise = I2C_MODES[mode]
    return vol, iol, rise / (LN_7_3[1] * capacitance_max)


__all__ = ["I2C_MODES", "LN_7_3", "PI", "i2c_limits"]
