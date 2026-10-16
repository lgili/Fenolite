# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part Q of the maintainer's check (``docs/evidence/altium-pcb.md``, "Part Q: panels and the
Embedded Board Array"; change c0173, task 2.3; ``H-A-PANEL-RECORD``, ``H-A-PANEL-LAYERKIND``).

``phase_a(folder)`` writes phase A of the kit into ``folder``:

- ``board/``: ``tests/data/panels/board.py`` built with ``--target altium`` (the project, its PCB document,
  library, schematic and output job), the board the maintainer makes panels of in cases Q1 to Q5;
- ``README.md``: the steps Q1 to Q6 in Portuguese (``tests/data/panels/kit/README-phase-a.md``), and
  ``PART-Q.md``: Part Q of the evidence page, in English;
- ``SHA256SUMS``: the SHA-256 of every file.

With ``FENOLITE_ALTIUM_PART_Q=<folder outside the repository>`` the kit is written there:
``FENOLITE_ALTIUM_PART_Q=~/fenolite-altium-checks/session-6/Q-panels uv run pytest
tests/unit/backends/altium/test_part_q.py -k phase_a``. Without it the kit is written under the test's own
folder. No file that Altium wrote is in the repository.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from _panels import PANELS, build_board

from fenolite.backends.altium.read.pcb import read_pcbdoc

ROOT = Path(__file__).resolve().parents[4]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_Q")
README = PANELS / "kit" / "README-phase-a.md"


def _part_q() -> str:
    page = (ROOT / "docs" / "evidence" / "altium-pcb.md").read_text(encoding="utf-8")
    start = page.index("## Part Q: panels and the Embedded Board Array")
    end = page.index("\n## ", start + 3)
    return page[start:end].rstrip() + "\n"


def sha256_sums(folder: Path) -> dict[str, str]:
    """The SHA-256 of every file under ``folder`` but ``SHA256SUMS``, by its relative path."""
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    }


def phase_a(folder: Path) -> dict[str, str]:
    """Write phase A of the kit into ``folder``; the SHA-256 of every file by its relative path."""
    board = folder / "board"
    if board.exists():
        for path in sorted(board.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
    build_board(board, "altium")
    cache = board / ".fenolite"
    if cache.exists():  # the build's cache is Fenolite's, not part of the kit
        for path in sorted(cache.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        cache.rmdir()
    (folder / "README.md").write_text(README.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "PART-Q.md").write_text(_part_q(), encoding="utf-8")
    sums = sha256_sums(folder)
    (folder / "SHA256SUMS").write_text("".join(f"{d}  {n}\n" for n, d in sums.items()), encoding="utf-8")
    return sums


def test_phase_a_kit(tmp_path: Path) -> None:
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "Q-panels"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    folder.mkdir(parents=True, exist_ok=True)
    sums = phase_a(folder)
    assert {"board/board.PrjPcb", "board/board.PcbDoc", "README.md", "PART-Q.md"} <= set(sums)
    assert not any(name.startswith("board/.fenolite") for name in sums)
    lines = (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert lines == [f"{d}  {n}" for n, d in sums.items()]
    doc = read_pcbdoc((folder / "board" / "board.PcbDoc").read_bytes())
    assert not [i for i in doc.issues if i.severity == "error"]
    readme = (folder / "README.md").read_text(encoding="utf-8")
    for case in range(1, 7):
        assert f"**Q{case}**" in readme, case
    assert "**Q7**" not in readme, "phase A holds Q1 to Q6 only"
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".PrjPcb", ".OutJob", ".md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            assert not re.search(r"(?:[A-Za-z]:\\|/home/|/tmp/|/Users/)", text), path.name


def test_phase_a_steps_match_the_evidence_page() -> None:
    """The Portuguese steps name the same variants, values and menus as the English cases."""
    readme = " ".join(README.read_text(encoding="utf-8").split())
    part = " ".join(_part_q().split())
    for word in (
        "panel-a.PcbDoc", "panel-cols4", "panel-rows3", "panel-spacing", "panel-margin", "panel-rot90",
        "panel-mirror", "panel-link", "panel-move", "panel-layers", "panel-two", "Column Spacing 42",
        "Row Spacing 32", "Synchronize Manually Later", "V Cut", "Route Tool Path", "X 100, Y 5",
        "Gerber Files", "NC Drill Files", "History", "Project Outputs", "fenolite kit verify",
    ):  # fmt: skip
        assert word in readme, word
        assert word in part, word
