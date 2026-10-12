# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""SVG uses symbol geometry and escaped authored text without external resources."""

from dataclasses import replace
from xml.etree import ElementTree

from fenolite.schematic.preview import svg
from tests.unit.schematic.test_composition_report import plan


def test_svg_is_self_contained_and_has_real_geometry():
    composed = plan()
    placement = composed.placements[0]
    composed = replace(
        composed, placements=(replace(placement, unit=replace(placement.unit, value='<script>&"')),)
    )
    data = svg(composed)
    root = ElementTree.fromstring(data)
    assert root.tag.endswith("svg")
    assert b"&lt;script&gt;&amp;" in data
    assert b'<g id="U1#1">' in data and b"<rect" in data
    assert b"href=" not in data and b"<script>" not in data and b"generated" in data.lower()
