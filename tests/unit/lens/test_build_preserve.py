# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The build's normal form (capability layout-lens, "Preservation is the build's normal form"; design-dsl,
MODIFIED "Built project files": "Cache texts come from the layout", "Existing project text is merged";
change c0019)."""

from __future__ import annotations

import pytest
from _buildhelp import (
    blink,
    build,  # noqa: I001
)
from _layout_edit import edit_blink
from _preserve_help import board_text, fresh, prepared

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.dsl import placements, to_model
from fenolite.lens.build import lower_for_schematic
from fenolite.lens.preserve import ExistingProject, match_footprints, prepare
from fenolite.model import canonical


@pytest.mark.parametrize("target", [9, 10])
def test_fresh_build_unchanged(target: int) -> None:
    output = fresh(target)
    text = output.files["blink.kicad_pcb"].decode("utf-8")
    assert output.schematic is not None  # the written board follows the schematic (c0061)
    lowered = lower_for_schematic(output.design, output.schematic)
    assert text == write_board(lowered, target=target).text
    skipped = build(blink(), target, schematic="skip")
    assert skipped.files["blink.kicad_pcb"].decode("utf-8") == write_board(skipped.design, target=target).text
    match = match_footprints(output.design, read_board(text))
    assert {p: m.key for p, m in match.matches.items()} == {"D1": "uuid", "R1": "uuid", "U1": "uuid"}


def test_cache_texts_come_from_the_layout() -> None:
    d = blink()
    ready = prepared(d, board_text(edit=edit_blink))
    output = build(d, 10, prepared=ready, placements_override=ready.placements)
    assert output.layout is not None
    texts = canonical.dump_texts(output.layout)
    assert all(output.files[f".fenolite/{name}"].decode("utf-8") == text for name, text in texts.items())
    assert output.layout.board is not None and len(output.layout.board.tracks) == 2


def test_existing_project_text_is_merged() -> None:
    d = blink()
    data = _json.loads(fresh().files["blink.kicad_pro"].decode("utf-8"))
    data["x_user_key"] = {"k": _json.JsonNumber("1.000")}
    existing = ExistingProject(project=_json.dumps(data))
    ready = prepare(to_model(d), placements(d), existing, name="blink")
    output = build(d, 10, prepared=ready)
    written = _json.loads(output.files["blink.kicad_pro"].decode("utf-8"))
    assert written["x_user_key"] == {"k": _json.JsonNumber("1.000")}
