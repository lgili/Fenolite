# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Screenshot references of the viewer page (capability viewer-visual-tests, scenario "A changed colour
fails"; change c0191): one authored fixture per scene kind, drawn in Chromium and compared with the committed
reference. After an intended change of the drawing: `uv run python tools/update_view_refs.py`."""

from __future__ import annotations

from pathlib import Path

import pytest
from _visual import MAX_RATIO, NAMES, job, run

pytestmark = pytest.mark.needs_browser


@pytest.mark.parametrize("name", NAMES)
def test_screen(name: str, pages: dict[str, Path], tmp_path: Path) -> None:
    (reply,) = run([job(name, pages[name], tmp_path)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    assert reply["ok"] is not None, f"no reference for {name}: run tools/update_view_refs.py"
    assert reply["ok"], (
        f"{name}: {reply.get('differing')} pixels differ ({reply.get('ratio', 0):.4%} > {MAX_RATIO:.1%}); "
        f"difference image {reply.get('diff')}, screenshot {tmp_path / (name + '.png')}"
    )


def test_a_changed_colour_fails(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "A changed colour fails": the Altium sheet with its sheet colour changed in the page."""
    script = 'S.sheet.color = "#dde6ff"; draw();'
    (reply,) = run([job("altium_sheet", pages["altium_sheet"], tmp_path, script=script)], tmp_path)
    assert reply["ok"] is False and reply["ratio"] > MAX_RATIO
    assert Path(reply["diff"]).is_file()  # the difference image


def test_the_light_shell_has_its_own_reference(pages: dict[str, Path], tmp_path: Path) -> None:
    """Scenario "The light shell has its own reference" (c0243): a toolbar colour token changed in the page
    fails the light reference."""
    script = 'document.documentElement.style.setProperty("--surface-1", "#f0d0d0");'
    (reply,) = run([job("kicad_board_light", pages["kicad_board_light"], tmp_path, script=script)], tmp_path)
    assert reply["errors"] == [], reply["errors"]
    assert reply["ok"] is False and reply["ratio"] > MAX_RATIO
    assert Path(reply["diff"]).is_file()
