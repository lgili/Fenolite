# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite silk --clip`` judged by the running ``kicad-cli`` (change c0226; capability
silkscreen-layout, "Clipped strokes checked"; hypotheses ``H-K-SILK-MASK`` and ``H-K-SILK-CLIP``;
``docs/formats/kicad/drc.md``, "Silkscreen over pads").

The ``mask`` cases probe what KiCad's ``silk_over_copper`` measures, on one pad of 1 mm with one silkscreen
line of 0.1 mm stroke: whether a line at a given distance is reported, with the mask expansion of the pad or
of the board, the board's ``min_silk_clearance``, a ``silk_clearance`` rule, and a pad without a mask
opening. The ``clip`` cases run the command on the bench ``clipped()`` of ``tests/_silkbench.py``."""

from __future__ import annotations

import io
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner
from _silkbench import SilkBoard, clipped, probe

from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.pro import synthesize_project
from fenolite.cli import main as cli_main
from fenolite.core.coords import Point
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
MM = 1_000_000
UM = 1_000
RULE = '(version 1)\n(rule "silk" (constraint silk_clearance (min 0.1mm)))\n'

# (case, line y in µm from the pad's centre, pad margin, board margin, min_silk_clearance, rule, mask,
#  silk_over_copper reported). The copper edge is at 500 µm and the line's ink 50 µm either side of it.
MASK_CASES = [
    ("over", 300, None, None, None, False, True, True),
    ("touch", 550, None, None, None, False, True, False),
    ("over-1um", 549, None, None, None, False, True, True),
    ("pad-margin", 600, 300 * UM, None, None, False, True, False),
    ("board-margin", 600, None, "0.3", None, False, True, False),
    ("min-silk", 600, None, None, 0.3, False, True, False),
    ("rule", 600, None, None, None, True, True, True),
    ("rule-clear", 700, None, None, None, True, True, False),
    ("bare", 300, None, None, None, False, False, False),
]


def _write(
    folder: Path,
    name: str,
    design: Design,
    *,
    board_margin: str | None = None,
    min_silk: float | None = None,
    rule: bool = False,
) -> Path:
    board = folder / f"{name}.kicad_pcb"
    text = write_board(design, target=major()).text
    if board_margin is not None:
        text, count = re.subn(
            r"\(pad_to_mask_clearance [^)]*\)", f"(pad_to_mask_clearance {board_margin})", text
        )
        assert count == 1
    board.write_text(text, encoding="utf-8", newline="\n")
    project = synthesize_project(design, target=major(), board_name=name)
    if min_silk is not None:
        data = json.loads(project)
        data["board"]["design_settings"]["rules"]["min_silk_clearance"] = min_silk
        project = json.dumps(data, indent=2) + "\n"
    board.with_suffix(".kicad_pro").write_text(project, encoding="utf-8", newline="\n")
    if rule:
        board.with_suffix(".kicad_dru").write_text(RULE, encoding="utf-8", newline="\n")
    return board


def _drc(board: Path) -> Counter[str]:
    files = {
        path.name: path
        for path in (board.with_suffix(".kicad_pro"), board.with_suffix(".kicad_dru"))
        if path.is_file()
    }
    report = runner().drc(board, files=files)
    assert report.report is not None
    found = (*report.report.violations, *report.report.unconnected_items)
    return Counter(item.type for item in found if not item.excluded)


@pytest.mark.kicad_min_major(10)  # 9.0.9 measures to the mask opening (docs/formats/kicad/drc.md, c0226)
@pytest.mark.parametrize(
    ("case", "line_y", "margin", "board_margin", "min_silk", "rule", "mask", "reported"),
    MASK_CASES,
    ids=[case[0] for case in MASK_CASES],
)
def test_mask_probe(
    tmp_path: Path,
    case: str,
    line_y: int,
    margin: int | None,
    board_margin: str | None,
    min_silk: float | None,
    rule: bool,
    mask: bool,
    reported: bool,
) -> None:
    bench = SilkBoard(width=20 * MM, height=20 * MM)
    bench.place(
        "U1",
        Point(10 * MM, 10 * MM),
        defn=probe(line_y * UM, mask=mask, margin=margin),
        ref_at=Point(10 * MM, 15 * MM),
    )
    board = _write(tmp_path, case, bench.build(), board_margin=board_margin, min_silk=min_silk, rule=rule)
    found = _drc(board)
    assert (found["silk_over_copper"] > 0) is reported, (case, found)
    assert not {"silk_overlap", "silk_edge_clearance"} & set(found), found


def _silk(
    monkeypatch: pytest.MonkeyPatch, folder: Path, board: Path, *args: str
) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(folder)
    monkeypatch.setenv("FENOLITE_CACHE_DIR", str(folder / "cache"))
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    cli = str(runner().path)
    code = cli_main.main(["silk", board.name, "--kicad-cli", cli, *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


@pytest.mark.parametrize("rule", [False, True], ids=["no-rule", "rule"])
def test_clip_passes_drc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, rule: bool) -> None:
    board = _write(tmp_path, "clipped", clipped(), rule=rule)
    before = _drc(board)
    assert before["silk_over_copper"] > 0  # the control
    code, env = _silk(monkeypatch, tmp_path, board, "--clip", "--drc", "--confirm")
    assert code == 0, env
    result = env["result"]
    assert result["changed"] is True and result["clip"]["margin"] == (100 * UM if rule else 0)
    assert result["drc"]["new"] == [] and env["evidence"]["level"] == "KICAD-VERIFIED"
    after = _drc(board)
    assert after["silk_over_copper"] == 0, after
    for kind in ("silk_overlap", "silk_edge_clearance"):
        assert after[kind] <= before[kind], (kind, before, after)
