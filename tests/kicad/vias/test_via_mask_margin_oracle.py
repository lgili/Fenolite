# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The mask opening of an untented via against ``kicad-cli pcb export gerbers`` (change c0445; capability
kicad-file-backend, "Board mask margin in a written board"; ``H-K-VIAPROT-MASK``).

The via bench (one untented via) is written with ``Board.mask_margin`` and plotted on ``F.Mask``: the
flash at the via is a circle of its diameter plus twice the board's margin, a negative margin included. A
``solder_mask_expansion`` rule of the rules file opens a pad wider and leaves the via as it was, so a
board's margin is the one value KiCad holds for a via's opening. KiCad's code was neither read nor
transcribed.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from pathlib import Path

import pytest
from _probes import runner
from _viabench import DIAMETER, PROJECT, STEM, bench, position

from fenolite.backends.kicad.pcb import write_board
from fenolite.model.board import ViaProtection

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
OPEN = ViaProtection(tenting_front=False, tenting_back=False)
RULE = (
    '(version 1)\n(rule "m"\n\t(condition "A.Type == \'Via\'")\n'
    "\t(constraint solder_mask_expansion (opt 0.1mm))\n)\n"
)


def _via_flash(margin: int | None, rules: str | None = None) -> float | None:
    """The diameter in mm of the ``F.Mask`` flash at the bench's one via; ``None`` without a flash."""
    design = bench([OPEN], name="mask")
    assert design.board is not None
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, mask_margin=margin))
    text = write_board(design, target=10).text
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / f"{STEM}.kicad_pcb"
        board.write_text(text, encoding="utf-8", newline="\n")
        files = {f"{STEM}.kicad_pro": board.with_suffix(".kicad_pro")}
        files[f"{STEM}.kicad_pro"].write_text(PROJECT, encoding="utf-8")
        if rules is not None:
            files[f"{STEM}.kicad_dru"] = board.with_suffix(".kicad_dru")
            files[f"{STEM}.kicad_dru"].write_text(rules, encoding="utf-8")
        run = runner().export(["pcb", "export", "gerbers", "-l", "F.Mask", "-o", "out/"], board, files=files,
                              out="out")  # fmt: skip
    data = next((d for name, d in run.outputs.items() if "F_Mask" in name), None)
    assert data is not None, run.stderr
    plot = data.decode("utf-8")
    apertures = dict(re.findall(r"%ADD(\d+)C,([0-9.]+)\*%", plot))
    centre = position(0)
    current = None
    for line in plot.splitlines():
        selected = re.fullmatch(r"D(\d+)\*", line)
        if selected and int(selected.group(1)) >= 10:
            current = selected.group(1)
        flash = re.fullmatch(r"X(-?\d+)Y(-?\d+)D03\*", line)
        at = None if flash is None else (int(flash.group(1)), -int(flash.group(2)))
        if at == (centre.x, centre.y) and current is not None:
            return float(apertures[current])
    return None


def test_the_board_margin_opens_an_untented_via() -> None:
    assert _via_flash(None) == DIAMETER / 1e6
    assert _via_flash(50_000) == pytest.approx(DIAMETER / 1e6 + 0.1)
    assert _via_flash(-101_600) == pytest.approx(DIAMETER / 1e6 - 0.2032)


def test_a_mask_rule_leaves_the_via_as_it_was() -> None:
    assert _via_flash(None, RULE) == DIAMETER / 1e6
