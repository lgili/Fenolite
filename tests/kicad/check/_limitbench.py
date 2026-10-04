# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An authored bench for KiCad's clearance report limit (``H-K-DRC-LIMIT``, change c0051).

``limit_project`` writes ``two_layer.kicad_pcb`` with ``pairs`` more pairs of ``F.Cu`` tracks, a ``{}``
project and a ``(version 1)`` rules file. The two tracks of a pair are on two nets of their own, 0.25 mm
wide and 0.3 mm apart, so each pair is one ``clearance`` violation (a 0.05 mm gap) and no short. The pairs
are inserted as text, as the check canary is: the net rows after the last net row, the tracks before the
closing parenthesis. Every byte is authored for Fenolite.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from _projects import STEM, TWO_LAYER

from fenolite.backends.kicad.cli import KicadCli
from fenolite.core.ids import FENOLITE_NS

COLUMNS = 40
"""Pairs per row: 4 mm apart in x, rows 1.5 mm apart in y, starting at (40, 40) mm, clear of the board."""
_NET_ROW = re.compile(r'^\t\(net (\d+) "[^"]*"\)\n', flags=re.MULTILINE)


def limit_board(pairs: int) -> str:
    """The text of ``two_layer.kicad_pcb`` with ``pairs`` close track pairs added."""
    base = TWO_LAYER.read_text(encoding="utf-8")
    rows = list(_NET_ROW.finditer(base))
    first = max(int(row.group(1)) for row in rows) + 1
    nets: list[str] = []
    tracks: list[str] = []
    for index in range(pairs):
        x, y = 40 + 4 * (index % COLUMNS), 40 + 1.5 * (index // COLUMNS)
        for side, offset in enumerate((0.0, 0.3)):
            net = first + 2 * index + side
            uid = uuid.uuid5(FENOLITE_NS, f"limit-bench:{index}:{side}")
            nets.append(f'\t(net {net} "LIMIT_{index}_{"AB"[side]}")\n')
            tracks.append(
                f"\t(segment (start {x} {y + offset:.2f}) (end {x + 2} {y + offset:.2f}) (width 0.25)"
                f' (layer "F.Cu") (net {net}) (uuid "{uid}"))\n'
            )
    after = rows[-1].end()
    text = base[:after] + "".join(nets) + base[after:]
    closing = text.rstrip().rfind(")")
    return text[:closing] + "".join(tracks) + text[closing:]


def limit_project(root: Path, pairs: int) -> Path:
    """A project folder under ``root`` holding the bench board with ``pairs`` pairs."""
    root.mkdir(parents=True)
    (root / f"{STEM}.kicad_pcb").write_text(limit_board(pairs), encoding="utf-8")
    (root / f"{STEM}.kicad_pro").write_text("{}\n", encoding="utf-8")
    (root / f"{STEM}.kicad_dru").write_text("(version 1)\n", encoding="utf-8")
    return root


def clearance_count(cli: KicadCli, root: Path) -> int:
    """The ``clearance`` violations of one plain DRC run on the project in ``root``."""
    others = {name: root / name for name in (f"{STEM}.kicad_pro", f"{STEM}.kicad_dru")}
    report = cli.drc(root / f"{STEM}.kicad_pcb", files=others).report
    assert report is not None
    return sum(1 for violation in report.violations if violation.type == "clearance")
