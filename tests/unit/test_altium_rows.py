# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The form of the Altium schematic-writer rows of ``docs/hypotheses.md`` (capability altium-build,
"Altium author reports", change c0032; "Binary sample and Viewer check", change c0033).

Every ``H-A-SCH-*``, ``H-A-SCHBIN-*`` and ``H-A-PRJ-*`` row is refuted with a registered successor, or
is ``INFERRED`` with a result starting ``pending (author report)``, or carries the author-report label
with its four fields; the tool field is ``AD <major>.<minor or x>`` or ``A365 Viewer`` (the Altium 365
Viewer shows no version).
``test_hypotheses_register.register_problems`` checks that form only for ``H-A-WRITE-*`` and ``H-A-PH-*``,
so this change checks its own rows here. The unit cases use registered ids only.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import pytest

from fenolite.core.evidence import Level
from fenolite.verify import HypothesisRow, load_register, parse_level

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "hypotheses.md"
STEMS = ("H-A-SCH-", "H-A-SCHBIN-", "H-A-PRJ-")
REGISTERED_BY_C0032 = frozenset(
    {
        "H-A-SCH-OPEN",
        "H-A-SCH-LINEEND",
        "H-A-SCH-UID",
        "H-A-SCH-NETS",
        "H-A-SCH-LINK",
        "H-A-SCH-ECO",
        "H-A-SCH-RELINK",
        "H-A-SCH-UPDATE",
        "H-A-PRJ-OPEN",
        "H-A-PRJ-KEEP",
    }
)
REGISTERED_BY_C0033 = frozenset(
    {"H-A-SCHBIN-CFB", "H-A-SCHBIN-FRAME", "H-A-SCHBIN-STORAGE", "H-A-SCHBIN-VIEWER", "H-A-SCHBIN-AD"}
)
FORM = (
    "ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact) "
    "(tool field A365 Viewer for the Altium 365 Viewer), "
    "INFERRED with a result starting 'pending (author report)', "
    "or a result starting 'refuted; superseded by <id>-2' naming a registered successor"
)
_LABEL = re.compile(r"ALTIUM-VERIFIED\(([^()]*)\)")


def report_label_ok(text: str) -> bool:
    """True for ``ALTIUM-VERIFIED(author-report; <tool>; <YYYY-MM-DD>; no artefact)``, the tool being
    ``AD <major>.<minor or x>`` or ``A365 Viewer``."""
    match = _LABEL.fullmatch(text)
    if match is None:
        return False
    fields = [field.strip() for field in match.group(1).split(";")]
    if len(fields) != 4 or fields[0] != "author-report" or fields[3] != "no artefact":
        return False
    if re.fullmatch(r"AD \d+\.(\d+|x)|A365 Viewer", fields[1]) is None:
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[2]) is None:
        return False
    try:
        date.fromisoformat(fields[2])
    except ValueError:
        return False
    return True


def row_problems(rows: Sequence[HypothesisRow]) -> list[str]:
    """One message per ``H-A-SCH-*``, ``H-A-SCHBIN-*`` or ``H-A-PRJ-*`` row whose level and result break
    the form."""
    registered = {row.id for row in rows}
    problems: list[str] = []
    for row in rows:
        if not row.id.startswith(STEMS):
            continue
        if row.refuted:
            successor = row.successor
            if (
                not row.result.startswith("refuted; superseded by ")
                or successor is None
                or successor == row.id
                or successor not in registered
            ):
                problems.append(f"{row.id}: a refuted row needs a registered successor; expected {FORM}")
            continue
        pending = row.level_text == "INFERRED" and row.result.startswith("pending (author report)")
        if not pending and not report_label_ok(row.level_text):
            problems.append(f"{row.id}: level {row.level_text!r} and result break the form; expected {FORM}")
    return problems


# --- live register ----------------------------------------------------------------------------------


def test_rows_are_well_formed() -> None:
    problems = row_problems(load_register(REGISTER))
    assert not problems, "\n".join(problems)


def test_the_change_registered_its_rows() -> None:
    rows = {row.id: row for row in load_register(REGISTER)}
    ids = REGISTERED_BY_C0032 | REGISTERED_BY_C0033
    assert ids <= set(rows)
    assert all(rows[i].backend == "altium" for i in ids)
    assert all(rows[i].test.startswith("kit request") for i in ids)


# --- unit cases -------------------------------------------------------------------------------------


