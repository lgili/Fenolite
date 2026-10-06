# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent two-face copper positions and one outside-view mirror."""

from dataclasses import replace
from xml.etree import ElementTree as ET

from fenolite.backends.kicad import frame
from fenolite.core.coords import Point
from fenolite.placement.preview import placement_preview

from ._constrained_fixture import board, part


def test_copper_on_both_faces_and_asymmetric_bottom_mirrored_once() -> None:
    bottom = part("bottom", 25, 18, side="bottom")
    bottom = replace(bottom, pads=(replace(bottom.pads[0], position=Point(0, -3)),))
    d = board(part("mount", 10, 10, drill=2, locked=True), bottom)
    top = ET.fromstring(placement_preview(d, frame, face="top"))
    back = ET.fromstring(placement_preview(d, frame, face="bottom"))
    front_pads = {e.attrib["data-pad"] for e in top.iter() if "data-pad" in e.attrib}
    back_pads = {e.attrib["data-pad"] for e in back.iter() if "data-pad" in e.attrib}
    assert front_pads == {"p_mount"} and back_pads == {"p_mount", "p_bottom"}
    entry = next(e for e in back.iter() if e.attrib.get("data-pad") == "p_bottom")
    assert entry.attrib["data-centre"] == "25,15"  # backend's stored bottom pad, no extra local mirror
    mirrors = [e for e in back.iter() if "scale(-1 1)" in e.attrib.get("transform", "")]
    assert len(mirrors) == 1 and mirrors[0].attrib["transform"] == "translate(40 0) scale(-1 1)"
    assert any("data-lock" in e.attrib for e in top.iter())
    assert "conservative extent" in placement_preview(d, frame, face="top", envelopes=True)
    assert placement_preview(d, frame, face="bottom") == placement_preview(d, frame, face="bottom")
