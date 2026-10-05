# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The form of the Altium schematic-writer rows of ``docs/hypotheses.md`` (capability altium-build,
"Altium author reports", change c0032; "Binary sample and Viewer check", change c0033).

Every ``H-A-SCH-*``, ``H-A-SCHBIN-*``, ``H-A-SCHLIB-*`` and ``H-A-PRJ-*`` row is refuted with a
registered successor, or is ``INFERRED`` with a result starting ``pending (author report)``, or carries
the author-report label with its four fields; the tool field is ``AD <major>.<minor or x>`` or
``A365 Viewer`` (the Altium 365 Viewer shows no version). The two oracle rows of change c0034
(``ORACLE_ROWS``) are settled by ``kicad-cli`` instead: ``pending (oracle)`` or ``pending (kicad-9 job)``
until it runs, then a KiCad or oracle label.
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
STEMS = ("H-A-SCH-", "H-A-SCHBIN-", "H-A-SCHLIB-", "H-A-PRJ-", "H-A-PCB-", "H-A-ECO-")
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
REGISTERED_BY_C0034 = frozenset(
    {
        "H-A-SCHLIB-OPEN",
        "H-A-SCHLIB-PIN",
        "H-A-SCHLIB-PARTS",
        "H-A-SCHLIB-IMPLIDX",
        "H-A-SCHLIB-PRJ",
        "H-A-SCHLIB-SCHDOC",
        "H-A-SCHLIB-MULTIPART",
        "H-A-SCHLIB-UPDATE",
        "H-A-SCHLIB-SECTIONKEY",
    }
)
ORACLE_ROWS = frozenset(
    {
        "H-A-SCHLIB-KICAD",
        "H-A-SCHLIB-KICAD9",
        "H-A-PCB-KICAD-LIB",
        "H-A-PCB-KICAD-DOC",
        "H-A-PCB-CU-KICAD",
        "H-A-PCB-CU-ROUNDTRIP",
    }
)
"""Rows settled by a ``kicad-cli`` round trip, not by an author report (changes c0034, c0035 and c0038)."""
ORACLE_TESTS = {
    "H-A-SCHLIB-KICAD": "test_schlib_oracle.py",
    "H-A-SCHLIB-KICAD9": "test_schlib_oracle.py",
    "H-A-PCB-KICAD-LIB": "test_pcblib_oracle.py",
    "H-A-PCB-KICAD-DOC": "test_pcbdoc_oracle.py",
    "H-A-PCB-CU-KICAD": "test_pcbdoc_copper_oracle.py",
    "H-A-PCB-CU-ROUNDTRIP": "test_copper_from_oracle.py",
}
ORACLE_THEN_REPORT = frozenset({"H-A-PCB-DOC-BOTTOM"})
"""Rows checked by an oracle first (``pending (oracle)``), then settled by an author report (c0035)."""
REGISTERED_BY_C0035 = frozenset(
    {
        "H-A-PCB-LIB-OPEN",
        "H-A-PCB-LIB-NAME",
        "H-A-PCB-PAD",
        "H-A-PCB-GRAPHICS",
        "H-A-PCB-ECO",
        "H-A-PCB-PRJ",
        "H-A-PCB-DOC-VIEWER",
        "H-A-PCB-DOC-OPEN",
        "H-A-PCB-DOC-LINK",
        "H-A-PCB-DOC-NETS",
    }
)
REGISTERED_BY_C0036 = frozenset({"H-A-SCH-NC-RECORD", "H-A-SCH-NC-ERC", "H-A-SCH-NC-VIEWER"})
REGISTERED_BY_C0037 = frozenset(
    {
        "H-A-SCH-HIER-OPEN",
        "H-A-SCH-HIER-PRJ",
        "H-A-SCH-HIER-COMPILE",
        "H-A-SCH-HIER-NAMES",
        "H-A-SCH-HIER-ECO",
        "H-A-SCH-HARN-OPEN",
        "H-A-SCH-HARN-FILE",
        "H-A-SCH-HARN-NETS",
        "H-A-SCH-HARN-UNUSED",
        "H-A-SCHBIN-MINI",
        "H-A-SCH-HIER-ORDER",
    }
)
"""The hierarchy and harness rows (change c0037), settled by Part H of the schematic evidence page; the
last two were registered after the reports of step H7: the first is refuted and the second succeeds it."""
REGISTERED_BY_C0038 = frozenset(
    {
        "H-A-PCB-CU-TRACK",
        "H-A-PCB-CU-VIA",
        "H-A-PCB-CU-STACK",
        "H-A-PCB-CU-PLANE",
        "H-A-PCB-CU-REPOUR",
        "H-A-PCB-CU-CLASS",
        "H-A-PCB-CU-RULES",
        "H-A-PCB-CU-VIEWER",
    }
)
"""The author-report rows of the PCB copper (change c0038); its two oracle rows are in ``ORACLE_ROWS``."""
REGISTERED_BY_C0048 = frozenset(
    {
        "H-A-ECO-NETCLASS",
        "H-A-ECO-PRJ-KEYS",
        "H-A-ECO-COMPCLASS",
        "H-A-ECO-ROOMS",
        "H-A-ECO-SUPPLY",
        "H-A-ECO-SHEETCLASS",
    }
)
"""The rows of the change order (change c0048), settled by Part E of the PCB evidence page."""
REGISTERED_BY_C0040 = frozenset(
    {
        "H-A-RD-SCH-FRAME",
        "H-A-RD-SCH-IDENT",
        "H-A-RD-SCH-HEADER",
        "H-A-RD-SCH-CASE",
        "H-A-RD-SCH-TEXT",
        "H-A-RD-SCH-TEXT-2",
        "H-A-RD-SCH-OWNER",
        "H-A-RD-SCH-ADDOWNER",
        "H-A-RD-SCH-LIBOWNER",
        "H-A-RD-SCH-FRAC",
        "H-A-RD-SCH-PARTS",
        "H-A-RD-SCH-PIN",
        "H-A-RD-SCH-PINSIDE",
        "H-A-RD-SCH-STORAGE",
        "H-A-RD-SCH-ASCII",
        "H-A-RD-SCH-KICAD",
    }
)
"""The rows of the schematic reader (change c0040), settled by the corpus test, the census and the library
oracle, not by an author report; their form is that of any register row. ``H-A-RD-SCH-TEXT-2`` succeeds the
refuted ``H-A-RD-SCH-TEXT``."""
ORACLE_LEVELS = re.compile(r"ORACLE-VERIFIED\(kicad-cli\)( \(.+\))?|KICAD-VERIFIED( \(.+\))?")
FORM = (
    "ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact) "
    "(tool field A365 Viewer for the Altium 365 Viewer), "
    "INFERRED with a result starting 'pending (author report)', "
    "or a result starting 'refuted; superseded by <successor id>' naming a registered successor"
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
        if row.id in ORACLE_ROWS:
            pending = row.level_text in ("INFERRED", "UNKNOWN") and row.result.startswith("pending (")
            settled = ORACLE_LEVELS.fullmatch(row.level_text) is not None and not row.result.startswith(
                "pending"
            )
            if not (pending or settled or row.refuted):
                problems.append(f"{row.id}: an oracle row is pending or carries a KiCad or oracle label")
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
        if row.id in ORACLE_THEN_REPORT:
            pending = pending or (row.level_text == "INFERRED" and row.result.startswith("pending (oracle)"))
        if not pending and not report_label_ok(row.level_text):
            problems.append(f"{row.id}: level {row.level_text!r} and result break the form; expected {FORM}")
    return problems


# --- live register ----------------------------------------------------------------------------------


def test_rows_are_well_formed() -> None:
    problems = row_problems(load_register(REGISTER))
    assert not problems, "\n".join(problems)


def test_the_change_registered_its_rows() -> None:
    rows = {row.id: row for row in load_register(REGISTER)}
    ids = (
        REGISTERED_BY_C0032
        | REGISTERED_BY_C0033
        | REGISTERED_BY_C0034
        | REGISTERED_BY_C0035
        | REGISTERED_BY_C0036
        | REGISTERED_BY_C0037
        | REGISTERED_BY_C0038
        | REGISTERED_BY_C0048
    )
    assert ids <= set(rows)
    assert all(rows[i].backend == "altium" for i in ids)
    assert all(rows[i].test.startswith("kit request") for i in ids)
    assert ORACLE_ROWS <= set(rows)
    assert all(rows[i].backend == "altium" and ORACLE_TESTS[i] in rows[i].test for i in ORACLE_ROWS)
    assert ORACLE_THEN_REPORT <= set(rows)
    assert all("test_pcbdoc_oracle.py" in rows[i].test for i in ORACLE_THEN_REPORT)
    copper = {i for i in rows if i.startswith("H-A-PCB-CU-")}
    assert copper == REGISTERED_BY_C0038 | {"H-A-PCB-CU-KICAD", "H-A-PCB-CU-ROUNDTRIP"}
    assert {i for i in rows if i.startswith("H-A-ECO-")} == REGISTERED_BY_C0048


def test_the_reader_registered_its_rows() -> None:
    rows = {row.id: row for row in load_register(REGISTER)}
    assert REGISTERED_BY_C0040 <= set(rows)
    assert {i for i in rows if i.startswith("H-A-RD-SCH-")} == REGISTERED_BY_C0040
    assert all(rows[i].backend == "altium" for i in REGISTERED_BY_C0040)
    assert all(not rows[i].test.startswith("kit request") for i in REGISTERED_BY_C0040)


def test_oracle_then_report_rows() -> None:
    assert row_problems([_row("H-A-PCB-DOC-BOTTOM", result="pending (oracle)")]) == []
    assert row_problems([_row("H-A-PCB-DOC-BOTTOM")]) == []
    assert row_problems([_row("H-A-PCB-PAD", result="pending (oracle)")]) != []


def test_oracle_rows() -> None:
    assert row_problems([_row("H-A-SCHLIB-KICAD", result="pending (oracle)")]) == []
    assert row_problems([_row("H-A-SCHLIB-KICAD9", level="UNKNOWN", result="pending (kicad-9 job)")]) == []
    done = _row("H-A-SCHLIB-KICAD", level="ORACLE-VERIFIED(kicad-cli) (10.0.6)", result="confirmed")
    assert row_problems([done]) == []
    assert (
        row_problems([_row("H-A-SCHLIB-KICAD", level="ORACLE-VERIFIED(kicad-cli)", result="pending")]) != []
    )
    assert row_problems([_row("H-A-SCHLIB-KICAD", result="confirmed")]) != []


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
