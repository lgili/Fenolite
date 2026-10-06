# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.2 release record says only what exists (capability release-gate, "Release record of v0.2" and
"Version 0.2.0"; change c0093). The rules are those of ``test_release_record.py`` for v0.1, with two
acceptance tables, the table of the later milestone that ships in the package, and the job column held to
``ci.yml``."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fenolite

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.2.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RESULTS = ("met", "met with a recorded limit", "not met", "pending")
HEADER = "| item | statement | proof | job | result |"
RELEASED = "0.2.0"
TABLES = {
    "Acceptance of v0.2a": ("v0.2a", ("1", "2", "3", "4", "5")),
    "Acceptance of v0.2b": ("v0.2b", ("1", "2", "3")),
    "Also in this package": ("v0.3", ()),
}
"""Section title: the milestone its rows belong to, and the numbered items that each need a row."""
FIXED_LIMITS = (
    ("v0.2a", "3", "RT2", ("H-K-ERC-REPEAT-2", "H-K-ERC-RT2-2", "kinds of violations", "another pin")),
    ("v0.2b", "1", "Update PCB from Schematic", ("H-K-SCH-UPDATE", "`INFERRED`", "one manual run")),
)
"""Milestone, item, the words that find the row, and what its limit must say: such a row never says
``met``."""
CHANGE_ID = re.compile(r"c\d{4}")
MILESTONES = {"v0.2a": (60, 68), "v0.2b": (69, 74), "v0.3": (39, 47)}
"""The change numbers of each milestone whose state the roadmap gives."""


