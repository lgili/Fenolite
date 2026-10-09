# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benches of the KiCad downgrade (change c0162; ``H-K-DOWN-ROWS``; capability kicad-version-gating,
"Downgrade resolver", scenario "Each row proved on 9.0.9").

A bench holds one construct of KiCad 10 in a minimal file: the token fuzz's example of the row
(``tests/data/kicad/tokens/examples.toml``), inserted into the fuzz skeleton of its kind at the header of
10.0, or a variant of it named here. ``tests/data/kicad/downgrade/`` holds each bench as ``kicad-cli``
10.0.6 saved it (``pcb upgrade --force`` or ``sch upgrade --force``; ``sym upgrade --force`` for a symbol
library), written by a 10.0.6 run with ``FENOLITE_GOLDEN_WRITE=1``. Fenolite downgrades the saved file for
KiCad 9; a 9.0.9 run loads it and runs its DRC (ERC for a schematic), which must report the violation types
10.0.6 reports on the source (``SOURCE_TYPES``, recorded by a 10.0.6 run); a 10.0.6 run re-saves the
downgraded file, which must give the source again: the model at level 5 for a board, the tree for a
schematic or a symbol library. The probe ``down-row-<bench>`` records ``equal`` when every check of the
running major holds, ``different`` when one does not, ``reject`` when the file does not load.
"""

from __future__ import annotations

import re
import tempfile
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import _fuzzmod

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "kicad" / "downgrade"
SKELETONS = ROOT / "tests" / "data" / "kicad" / "tokens"
WRITE_VARIABLE = "FENOLITE_GOLDEN_WRITE"
SUFFIX: Mapping[FileKind, str] = {
    FileKind.BOARD: ".kicad_pcb",
    FileKind.SCHEMATIC: ".kicad_sch",
    FileKind.SYMBOL_LIB: ".kicad_sym",
}
SKELETON: Mapping[FileKind, str] = {
    FileKind.BOARD: "skeleton.kicad_pcb",
    FileKind.SCHEMATIC: "skeleton.kicad_sch",
    FileKind.SYMBOL_LIB: "skeleton.kicad_sym",
}


def _fuzz():  # noqa: ANN202  (a module loaded from tools/)
    return _fuzzmod.load()


def header(kind: FileKind, major: int) -> int:
    return FORMAT_VERSIONS[kind][major]


def with_header(text: str, version: int) -> str:
    """``text`` with its root's ``(version N)`` set to ``version``."""
    return re.sub(r"\(version \d+\)", f"(version {version})", text, count=1)


def skeleton(kind: FileKind, major: int) -> str:
    """The fuzz skeleton of ``kind`` at the header of ``major``."""
    return with_header((SKELETONS / SKELETON[kind]).read_text(encoding="utf-8"), header(kind, major))


def appended(text: str, fragment: str) -> str:
    """``text`` with ``fragment`` appended as the last child of its root."""
    body = text.rstrip()
    assert body.endswith(")")
    return body[:-1].rstrip() + "\n\t" + fragment + "\n)\n"


# --- task 1.2: the absent defaults of via protection and the form of a buried via ----------------------


def runner_major(runner: KicadCli) -> int:
    return runner.major()


def upgraded_board(runner: KicadCli, text: str) -> str:
    """``text`` re-saved by ``pcb upgrade --force`` (10.0 only), whitespace folded to one space."""
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        board = Path(tmp) / "bench.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        saved = runner.upgrade_board(board).decode("utf-8")
    return re.sub(r"\s+", " ", saved)


def drc_types(runner: KicadCli, text: str, name: str = "bench") -> tuple[str, ...] | None:
    """The DRC violation types with their counts, sorted; ``None`` when the board does not load."""
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        board = Path(tmp) / f"{name}.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        run = runner.drc(board)
    if run.report is None:
        return None
    found = (*run.report.violations, *run.report.unconnected_items)
    return tuple(f"{k}={n}" for k, n in sorted(Counter(v.type for v in found).items()))


