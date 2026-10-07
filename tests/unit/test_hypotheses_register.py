# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The hypothesis register stays consistent with the ids cited in live text (capability
verification-evidence, change c0014).

``register_problems`` checks the rows; ``citation_problems`` checks every id cited under ``ROOTS`` and in
the top-level Markdown files. Temporary-tree cases use ids the real register holds, so this file cites
nothing unregistered except the ``SYNTHETIC`` literals it must spell to declare them.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from fenolite.core.evidence import Level
from fenolite.verify import (
    HypothesisRow,
    cited_ids,
    load_families,
    load_register,
    proposed_ids,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTER = "docs/hypotheses.md"
ROOTS = ("docs", "openspec/specs", "openspec/changes", "src", "tests", "tools")
EXCLUDE = ("openspec/changes/archive", "tests/corpus/cache")
SYNTHETIC: dict[str, frozenset[str]] = {
    "tests/unit/core/test_evidence.py": frozenset({"H-K-1", "H-G-2"}),
    "tests/unit/test_hypotheses_register.py": frozenset({"H-K-1", "H-G-2"}),
}
AUTHOR_FAMILIES = ("H-A-WRITE-", "H-A-PH-")
AUTHOR_FORM = (
    "ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD or YYYY-MM>; no artefact), "
    "or INFERRED with a result starting 'pending (author report)'"
)
_AUTHOR_LEVEL = re.compile(r"ALTIUM-VERIFIED\(([^()]*)\)")


def _author_level_ok(row: HypothesisRow) -> bool:
    if row.level is Level.INFERRED:
        return row.level_text == "INFERRED" and row.result.startswith("pending (author report)")
    match = _AUTHOR_LEVEL.fullmatch(row.level_text)
    if match is None:
        return False
    fields = [field.strip() for field in match.group(1).split(";")]
    return (
        len(fields) == 4
        and fields[0] == "author-report"
        and re.fullmatch(r"AD \d+\.(\d+|x)", fields[1]) is not None
        and re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", fields[2]) is not None
        and fields[3] == "no artefact"
    )


def register_problems(rows: Sequence[HypothesisRow]) -> list[str]:
    """Duplicate ids, refuted rows without a registered successor, and malformed author-report rows."""
    problems: list[str] = []
    counts = Counter(row.id for row in rows)
    problems += [f"{ident}: duplicate id ({n} rows)" for ident, n in sorted(counts.items()) if n > 1]
    ids = set(counts)
    for row in rows:
        if row.refuted:
            if row.successor is None:
                problems.append(
                    f"{row.id}: refuted, but its result names no successor ('superseded by <id>')"
                )
            elif row.successor == row.id:
                problems.append(f"{row.id}: superseded by itself")
            elif row.successor not in ids:
                problems.append(f"{row.id}: superseded by {row.successor}, which is not registered")
        if row.id.startswith(AUTHOR_FAMILIES):
            if not _author_level_ok(row):
                problems.append(f"{row.id}: an author-report row needs level {AUTHOR_FORM}")
            if not row.test.startswith("kit request"):
                problems.append(f"{row.id}: an author-report row needs a test column starting 'kit request'")
    return problems


def _roots(root: Path) -> list[Path]:
    return [root / r for r in ROOTS if (root / r).exists()] + sorted(root.glob("*.md"))


def citation_problems(root: Path, *, synthetic: Mapping[str, frozenset[str]] = SYNTHETIC) -> list[str]:
    """Every cited id or family that is not registered, proposed (inside an active change), reserved
    or allowed as a synthetic literal, as ``<path>: <id>`` messages."""
    register = root / REGISTER
    registered = {row.id for row in load_register(register)}
    families = set(load_families(register))
    proposed = proposed_ids(root / "openspec" / "changes")
    cited = cited_ids(_roots(root), base=root, exclude=EXCLUDE)
    problems: list[str] = []
    for key, paths in cited.items():
        for path in paths:
            in_change = path.startswith("openspec/changes/") and not path.startswith(
                "openspec/changes/archive/"
            )
            known = registered | proposed if in_change else registered
            if key.endswith("-*"):
                stem = key[:-2]
                ok = key in families or stem in known or any(i.startswith(stem + "-") for i in known)
            else:
                ok = key in known
            if not ok and key not in synthetic.get(path, frozenset()):
                problems.append(f"{path}: {key} is not registered in {REGISTER}")
    return sorted(problems)


# --- live tests -----------------------------------------------------------------------------------


def test_register_loads() -> None:
    rows = load_register(ROOT / REGISTER)
    lines = (ROOT / REGISTER).read_text(encoding="utf-8").splitlines()
    assert len(rows) == sum(1 for line in lines if line.startswith("| H-"))


def test_register_integrity() -> None:
    problems = register_problems(load_register(ROOT / REGISTER))
    assert not problems, "\n".join(problems)


def test_cited_ids_registered() -> None:
    problems = citation_problems(ROOT)
    assert not problems, "register these ids in docs/hypotheses.md (or reword the citation):\n" + "\n".join(
        problems
    )


def test_author_report_rows_exist_for_both_families() -> None:
    ids = [row.id for row in load_register(ROOT / REGISTER)]
    assert any(i.startswith("H-A-WRITE-") for i in ids) and any(i.startswith("H-A-PH-") for i in ids)


def test_the_allowlist_is_closed() -> None:
    assert set(SYNTHETIC) == {"tests/unit/core/test_evidence.py", "tests/unit/test_hypotheses_register.py"}


# --- register_problems --------------------------------------------------------------------------------


def _row(
    ident: str, *, level: str = "INFERRED", result: str = "pending", test: str = "a test"
) -> HypothesisRow:
    from fenolite.verify import parse_level

    return HypothesisRow(
        ident, "kicad", "a claim", parse_level(level), level, test, "a criterion", result, "2026-10-01"
    )


def test_duplicate_id() -> None:
    problems = register_problems([_row("H-K-UNIT"), _row("H-K-UNIT")])
    assert len(problems) == 1 and "H-K-UNIT" in problems[0] and "duplicate" in problems[0]


def test_refuted_row_without_a_registered_successor() -> None:
    refuted = _row("H-K-SEXPR-NUM-WRITE", result="refuted; superseded by H-K-SEXPR-NUM-WRITE-2; observed")
    problems = register_problems([refuted])
    assert (
        len(problems) == 1 and "H-K-SEXPR-NUM-WRITE" in problems[0] and "H-K-SEXPR-NUM-WRITE-2" in problems[0]
    )
    assert register_problems([refuted, _row("H-K-SEXPR-NUM-WRITE-2")]) == []


def test_row_superseded_by_itself() -> None:
    problems = register_problems([_row("H-K-TOK-FUTURE", result="refuted; superseded by H-K-TOK-FUTURE")])
    assert problems == ["H-K-TOK-FUTURE: superseded by itself"]


def test_refuted_row_naming_no_successor() -> None:
    problems = register_problems([_row("H-K-TOK-FUTURE", result="refuted on 9.0.9")])
    assert len(problems) == 1 and "names no successor" in problems[0]


@pytest.mark.parametrize(
    "level",
    ["ALTIUM-VERIFIED(author-report)", "ALTIUM-VERIFIED(author-report; 24; soon; no artefact)"],
)
def test_malformed_author_report_rows_are_refused(level: str) -> None:
    problems = register_problems([_row("H-A-WRITE-SCHLIB", level=level, test="kit request (v0.3): open")])
    assert (
        len(problems) == 1
        and "H-A-WRITE-SCHLIB" in problems[0]
        and "ALTIUM-VERIFIED(author-report;" in problems[0]
    )


def test_well_formed_author_report_row_is_accepted() -> None:
    level = "ALTIUM-VERIFIED(author-report; AD 24.x; 2026-09; no artefact)"
    assert register_problems([_row("H-A-WRITE-SCHLIB", level=level, test="kit request (v0.3): open")]) == []


def test_pending_author_rows_are_accepted() -> None:
    row = _row("H-A-PH-CHECKSUM", result="pending (author report): later", test="kit request (v0.3): open")
    assert register_problems([row]) == []


def test_author_row_needs_a_kit_request() -> None:
    row = _row("H-A-PH-CHECKSUM", result="pending (author report): later", test="a test")
    assert register_problems([row]) == [
        "H-A-PH-CHECKSUM: an author-report row needs a test column starting 'kit request'"
    ]


# --- citation_problems on temporary trees -----------------------------------------------------------

HEADER = (
    "| id | backend | statement | level | test or kit request | criterion | result | date |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def _tree(
    root: Path, files: dict[str, str], *, registered: Sequence[str] = ("H-K-UNIT",), families: str = ""
) -> Path:
    rows = "".join(f"| {i} | kicad | c | INFERRED | t | k | pending | 2026-10-01 |\n" for i in registered)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / REGISTER).write_text(HEADER + rows + families, encoding="utf-8")
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_unregistered_id_in_a_document(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"docs/x.md": "see H-K-02"})
    assert citation_problems(root) == ["docs/x.md: H-K-02 is not registered in docs/hypotheses.md"]


