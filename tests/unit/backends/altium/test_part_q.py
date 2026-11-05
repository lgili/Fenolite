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

``phase_b(folder)`` writes phase B (task 7.3) beside it, from the same ``board/``:

- ``written/``: ``panel.PcbDoc`` and ``panel.PrjPcb``, the panel's own items and one Embedded Board Array of
  ``../board/board.PcbDoc`` (``panel.altium.embedded_files``), the gate ``pcbdoc.EMBEDDED_ARRAYS`` forced on
  for the kit only: no release and no command writes it;
- ``flat/``: the flattened panel of the same script (``panel.altium_panel``);
- ``expected.md``: the array's properties and the cases Q7 to Q12, and ``SHA256SUMS`` again.

With ``FENOLITE_ALTIUM_PART_Q=<folder outside the repository>`` the kit is written there:
``FENOLITE_ALTIUM_PART_Q=~/fenolite-altium-checks/session-6/Q-panels uv run pytest
tests/unit/backends/altium/test_part_q.py -k phase_a`` (``-k phase_b`` for phase B). Without it the kit
is written under the test's own folder. No file that Altium wrote is in the repository.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import pytest
from _panels import PANELS, build_board, committed_board

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprops import PropertyRecord, parse_blocks, parse_mil
from fenolite.dsl import Panel, mm, to_model
from fenolite.panel.altium import embedded_files
from fenolite.panel.build import altium_panel, read_source
from fenolite.panel.layout import PanelLayout, layout

ROOT = Path(__file__).resolve().parents[4]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_Q")
Q12 = os.environ.get("FENOLITE_ALTIUM_Q12")
DOCUMENT = "../board/board.PcbDoc"
"""The referenced document, relative to ``written/panel.PcbDoc``."""
MM = 1_000_000
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


def kit_panel() -> Panel:
    """The panel of phase B: 2 × 2 copies of ``board.PcbDoc`` with 2 mm tabbed gaps (spacing 42 and 32 mm,
    as Q1), scored top and bottom rails of 5 mm, three fiducials and four tooling holes, so that Q9 finds
    mouse-bite and tooling holes and a ``V-Cut`` layer."""
    panel = Panel("panel", board="board.PcbDoc")
    panel.grid(2, 2, gap=mm(2))
    panel.rails(top=mm(5), bottom=mm(5))
    panel.separate("tabs", between="columns")
    panel.separate("tabs", between="rows")
    panel.separate("vscore", between="rails")
    panel.fiducials()
    panel.tooling_holes()
    return panel


def _q_cases(first: int, last: int) -> str:
    lines: list[str] = []
    keep = False
    for line in _part_q().splitlines():
        start = re.match(r"(\d+)\. \*\*Q(\d+)\*\*", line)
        if start:
            keep = first <= int(start.group(2)) <= last
        elif line and not line.startswith(" "):
            keep = False
        if keep:
            lines.append(line)
    return "\n".join(lines) + "\n"


def expected_text(laid: PanelLayout) -> str:
    """``expected.md``: what Q7 should show of the array, in the units of Altium's Properties panel."""
    left = min(copy.rect.x0 for copy in laid.copies)
    low = max(copy.rect.y1 for copy in laid.copies)
    holes = sum(len(tab.holes) for tab in laid.tabs)
    return (
        "# Part Q, phase B: expected (change c0173, task 7.3)\n\n"
        "Written by Fenolite with the gate `pcbdoc.EMBEDDED_ARRAYS` forced on for this kit only.\n\n"
        "## `written/panel.PcbDoc`\n\n"
        "| property | expected |\n|---|---|\n"
        f"| arrays | 1 |\n| PCB Document | `{DOCUMENT}` (relative to the panel) |\n"
        f"| Location X, Y | {left / MM:g} mm, {(laid.size.h - low) / MM:g} mm from the document origin |\n"
        "| Rotation | 0 |\n| Column Count, Row Count | 2, 2 |\n"
        "| Column Spacing, Row Spacing | 42 mm, 32 mm (2 mm gaps; margins 2 mm) |\n"
        "| Mirrored | off |\n| Link Location to Embedded Board Origin | off |\n"
        f"| panel | {laid.size.w / MM:g} × {laid.size.h / MM:g} mm, its rectangle the board shape |\n"
        "| Mechanical 1 | named `Route Tool Path`, no layer type (Q3 was not measured) |\n"
        "| Mechanical 2 | named `V-Cut`, no layer type: the two rail score lines |\n"
        f"| free non-plated holes | {holes} mouse-bite holes and {len(laid.tooling_holes)} tooling holes |\n"
        f"| fiducials | {len(laid.fiducials)} free copper pads on the rails |\n\n"
        "The copies are not in the document: Altium draws them from `board/board.PcbDoc`.\n\n"
        "## `flat/panel.PcbDoc`\n\nThe flattened panel of the same script: every copy's items in the "
        "document, the same holes, fiducials and layers (Q11). It is made of the KiCad build of the same "
        "`board.py`, since the board read back from `board.PcbDoc` states a thickness of 0.39116 mm, which "
        "the V-score check refuses.\n\n"
        "## Cases\n\n" + _q_cases(7, 12)
    )


