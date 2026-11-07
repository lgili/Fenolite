# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small authored circuits used through ``design.use``; see ``docs/blocks/index.md``."""

from fenolite.blocks.divider import voltage_divider
from fenolite.blocks.i2c import i2c_pullups
from fenolite.blocks.led import led_indicator
from fenolite.blocks.protect import protected_input
from fenolite.blocks.rc import rc_lowpass

__all__ = ["i2c_pullups", "led_indicator", "protected_input", "rc_lowpass", "voltage_divider"]