def section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def rows(text: str, title: str) -> list[dict[str, str]]:
    """The rows of the table of one section."""
    lines = section(text, title).splitlines()
    assert HEADER in lines, f"the table of '## {title}' is missing"
    found: list[dict[str, str]] = []
    for line in lines[lines.index(HEADER) + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 5, line
        found.append(dict(zip(("item", "statement", "proof", "job", "result"), cells, strict=True)))
    return found


def jobs(workflow: str) -> set[str]:
    """The job ids of a workflow file, read textually: the dev extra has no YAML parser."""
    body = workflow.split("\njobs:\n", 1)[1] if "\njobs:\n" in workflow else ""
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", body, re.MULTILINE))


def proof_problem(proof: str) -> str:
    """Why ``proof`` names nothing that exists; empty when it does."""
    path, _, name = proof.partition("::")
    if not path.startswith("tests/"):
        return "not a path under tests/"
    file = ROOT / path
    if not file.is_file():
        return f"{path} does not exist"
    if name:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if name not in names:
            return f"{path} has no function {name}"
    return ""


def label(milestone: str, item: str) -> str:
    """How an entry names a row: ``v0.2a item 3`` for a numbered item, the change id for the others."""
    return item if CHANGE_ID.fullmatch(item) and milestone == "v0.3" else f"{milestone} item {item}"


def entries(text: str, title: str, name: str) -> str:
    """The list entries of ``## <title>`` that name ``name`` in their bold head."""
    found = [e for e in section(text, title).split("\n- ") if re.match(rf"\*\*{re.escape(name)}[.,]", e)]
    return "\n".join(found)


def record_problems(text: str, *, workflow: str) -> list[str]:
    """Everything the guard refuses in the record."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    pending: list[str] = []
    for title, (milestone, needed) in TABLES.items():
        table = rows(text, title)
        for row in table:
            name = label(milestone, row["item"])
            where = f"{name} ({row['statement'][:40]})"
            if row["item"] not in needed and not CHANGE_ID.fullmatch(row["item"]):
                problems.append(f"{where}: the item is neither a number of the acceptance nor a change id")
            why = proof_problem(row["proof"])
            if why:
                problems.append(f"{where}: proof {why}")
            named = [job.strip() for job in row["job"].split(",")]
            problems.extend(f"{where}: no job {job!r} in ci.yml" for job in named if job not in known_jobs)
            result = row["result"]
            if result not in RESULTS:
                problems.append(f"{where}: result {result!r}")
            if result == "met with a recorded limit" and not entries(text, "Recorded limits", name):
                problems.append(f"{where}: no entry under '## Recorded limits'")
            if result == "pending":
                pending.append(name)
            if result in ("pending", "not met") and not entries(text, "Open rows", name):
                problems.append(f"{where}: a row that is {result} needs an entry under '## Open rows'")
        missing = sorted(set(needed) - {row["item"] for row in table})
        problems.extend(f"{milestone} item {item}: no row" for item in missing)

    for milestone, item, words, must in FIXED_LIMITS:
        name = label(milestone, item)
        limit = entries(text, "Recorded limits", name)
        hit = [row for row in rows(text, f"Acceptance of {milestone}") if words in row["statement"]]
        if not hit:
            problems.append(f"{name}: no row names {words!r}")
        problems.extend(f"{name}: the row for {words!r} says 'met'" for row in hit if row["result"] == "met")
        problems.extend(f"{name}: the limit lacks {word!r}" for word in must if word not in limit)

    limits = section(text, "Recorded limits")
    for words in (
        "blink_official",
        "tests/libs/test_build_official.py",
        "no CI job",
        "pin_not_connected",
        "inside KiCad's report",
        "public gate only",
        "private gate was not run",
    ):
        if words not in limits:
            problems.append(f"limits: {words!r} is missing")
    also = section(text, "Also in this package")
    if "does not claim the acceptance" not in also:
        problems.append("also in this package: the words 'does not claim the acceptance' are missing")
    if "share one designator" not in section(text, "Open rows"):
        problems.append("open rows: the repeated-sheet defect lacks 'share one designator'")
    if not [r for r in rows(text, "Also in this package") if r["result"] == "not met"]:
        problems.append("also in this package: the repeated-sheet defect must be a row that is 'not met'")
    runs = section(text, "Runs and versions")
    if not re.search(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+", runs):
        problems.append("runs: no CI run is linked")
    for words in ("9.0.9", "10.0.6", "release candidate"):
        if words not in runs:
            problems.append(f"runs: {words!r} is missing")
    build = section(text, "Release build")
    for words in ("git worktree add", "never from the working tree"):
        if words not in build:
            problems.append(f"release build: the section lacks {words!r}")
    steps = section(text, "Maintainer's steps")
    for words in ("verdict", "`dev` to `main`", "v0.2.0", "clean checkout", "Publish"):
        if words not in steps:
            problems.append(f"maintainer's steps: {words!r} is missing")
    if not section(text, "Deferred after v0.2").strip():
        problems.append("deferred: the section is missing")
    verdict = section(text, "Verdict").strip()
    if not verdict:
        problems.append("verdict: the section is missing")
    elif pending and verdict != "pending":
        problems.append(f"verdict: written while {', '.join(pending)} is pending")
    return problems


def history_problems(text: str, *, version: str) -> list[str]:
    """Why the residue history page does not allow ``version``."""
    row = next((line for line in text.splitlines() if line.startswith("|") and "| v0.2.0 |" in line), "")
    if not row:
        return [f"{HISTORY.name}: no v0.2.0 row"] if version == RELEASED else []
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if len(cells) != 7:
        return [f"{HISTORY.name}: the v0.2.0 row needs 7 cells"]
    problems: list[str] = []
    if cells[5] != "not run":
        problems.append(f"{HISTORY.name}: the private gate column of v0.2.0 says {cells[5]!r}, not 'not run'")
    if cells[6] != "0":
        problems.append(f"{HISTORY.name}: the v0.2.0 row reports {cells[6]} hit(s)")
    return problems


def changelog_problems(text: str, *, version: str) -> list[str]:
    """A ``[0.2.0]`` section that is missing at that version, repeats a heading, names a private name or
    keeps more than one entry about archived specs."""
    headings = re.findall(r"^## \[([^\]]+)\]", text, re.MULTILINE)
    released = re.search(
        rf"^## \[{re.escape(RELEASED)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    if not released:
        return [f"no [{RELEASED}] section at version {RELEASED}"] if version == RELEASED else []
    problems: list[str] = []
    if headings[:3] != ["Unreleased", RELEASED, "0.1.0"]:
        problems.append(f"the sections start {headings[:3]}, not Unreleased, {RELEASED}, 0.1.0")
    body = released.group(1)
    names = re.findall(r"^### (.+)$", body, re.MULTILINE)
    problems.extend(
        f"[{RELEASED}]: the heading '### {h}' appears twice" for h in sorted(set(names)) if names.count(h) > 1
    )
    private = sorted(set(re.findall(r"`(_[A-Za-z0-9_.]+)", body)))
    problems.extend(f"[{RELEASED}]: an entry names {name}" for name in private)
    archived = [line for line in body.splitlines() if line.startswith("- ") and "Archived" in line]
    if len(archived) > 1:
        problems.append(f"[{RELEASED}]: {len(archived)} entries about archived specs; fold them into one")
    loose = [line for line in body.split("###", 1)[0].splitlines() if line.startswith("- ")]
    if loose:
        problems.append(f"[{RELEASED}]: {len(loose)} entries stand before the first '###' heading")
    return problems


def roadmap_problems(text: str, open_changes: set[str]) -> list[str]:
    """A milestone row of v0.2a, v0.2b or v0.3 that says ``proposed`` or hides a change that is not
    archived, or a roadmap that does not name the release change."""
    problems: list[str] = []
    table = section(text, "Milestones")
    for milestone, (first, last) in MILESTONES.items():
        row = next((line for line in table.splitlines() if f"| {milestone} |" in line), "")
        state = row.strip().strip("|").split("|")[-1] if row else ""
        if not row:
            problems.append(f"roadmap: no milestone row for {milestone}")
        if "proposed" in state:
            problems.append(f"roadmap: the row of {milestone} still says 'proposed'")
        ids = {f"c{number:04d}" for number in range(first, last + 1)}
        hidden = sorted(change for change in ids & open_changes if change not in state)
        problems.extend(f"roadmap: the row of {milestone} does not name {change}" for change in hidden)
    if "c0093" not in text:
        problems.append("roadmap: the release change c0093 is not named")
    return problems


def open_changes() -> set[str]:
    """The ids of the changes that are not archived."""
    folder = ROOT / "openspec" / "changes"
    return {path.name[:5] for path in folder.iterdir() if path.is_dir() and CHANGE_ID.match(path.name)}


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def check(text: str) -> list[str]:
    return record_problems(text, workflow=WORKFLOW.read_text(encoding="utf-8"))


def with_result(text: str, start: str, result: str) -> str:
    """``text`` with the result of the first table row that starts with ``start`` replaced."""
    line = next(row for row in text.splitlines() if row.startswith(start))
    return text.replace(line, line.rsplit("|", 2)[0] + f"| {result} |", 1)


def test_record_is_consistent() -> None:
    """Scenarios "Every item present" and "Limits are named"."""
    assert check(record()) == []


def test_missing_proof_is_named() -> None:
    """Scenario "Missing proof"."""
    text = record().replace("tests/unit/cli/test_diff_cmd.py", "tests/unit/cli/test_missing.py", 1)
    assert any("test_missing.py does not exist" in p for p in check(text))
    text = record().replace("::test_one_footprint_moved", "::test_gone", 1)
    assert any("has no function test_gone" in p for p in check(text))


def test_unknown_job_is_named() -> None:
    """Scenario "Unknown job"."""
    text = record().replace(
        "| routing | met with a recorded limit |", "| kicad-11 | met with a recorded limit |", 1
    )
    assert any("no job 'kicad-11' in ci.yml" in p for p in check(text))
    assert jobs(WORKFLOW.read_text(encoding="utf-8")) >= {
        "unit",
        "wheel",
        "dco",
        "kicad-9",
        "kicad-10",
        "routing",
    }


def test_results_are_the_four_words() -> None:
    """Scenario "Another word"."""
    text = with_result(record(), "| 4 | `diff`", "mostly met")
    assert any("result 'mostly met'" in p for p in check(text))


def test_missing_item_is_named() -> None:
    """Scenario "Missing item"."""
    kept = [line for line in record().splitlines() if not line.startswith("| 2 | Two overlapping")]
    text = "\n".join(line for line in kept if not line.startswith("| 2 | Also for a new rule kind"))
    assert "v0.2b item 2: no row" in check(text)


def test_limit_entry_is_required() -> None:
    """Scenario "Limit without an entry"."""
    text = record().replace("- **v0.2a item 4, `fmt`.**", "- **The printer.**")
    assert any(p.startswith("v0.2a item 4") and "Recorded limits" in p for p in check(text))


@pytest.mark.parametrize(
    ("start", "named"),
    [("| 3 | RT2 through", "v0.2a item 3"), ("| 1 | Also after the stand-in", "v0.2b item 1")],
)
def test_fixed_limit_rows_cannot_say_met(start: str, named: str) -> None:
    """Scenario "A row with a fixed limit cannot say met"."""
    assert any(p.startswith(named) and "says 'met'" in p for p in check(with_result(record(), start, "met")))


def test_fixed_limits_are_stated() -> None:
    """Scenario "Limits are named"."""
    text = record()
    assert "v0.2a item 3: the limit lacks 'another pin'" in check(
        text.replace("another pin", "another place")
    )
    assert any("no CI job" in p for p in check(text.replace("no CI job installs", "CI installs")))
    assert "v0.2b item 1: the limit lacks 'one manual run'" in check(text.replace("one manual run", "a run"))


def test_pending_row_needs_its_entry_and_blocks_the_verdict() -> None:
    """Scenarios "Open row without a reason" and "Verdict over a pending row"."""
    text = record()
    assert "| pending |" in text, "the record holds a pending row while c0070 is open"
    without = text.replace("- **v0.2b item c0070.**", "- **The sheets.**")
    assert any("Open rows" in p for p in check(without))
    decided = re.sub(r"## Verdict\n\n.*\Z", "## Verdict\n\nReleased as v0.2.0.\n", text, flags=re.DOTALL)
    assert any(p.startswith("verdict: written while v0.2b item c0070") for p in check(decided))
    closed = with_result(decided, "| c0070 | One schematic sheet", "met")
    assert not [p for p in check(closed) if p.startswith("verdict")]


def test_later_milestone_is_not_claimed() -> None:
    """Scenario "The later milestone is not claimed"."""
    text = record()
    assert any("does not claim" in p for p in check(text.replace("does not claim the acceptance", "meets")))
    met = with_result(text, "| c0043 | The components of a repeated sheet", "met")
    assert any("repeated-sheet defect" in p for p in check(met))
    unexplained = with_result(text, "| 4 | `diff`", "not met")
    assert any(p.startswith("v0.2a item 4") and "Open rows" in p for p in check(unexplained))


def test_build_rule_and_steps_are_stated() -> None:
    """Scenario "Maintainer's steps"."""
    text = record()
    assert any(p.startswith("release build") for p in check(text.replace("never from the working tree", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("`dev` to `main`", "x")))


def test_history_row() -> None:
    """Scenario "History row required"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    only_old = "\n".join(line for line in text.splitlines() if "| v0.2.0 |" not in line)
    assert history_problems(only_old, version=RELEASED) == [f"{HISTORY.name}: no v0.2.0 row"]
    claimed = only_old + "\n| 2026-10-06 | v0.2.0 | root .. abc | all | 5 | on | 0 |\n"
    assert any("private gate column" in p for p in history_problems(claimed, version=RELEASED))


def test_changelog_section_is_clean() -> None:
    """Scenarios "Versions agree" and "Changelog section is clean"."""
    assert changelog_problems(CHANGELOG.read_text(encoding="utf-8"), version=fenolite.__version__) == []
    assert changelog_problems("## [Unreleased]\n", version=RELEASED) == [
        f"no [{RELEASED}] section at version {RELEASED}"
    ]
    bad = (
        "## [Unreleased]\n\n## [0.2.0] - pending\n\n- loose\n\n### Added\n\n- Archived a\n- Archived b\n\n"
        "### Added\n\n- c with `_private.name`\n\n## [0.1.0] - 2026-10-05\n"
    )
    problems = changelog_problems(bad, version=RELEASED)
    for words in ("appears twice", "_private.name", "fold them into one", "before the first"):
        assert any(words in p for p in problems), words


def test_versions_agree() -> None:
    """Scenario "Versions agree": the package, its alias and the alias pin."""
    alias = (ROOT / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    version = fenolite.__version__
    assert f'version = "{version}"' in alias and f"fenolite=={version}" in alias


def test_roadmap_states() -> None:
    """Scenario "Stale roadmap state rejected"."""
    text = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
    assert roadmap_problems(text, open_changes()) == []
    row = next(line for line in section(text, "Milestones").splitlines() if "| v0.2a |" in line)
    stale = text.replace(row, row.rsplit("|", 2)[0] + "| proposed on 2026-10-04 |")
    assert "roadmap: the row of v0.2a still says 'proposed'" in roadmap_problems(stale, set())
    assert "roadmap: the row of v0.3 does not name c0040" in roadmap_problems(text, {"c0040"})