def test_registered_id_passes(tmp_path: Path) -> None:
    assert citation_problems(_tree(tmp_path, {"docs/x.md": "see H-K-UNIT"})) == []


def test_unregistered_id_in_the_changelog(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"CHANGELOG.md": "adds H-K-02"})
    assert citation_problems(root) == ["CHANGELOG.md: H-K-02 is not registered in docs/hypotheses.md"]


def test_dot_files_are_skipped(tmp_path: Path) -> None:
    assert citation_problems(_tree(tmp_path, {"openspec/changes/c0099-x/.openspec.yaml": "H-K-02"})) == []


def test_archived_changes_are_history(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"openspec/changes/archive/2026-01-01-c0001-x/design.md": "H-K-02"})
    assert citation_problems(root) == []


def test_stem_extended_by_a_row(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"docs/x.md": "H-K-FMT-* rows"}, registered=("H-K-FMT-INDENT",))
    assert citation_problems(root) == []


def test_stem_with_no_row(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"docs/x.md": "H-K-TOK-* rows"})
    assert citation_problems(root) == ["docs/x.md: H-K-TOK-* is not registered in docs/hypotheses.md"]


def test_reserved_family(tmp_path: Path) -> None:
    families = (
        "\n| family | backend | rows for | owner |\n|---|---|---|---|\n"
        "| `H-K-KRT-*` | kicad | routing | later |\n"
    )
    root = _tree(tmp_path, {"docs/x.md": "H-K-KRT-* rows"}, families=families)
    assert citation_problems(root) == []


