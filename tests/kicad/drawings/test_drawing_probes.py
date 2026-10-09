# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing probes on the running ``kicad-cli`` (capability kicad-oracle, "Drawing facts are probed";
change c0117). Each test settles one hypothesis: a probe that records another outcome than its
hypothesis states fails here, and the part it settles stops (``docs/hypotheses.md``)."""

from __future__ import annotations

import _drawbench
import _probes
import pytest

from fenolite.exports.drawing_layout import AUTO_PAPERS

pytestmark = pytest.mark.needs_kicad


def _outcomes(*names: str) -> dict[str, str]:
    found = {name: _probes.run(name) for name in names}
    print(f"kicad-cli {_probes.version()}: {found}")
    return found


def test_items_are_drawn() -> None:
    """``H-K-DRAW-ITEMS``."""
    names = (
        "draw-table",
        "draw-textbox",
        "draw-dimension",
        "draw-vars",
        "draw-defvar-board",
        "draw-defvar-sheet",
    )
    assert _outcomes(*names) == dict.fromkeys(names, "present")


def test_text_bounds() -> None:
    """``H-K-DRAW-TEXT``."""
    assert _outcomes("draw-wrap-overflow", "draw-pitch", "draw-glyph-bound") == {
        "draw-wrap-overflow": "present",
        "draw-pitch": "equal",
        "draw-glyph-bound": "equal",
    }


def test_page_is_the_board_frame() -> None:
    """``H-K-DRAW-PAGE``: the three plot facts, and the ``--scale`` rows of the help pages as recorded
    (10.0 has the option for both exports, 9.0 for neither)."""
    names = ("draw-page-position", "draw-mirror", "draw-no-holes")
    assert _outcomes(*names) == dict.fromkeys(names, "equal")
    scale = "present" if _probes.major() >= 10 else "absent"
    helps = ("help-pcb-export-pdf-scale", "help-pcb-export-svg-scale")
    assert _outcomes(*helps) == dict.fromkeys(helps, scale)


@pytest.mark.parametrize("paper", list(AUTO_PAPERS))
def test_default_sheet_boxes(paper: str) -> None:
    """``H-K-DRAW-SHEET``."""
    name = f"draw-default-sheet-{paper}"
    assert _outcomes(name) == {name: "equal"}


def test_drill_maps_and_counts() -> None:
    """``H-K-DRAW-DRILL``."""
    files = sorted(name for name in _drawbench.drill_run().outputs if name.startswith("drawings/"))
    print(f"kicad-cli {_probes.version()}: drill files {files}")
    assert _outcomes("draw-drill-files", "draw-drill-counts") == {
        "draw-drill-files": "equal",
        "draw-drill-counts": "equal",
    }


def test_assembly_options() -> None:
    """``H-K-DRAW-ASSEMBLY``."""
    names = ("draw-dnp-crossout", "draw-dnp-hide", "draw-values", "draw-pads")
    assert _outcomes(*names) == dict.fromkeys(names, "present")
    assert _outcomes("draw-bottom-designator") == {"draw-bottom-designator": "equal"}


def test_repeat_of_two_exports() -> None:
    """``H-K-DRAW-REPEAT``."""
    names = ("draw-repeat-pdf", "draw-repeat-report")
    assert _outcomes(*names) == dict.fromkeys(names, "equal")


def test_layer_rows_are_added() -> None:
    """``H-K-DRAW-LAYER``."""
    assert _outcomes("draw-layer-added") == {"draw-layer-added": "present"}


def test_every_probe_is_registered() -> None:
    assert set(_drawbench.draw_probes()) <= set(_probes.PROBES)
    assert len(_drawbench.draw_probes()) == 29