def loads(runner: KicadCli, text: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        board = Path(tmp) / "bench.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", board.name]
        run = runner.run(args, files={board.name: board})
    return run.returncode == 0 and "out.svg" in run.outputs


PROTECTION_CHILDREN = ("covering", "plugging", "capping", "filling")
SETUP_ABSENT_10 = (
    "(covering (front no) (back no) ) (plugging (front no) (back no) ) (capping no) (filling no)"
)
"""What 10.0.6 writes in ``setup`` for a board whose ``setup`` holds none of the four (measured on
2026-10-09): the absent default of the board is ``no``."""
VIA_ABSENT_9 = "(capping no) (covering (front no) (back no) ) (plugging (front no) (back no) ) (filling no)"
"""What 10.0.6 writes for a via of a board of format 9 (which cannot hold the four): ``no``, so what 9.0
does without them is what 10.0 does with ``no``."""
BURIED_VIA_10 = (
    '(via buried (at 22 22) (size 0.6) (drill 0.3) (layers "In1.Cu" "In2.Cu") (net 1) '
    '(uuid "6f1d2c3e-0000-4000-8000-0000000000bb"))'
)
BURIED_VIA_9 = BURIED_VIA_10.replace("(via buried", "(via blind")
BURIED_TYPES = ("lib_footprint_issues=1", "track_dangling=1", "unconnected_items=3", "via_dangling=2")
"""The DRC violation types of the buried-via bench on 10.0.6 and of its 9 form on 9.0.9 (2026-10-09)."""


def protection_defaults(runner: KicadCli) -> str:
    """``equal`` when the running major gives the recorded absent defaults (task 1.2): on 10.0.6 a board of
    format 10 without the four children in ``setup`` or on a via is re-saved with ``SETUP_ABSENT_10`` and
    a via without them, and a board of format 9 with ``VIA_ABSENT_9`` on each via; on 9.0.9 the board of
    format 9 loads and one with ``(capping no)`` on a via does not (9.0 has no such child)."""
    nine = skeleton(FileKind.BOARD, 9)
    if runner.major() == 9:
        via = '(drill 0.3)\n\t\t(layers "F.Cu" "B.Cu")'
        capped = nine.replace(via, via + "\n\t\t(capping no)")
        assert capped != nine
        return "equal" if loads(runner, nine) and not loads(runner, capped) else "different"
    ten = upgraded_board(runner, skeleton(FileKind.BOARD, 10))
    from_nine = upgraded_board(runner, nine)
    via_ten = ten[ten.find("(via ") :].split("(zone", 1)[0]
    via_nine = from_nine[from_nine.find("(via ") :].split("(zone", 1)[0]
    ok = (
        SETUP_ABSENT_10 in ten
        and not any(f"({child}" in via_ten for child in PROTECTION_CHILDREN)
        and VIA_ABSENT_9 in via_nine
    )
    return "equal" if ok else "different"


def buried_form(runner: KicadCli) -> str:
    """``equal`` when 9's form of a buried via holds on the running major (task 1.2): on 10.0.6 the bench
    with a buried via gives ``BURIED_TYPES`` and the 9 form (``blind`` with the same span) is read back as
    a blind via of that span; on 9.0.9 the 9 form loads and gives ``BURIED_TYPES``."""
    if runner.major() == 9:
        found = drc_types(runner, appended(skeleton(FileKind.BOARD, 9), BURIED_VIA_9))
        return "equal" if found == BURIED_TYPES else "different"
    source = appended(skeleton(FileKind.BOARD, 10), BURIED_VIA_10)
    back = upgraded_board(runner, appended(skeleton(FileKind.BOARD, 9), BURIED_VIA_9))
    same_span = '(via blind (at 22 22) (size 0.6) (drill 0.3) (layers "In1.Cu" "In2.Cu")' in back
    return "equal" if drc_types(runner, source) == BURIED_TYPES and same_span else "different"


__all__ = ["DATA", "buried_form", "protection_defaults"]
