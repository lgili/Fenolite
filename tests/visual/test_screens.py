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


@pytest.mark.parametrize("name", NAMES)
def test_deterministic(name: str, pages: dict[str, Path], tmp_path: Path) -> None:
    """H-G-WB-STABLE: independent contexts render the same authored fixture to identical PNG bytes."""
    from hashlib import sha256

    first, second = tmp_path / "first.png", tmp_path / "second.png"
    replies = run([job(name, pages[name], tmp_path, shot=str(path)) for path in (first, second)], tmp_path)
    assert all(reply["errors"] == [] for reply in replies)
    assert sha256(first.read_bytes()).digest() == sha256(second.read_bytes()).digest()