def _clear(folder: Path) -> None:
    if folder.exists():
        for path in sorted(folder.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
    folder.mkdir(parents=True)


def phase_b(folder: Path) -> dict[str, str]:
    """Write phase B of the kit into ``folder`` (phase A first when ``board/`` is missing); the SHA-256 of
    every file by its relative path."""
    board = folder / "board" / "board.PcbDoc"
    if not board.is_file():
        phase_a(folder)
    model = to_model(kit_panel())
    design, _ = read_source(board)
    laid = layout(model, design)
    files, issues = embedded_files(model, laid, design, DOCUMENT)  # the gate, forced on for the kit only
    assert files and not [i for i in issues if i.severity == "error"], issues
    # the flattened panel is made of the committed KiCad build of the same board.py: the board imported from
    # board.PcbDoc reads 0.39116 mm thick, which the V-score check refuses (panel.vscore-thickness)
    flat = altium_panel(model, committed_board(10))
    assert not flat.refused and flat.form == "flat", flat.issues
    for name, written in (("written", files), ("flat", flat.files)):
        _clear(folder / name)
        for file, data in written.items():
            (folder / name / file).write_bytes(data)
    (folder / "expected.md").write_text(expected_text(laid), encoding="utf-8")
    sums = sha256_sums(folder)
    (folder / "SHA256SUMS").write_text("".join(f"{d}  {n}\n" for n, d in sums.items()), encoding="utf-8")
    return sums


def arrays(data: bytes) -> tuple[PropertyRecord, ...]:
    compound = open_compound(data)
    found, trailing, issues = parse_blocks(compound.read("EmbeddedBoards6/Data"), where="EmbeddedBoards6")
    assert not trailing and not issues
    assert compound.read("EmbeddedBoards6/Header") == len(found).to_bytes(4, "little")
    return found


def _units(text: str | None) -> int:
    value = parse_mil(text)
    assert value is not None and value.denominator == 1, text
    return int(value)


def test_phase_b_kit(tmp_path: Path) -> None:
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "Q-panels"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    folder.mkdir(parents=True, exist_ok=True)
    assert pcbdoc.EMBEDDED_ARRAYS is False, "phase B forces the gate for the kit only"
    sums = phase_b(folder)
    assert {"written/panel.PcbDoc", "written/panel.PrjPcb", "flat/panel.PcbDoc", "expected.md"} <= set(sums)
    lines = (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert lines == [f"{d}  {n}" for n, d in sums.items()]
    written = (folder / "written" / "panel.PcbDoc").read_bytes()
    doc = read_pcbdoc(written)
    assert not [i for i in doc.issues if i.severity == "error"]
    (array,) = arrays(written)
    assert array.get("DOCUMENTPATH") == DOCUMENT
    assert (array.get("ROWCOUNT"), array.get("COLCOUNT")) == ("2", "2")
    assert abs(_units(array.get("COLSPACING")) - rec.to_units(42 * MM)) <= 1
    assert abs(_units(array.get("ROWSPACING")) - rec.to_units(32 * MM)) <= 1
    assert not doc.components, "no copy of the board"
    assert arrays((folder / "flat" / "panel.PcbDoc").read_bytes()) == ()
    expected = (folder / "expected.md").read_text(encoding="utf-8")
    for word in ("`../board/board.PcbDoc`", "42 mm, 32 mm", "**Q7**", "**Q12**", "Route Tool Path", "V-Cut"):
        assert word in expected, word
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".PrjPcb", ".md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            assert not re.search(r"(?:[A-Za-z]:\\|/home/|/tmp/|/Users/)", text), path.name


@pytest.mark.skipif(not Q12, reason="FENOLITE_ALTIUM_Q12 names panel-saved.PcbDoc of case Q12")
def test_q12_saved_array_reads_back() -> None:
    """Case Q12: the array that Altium saved again has the counts, spacing, rotation and document path that
    phase B wrote."""
    assert Q12
    (array,) = arrays(Path(Q12).expanduser().read_bytes())
    assert array.get("DOCUMENTPATH") == DOCUMENT
    assert (array.get("ROWCOUNT"), array.get("COLCOUNT")) == ("2", "2")
    assert abs(_units(array.get("COLSPACING")) - rec.to_units(42 * MM)) <= 1
    assert abs(_units(array.get("ROWSPACING")) - rec.to_units(32 * MM)) <= 1
    assert float(array.text("ROTATION")) == 0 and array.get("MIRROR") == "FALSE"


MEASURED_KEYS = (
    "DOCUMENTPATH", "X", "Y", "X1", "Y2", "ROTATION", "ROWSPACING", "COLSPACING", "ROWCOUNT", "COLCOUNT",
    "MIRROR", "ORIGINMODE",
)  # fmt: skip


def test_measured_rows_name_every_written_key() -> None:
    """Task 7.1: every key the writer sets from a property has an ``INFERRED`` row of S-1422, and each
    variant of Q2 is named by the row of its field."""
    page = (ROOT / "docs" / "formats" / "altium" / "pcb-document.md").read_text(encoding="utf-8")
    rows = [line for line in page.splitlines() if "| S-1422 |" in line or "S-1422," in line]
    assert rows and all("H-A-PANEL-" in row for row in rows)
    text = " ".join(rows)
    for key in MEASURED_KEYS:
        assert f"`{key}`" in text, key
    for variant in ("panel-a", "panel-cols4", "panel-rows3", "panel-spacing", "panel-margin", "panel-rot90",
                    "panel-mirror", "panel-link", "panel-move", "panel-two"):  # fmt: skip
        assert f"`{variant}`" in text, variant
    written, *_ = parse_blocks(
        rec.embedded_board_array(DOCUMENT, (0, 0), (1, 1), rows=1, cols=1, row_spacing=1, col_spacing=1),
        where="array",
    )
    keys = written[0].keys()
    assert all(f"`{key}`" in text for key in keys if not key.startswith("VIEWPORT")), keys