def _row(ident: str, level: str = "INFERRED", result: str = "pending (author report)") -> HypothesisRow:
    parsed = parse_level(level)
    return HypothesisRow(ident, "altium", "a claim", parsed, level, "kit request", "a", result, "2026-10-02")


def test_bare_author_report_cell_is_reported() -> None:
    problems = row_problems([_row("H-A-SCH-OPEN", level="ALTIUM-VERIFIED(author-report)")])
    assert len(problems) == 1
    assert problems[0].startswith("H-A-SCH-OPEN: ")
    assert "ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)" in problems[0]


@pytest.mark.parametrize(
    "level",
    [
        "ALTIUM-VERIFIED(author-report; AD 24.3; 2026-10-03; no artefact)",
        "ALTIUM-VERIFIED(author-report; AD 25.x; 2026-10-04; no artefact)",
    ],
)
def test_well_formed_report_rows(level: str) -> None:
    assert row_problems([_row("H-A-PRJ-OPEN", level=level, result="confirmed")]) == []


@pytest.mark.parametrize(
    "level",
    [
        "ALTIUM-VERIFIED(author-report; AD 24.3; 2026-10; no artefact)",
        "ALTIUM-VERIFIED(author-report; AD 24.3; 2026-13-01; no artefact)",
        "ALTIUM-VERIFIED(author-report; 24.3; 2026-10-03; no artefact)",
        "ALTIUM-VERIFIED(author-report; AD 24.3; 2026-10-03)",
        "ALTIUM-VERIFIED(kit; AD 24.3; 2026-10-03; no artefact)",
        "KICAD-VERIFIED",
    ],
)
def test_malformed_levels(level: str) -> None:
    problems = row_problems([_row("H-A-SCH-NETS", level=level, result="confirmed")])
    assert len(problems) == 1 and problems[0].startswith("H-A-SCH-NETS: ")


def test_pending_rows() -> None:
    assert row_problems([_row("H-A-SCH-UID")]) == []
    assert row_problems([_row("H-A-SCH-UID", result="pending")]) != []
    assert row_problems([_row("H-A-SCH-UID", level="INFERRED (local)")]) != []


def test_refuted_rows_need_a_registered_successor() -> None:
    ident = "H-A-SCH-LINK"
    successor = f"{ident}-2"
    level = "ALTIUM-VERIFIED(author-report; AD 24.3; 2026-10-03; no artefact)"
    refuted = _row(ident, level=level, result=f"refuted; superseded by {successor}; mode Any")
    assert row_problems([refuted, _row(successor)]) == []
    (problem,) = row_problems([refuted])
    assert problem.startswith(f"{ident}: a refuted row needs a registered successor")
    (problem,) = row_problems([_row(ident, level=level, result=f"refuted; superseded by {ident}")])
    assert problem.startswith(f"{ident}: ")


def test_other_families_are_ignored() -> None:
    assert row_problems([_row("H-A-WRITE-SCHDOC", level="ALTIUM-VERIFIED(author-report)")]) == []
    assert row_problems([_row("H-A-UNIT", result="pending")]) == []


def test_level_parses_as_author_report() -> None:
    level = parse_level("ALTIUM-VERIFIED(author-report; AD 24.3; 2026-10-03; no artefact)")
    assert level is Level.ALTIUM_VERIFIED_AUTHOR_REPORT


def test_viewer_report_form() -> None:
    """A Viewer row with the ``A365 Viewer`` tool passes; a bare author-report label is reported."""
    viewer = _row(
        "H-A-SCHBIN-VIEWER", "ALTIUM-VERIFIED(author-report; A365 Viewer; 2026-10-03; no artefact)", "ok"
    )
    bare = _row("H-A-SCHBIN-AD", level="ALTIUM-VERIFIED(author-report)")
    problems = row_problems([viewer, bare])
    assert len(problems) == 1 and problems[0].startswith("H-A-SCHBIN-AD: ")
    assert "ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)" in problems[0]
    assert "A365 Viewer" in problems[0]


@pytest.mark.parametrize("tool", ["A365 viewer", "Viewer", "A365 Viewer 1.0"])
def test_other_tool_fields_refused(tool: str) -> None:
    level = f"ALTIUM-VERIFIED(author-report; {tool}; 2026-10-03; no artefact)"
    assert row_problems([_row("H-A-SCHBIN-CFB", level=level, result="confirmed")]) != []
