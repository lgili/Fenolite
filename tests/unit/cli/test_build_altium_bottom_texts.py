# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A part placed on the bottom by a design script comes out of ``fenolite build --target altium`` with its
designator and comment on Bottom Overlay, mirrored (change c0430). The routed blink places ``D1`` with
``side="bottom"`` and ``R1`` on the top.

The written text records are Fenolite's 137-byte form, which holds no long layer id: Altium Designer takes
the layer of such a text from its layer byte and saves it with the long id of that layer (S-1893: Altium's
save of a routed blink written this way holds ``D1``'s texts on Bottom Overlay with ``0x01030007``)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _routed import NAME, Routed

import fenolite.cli.main as cli_main
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TextRecord

TOP_OVERLAY, BOTTOM_OVERLAY = 33, 34


CASES = [("D1", "BOTTOM", BOTTOM_OVERLAY, True), ("R1", "TOP", TOP_OVERLAY, False)]


@pytest.mark.parametrize(("ref", "side", "layer", "mirrored"), CASES)
def test_script_part_on_the_bottom_has_its_texts_on_bottom_overlay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ref: str, side: str, layer: int, mirrored: bool
) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    args = [
        "build",
        str(routed.script),
        "--out",
        str(routed.out),
        "--target",
        "altium",
        "--confirm",
        "--json",
    ]
    assert cli_main.main(args) == 0, json.loads(stdout.getvalue() or "{}").get("issues")
    doc = read_pcbdoc((routed.out / f"{NAME}.PcbDoc").read_bytes())
    index = next(i for i, c in enumerate(doc.components) if c.source_designator == ref)
    assert doc.components[index].layer == side
    texts = [
        t
        for t in doc.texts
        if isinstance(t, TextRecord) and t.prefix.component == index and (t.is_designator or t.is_comment)
    ]
    assert sorted((t.is_designator, t.is_comment) for t in texts) == [(False, True), (True, False)]
    assert {(t.prefix.layer, t.mirrored) for t in texts} == {(layer, mirrored)}
    assert {rec.long_layer_offset(t.raw) for t in texts} == {None}  # the written form holds no long id
