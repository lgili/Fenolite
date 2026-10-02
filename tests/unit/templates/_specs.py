# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored test specifications for the template tests (change c0012)."""

from __future__ import annotations

BASE = """
[sheet]
name = "test"
sizes = ["A4", "A3"]
text_size = 1.5
line_width = 0.15
text_line_width = 0.15

[margins]
left = 20
right = 10
top = 10
bottom = 10

[frame]
line_width = 0.7
"""

ZONE_KEYS = "zones = true\nzone_pitch = 50\nzone_band = 5\nzone_line_width = 0.35\nzone_text_size = 3.5\n"
ZONES = BASE.replace("line_width = 0.7\n", "line_width = 0.7\n" + ZONE_KEYS)

TITLE = """
[title_block]
corner = "rb"
columns = [30, 60, 30]
rows = [8, 8]
line_width = 0.35
label_size = 1.8

[[title_block.cell]]
row = 0
col = 0
span = 2
label = "Title"
token = "title"

[[title_block.cell]]
row = 0
col = 2
label = "Sheet"
token = "sheet"
justify = "center"

[[title_block.cell]]
row = 1
col = 0
token = "param:LOT_NO"
justify = "right"
font_size = 2.5
"""