def test_prefix_in_a_grep_pattern(tmp_path: Path) -> None:
    root = _tree(
        tmp_path, {"docs/x.md": "grep -c '^| H-K-FMT-' docs/hypotheses.md"}, registered=("H-K-FMT-INDENT",)
    )
    assert citation_problems(root) == []


def test_range_notation(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"docs/x.md": "H-K-00…H-K-03"}, registered=("H-K-00", "H-K-03"))
    assert citation_problems(root) == []


def _proposing_design(ident: str) -> str:
    return (
        f"## Hypotheses registered by this change\n\n| id | statement |\n|---|---|\n| {ident} | a claim |\n"
    )


def test_proposed_id_cited_by_an_active_change(tmp_path: Path) -> None:
    files = {
        "openspec/changes/c0099-x/design.md": _proposing_design("H-K-SEXPR-STRICT"),
        "openspec/changes/c0098-y/tasks.md": "register H-K-SEXPR-STRICT",
    }
    assert citation_problems(_tree(tmp_path, files)) == []


def test_proposed_id_cited_outside_the_changes(tmp_path: Path) -> None:
    files = {
        "openspec/changes/c0099-x/design.md": _proposing_design("H-K-SEXPR-STRICT"),
        "openspec/changes/c0098-y/tasks.md": "register H-K-SEXPR-STRICT",
        "src/fenolite/x.py": "# H-K-SEXPR-STRICT",
    }
    problems = citation_problems(_tree(tmp_path, files))
    assert problems == ["src/fenolite/x.py: H-K-SEXPR-STRICT is not registered in docs/hypotheses.md"]


def test_archived_designs_propose_nothing(tmp_path: Path) -> None:
    files = {
        "openspec/changes/archive/2026-01-01-c0097-z/design.md": _proposing_design("H-K-SEXPR-STRICT"),
        "openspec/changes/c0098-y/tasks.md": "register H-K-SEXPR-STRICT",
    }
    problems = citation_problems(_tree(tmp_path, files))
    assert problems == [
        "openspec/changes/c0098-y/tasks.md: H-K-SEXPR-STRICT is not registered in docs/hypotheses.md"
    ]


def test_the_evidence_test_passes() -> None:
    assert not [p for p in citation_problems(ROOT) if p.startswith("tests/unit/core/test_evidence.py")]


def test_a_synthetic_id_elsewhere_fails(tmp_path: Path) -> None:
    root = _tree(tmp_path, {"tests/unit/test_other.py": "ids = ('H-K-1',)"})
    assert citation_problems(root) == [
        "tests/unit/test_other.py: H-K-1 is not registered in docs/hypotheses.md"
    ]


# --- kit label rows (capability verification-evidence, "Kit label rows"; change c0091) -------------------


def kit_label_problems(rows: Sequence[HypothesisRow], root: Path) -> list[str]:
    """One message per row that carries ``ALTIUM-VERIFIED(kit; …)`` without a committed, passing, current
    run record under ``root`` (``fenolite.verify.kit.record.label_problems``). The kit that the tree builds
    is built only when a row carries the label."""
    if not any(row.level is Level.ALTIUM_VERIFIED_KIT for row in rows):
        return []
    from fenolite.cli._kit import kit_sources
    from fenolite.verify.kit.manifest import kit_files, read_kit
    from fenolite.verify.kit.record import label_problems, load_records

    kit = read_kit(kit_files(kit_sources())["kit.json"])
    return label_problems(rows, load_records(root), kit)


def test_kit_labels_of_the_register_have_their_record() -> None:
    problems = kit_label_problems(load_register(ROOT / REGISTER), ROOT)
    assert not problems, "\n".join(problems)


KIT_RUN = "2026-11-01-abcdef12"
KIT_LABEL = f"ALTIUM-VERIFIED(kit; AD 26.5; 2026-11-01; {KIT_RUN})"
KIT_ARCHIVE = "abcdef12" + "0" * 56


def _kit_record(**changes: object) -> dict[str, object]:
    """A run record written out for these tests: it is no run, and it is written only into a test folder."""
    from fenolite.cli._kit import kit_sources
    from fenolite.verify.kit.manifest import kit_files, read_kit
    from fenolite.verify.kit.record import RUN_SCHEMA, step_source

    kit = read_kit(kit_files(kit_sources())["kit.json"])
    steps = [
        {
            "id": s.id,
            "kind": s.kind,
            "outcome": "pass",
            "scripted": False,
            "pending": [],
            "source": step_source(kit, s),
        }
        for s in kit.steps
    ]
    record: dict[str, object] = {
        "schema": RUN_SCHEMA,
        "run_id": KIT_RUN,
        "date": "2026-11-01",
        "synthetic": False,
        "kit_sha256": kit.digest,
        "kit_version": 1,
        "kit_fenolite_version": "0",
        "fenolite_version": "0",
        "altium_version": "AD 26.5",
        "os_family": "Windows",
        "samples": dict(kit.samples),
        "script_sha256": kit.script_sha256,
        "steps": steps,
        "hypotheses": [
            {"id": "H-A-KIT-RESAVE", "outcome": "pass", "form": False},
            {"id": "H-A-PCBX-STACK", "outcome": "pass", "form": True},
            {"id": "H-A-KIT-COMPILE", "outcome": "fail", "form": True},
        ],
        "results": [],
        "privacy_findings": 0,
        "archive": {"name": f"altium-kit-{KIT_RUN}.zip", "sha256": KIT_ARCHIVE, "size": 1},
    }
    record.update(changes)
    return record


def _committed(root: Path, record: Mapping[str, object]) -> Path:
    import json

    folder = root / "docs" / "evidence" / "altium-kit"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{record['run_id']}.json").write_text(json.dumps(record), encoding="utf-8", newline="\n")
    return root


def _kit_row(
    ident: str = "H-A-KIT-RESAVE", result: str = f"confirmed (archive {KIT_ARCHIVE})"
) -> HypothesisRow:
    return _row(ident, level=KIT_LABEL, result=result)


def test_kit_label_without_a_record(tmp_path: Path) -> None:
    """Scenario "Label without a record": the row and the missing record are named."""
    assert kit_label_problems([_kit_row()], tmp_path) == [
        f"H-A-KIT-RESAVE: no run record {KIT_RUN}.json under docs/evidence/altium-kit"
    ]


def test_kit_label_with_a_record(tmp_path: Path) -> None:
    """Scenario "Label with a record"."""
    root = _committed(tmp_path, _kit_record())
    assert kit_label_problems([_kit_row()], root) == []
    typed = _kit_row("H-A-PCBX-STACK", f"confirmed (archive {KIT_ARCHIVE}); typed value (form)")
    assert kit_label_problems([_kit_row(), typed], root) == []


def test_kit_label_refusals(tmp_path: Path) -> None:
    """A row that the run did not pass, a result text without the archive digest or without ``form``."""
    root = _committed(tmp_path, _kit_record())
    for row, text in (
        (_kit_row("H-A-KIT-COMPILE"), "no passing verdict"),
        (_kit_row("H-A-KIT-DRC"), "no passing verdict"),
        (_kit_row(result="confirmed"), "archive digest"),
        (_kit_row("H-A-PCBX-STACK"), "'form'"),
    ):
        problems = kit_label_problems([row], root)
        assert len(problems) == 1 and text in problems[0], problems


def test_kit_label_of_a_synthetic_record(tmp_path: Path) -> None:
    """A record that says synthetic is not a record: the loader refuses the folder."""
    from fenolite.core.errors import FormatError

    root = _committed(tmp_path, _kit_record(synthetic=True))
    with pytest.raises(FormatError, match="synthetic"):
        kit_label_problems([_kit_row()], root)


def test_kit_label_of_a_stale_run(tmp_path: Path) -> None:
    """A run whose sample has other bytes than the kit the tree builds is stale for the rows of that
    sample, and only for them."""
    record = _kit_record()
    samples = {**record["samples"], "board6": "0" * 64}  # type: ignore[dict-item]
    steps = [
        {**step, "source": "0" * 64} if step["id"].startswith("K5.") else step
        for step in record["steps"]  # type: ignore[union-attr]
    ]
    root = _committed(tmp_path, {**record, "samples": samples, "steps": steps})
    typed = _kit_row("H-A-PCBX-STACK", f"confirmed (archive {KIT_ARCHIVE}); typed value (form)")
    flat_only = _row("H-A-SCHDOT-STRINGS", level=KIT_LABEL)
    problems = kit_label_problems([typed, flat_only], root)
    assert any(p.startswith("H-A-PCBX-STACK: its kit run is stale") for p in problems)
    assert not any(p.startswith("H-A-SCHDOT-STRINGS: its kit run is stale") for p in problems)


def test_rows_without_a_kit_label_need_no_kit(tmp_path: Path) -> None:
    assert kit_label_problems([_row("H-K-UNIT")], tmp_path) == []
