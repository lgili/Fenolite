# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.2 release record says only what exists (capability release-gate, "Release record of v0.2" and
"Version 0.2.0"; change c0093). The rules are those of ``test_release_record.py`` for v0.1, with two
acceptance tables, the table of the later milestone that ships in the package, and the job column held to
``ci.yml``. The patch releases of the series are held to "Patch releases of 0.2" (change c0133): the guard
reads their list from the record, so it holds at any later version of the package."""

from __future__ import annotations

import ast
import re
from collections.abc import Sequence
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
SERIES = "0.2"
"""The series of ``RELEASED``: a version ``0.2.N`` with N from 1 is one of its patch releases."""
RUN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+")
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


def table(body: str) -> list[dict[str, str]]:
    """The rows of the first table of ``body`` that has the header of the record; none without it."""
    lines = body.splitlines()
    found: list[dict[str, str]] = []
    for line in lines[lines.index(HEADER) + 2 :] if HEADER in lines else []:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 5, line
        found.append(dict(zip(("item", "statement", "proof", "job", "result"), cells, strict=True)))
    return found


def rows(text: str, title: str) -> list[dict[str, str]]:
    """The rows of the table of one section."""
    assert HEADER in section(text, title).splitlines(), f"the table of '## {title}' is missing"
    return table(section(text, title))


def patch_number(version: str) -> int:
    """The N of ``0.2.N``; 0 for ``0.2.0`` and for a version of another series."""
    match = re.fullmatch(rf"{re.escape(SERIES)}\.(\d+)", version)
    return int(match.group(1)) if match else 0


def patches(text: str) -> list[str]:
    """The patch releases the record names, in the order of their subsections."""
    return re.findall(r"^### (\d+\.\d+\.\d+)$", section(text, "Patch releases"), re.MULTILINE)


def subsection(text: str, name: str) -> str:
    """The body of ``### <name>`` under ``## Patch releases``."""
    body = section(text, "Patch releases")
    match = re.search(rf"^### {re.escape(name)}\n(.*?)(?=^### |\Z)", body, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


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


def row_problems(text: str, row: dict[str, str], name: str, known_jobs: set[str]) -> list[str]:
    """What the guard refuses in one row, whose entries under the two lists are named ``name``."""
    where = f"{name} ({row['statement'][:40]})"
    problems: list[str] = []
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
    if result in ("pending", "not met") and not entries(text, "Open rows", name):
        problems.append(f"{where}: a row that is {result} needs an entry under '## Open rows'")
    return problems


def record_problems(text: str, *, workflow: str) -> list[str]:
    """Everything the guard refuses in the record of ``0.2.0``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    pending: list[str] = []
    for title, (milestone, needed) in TABLES.items():
        found = rows(text, title)
        for row in found:
            name = label(milestone, row["item"])
            if row["item"] not in needed and not CHANGE_ID.fullmatch(row["item"]):
                where = f"{name} ({row['statement'][:40]})"
                problems.append(f"{where}: the item is neither a number of the acceptance nor a change id")
            problems.extend(row_problems(text, row, name, known_jobs))
            if row["result"] == "pending":
                pending.append(name)
        missing = sorted(set(needed) - {row["item"] for row in found})
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
    if not RUN.search(runs):
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


def patch_problems(text: str, *, workflow: str, version: str) -> list[str]:
    """Everything the guard refuses under ``## Patch releases`` when the package is at ``version``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    named = patches(text)
    wanted = [f"{SERIES}.{number}" for number in range(1, len(named) + 1)]
    if named != wanted:
        problems.append(f"patch releases: the subsections are {named}, not {wanted}")
    problems.extend(
        f"patch releases: no subsection for {SERIES}.{number}"
        for number in range(1, patch_number(version) + 1)
        if f"{SERIES}.{number}" not in named
    )
    accepted = {row["item"] for title in TABLES for row in rows(text, title)}
    for name in named:
        body = subsection(text, name)
        found = table(body)
        if not found:
            problems.append(f"{name}: the subsection has no table with a row")
        pending: list[str] = []
        for row in found:
            item = row["item"]
            if not CHANGE_ID.fullmatch(item):
                problems.append(f"{name} ({row['statement'][:40]}): the item is not a change id")
            elif item in accepted:
                problems.append(f"{name}: {item} is an item of the tables of {RELEASED}")
            problems.extend(f"{name}, {problem}" for problem in row_problems(text, row, item, known_jobs))
            if row["result"] == "pending":
                pending.append(item)
        before = f"`v{SERIES}.{patch_number(name) - 1}`"
        for words in ("cut from the tag", before, "`main` into `dev`"):
            if words not in body:
                problems.append(f"{name}: {words!r} is missing")
        verdict = re.search(rf"^\*\*Verdict of {re.escape(name)}\.\*\*(.*)$", body, re.MULTILINE)
        if not verdict:
            problems.append(f"{name}: no line '**Verdict of {name}.**'")
        elif verdict.group(1).strip() != "pending":
            if pending:
                problems.append(f"{name}: verdict written while {', '.join(pending)} is pending")
            if not RUN.search(body):
                problems.append(f"{name}: a verdict needs a linked CI run in the subsection")
    return problems


def history_problems(text: str, *, version: str, patches: Sequence[str] = ()) -> list[str]:
    """Why the residue history page does not allow ``version``, or lacks a patch release of the record."""
    problems: list[str] = []
    for release in (RELEASED, *patches):
        tag = f"v{release}"
        row = next((line for line in text.splitlines() if line.startswith("|") and f"| {tag} |" in line), "")
        if not row:
            if release != RELEASED or version == RELEASED:
                problems.append(f"{HISTORY.name}: no {tag} row")
            continue
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if len(cells) != 7:
            problems.append(f"{HISTORY.name}: the {tag} row needs 7 cells")
            continue
        if cells[5] != "not run":
            problems.append(
                f"{HISTORY.name}: the private gate column of {tag} says {cells[5]!r}, not 'not run'"
            )
        if cells[6] != "0":
            problems.append(f"{HISTORY.name}: the {tag} row reports {cells[6]} hit(s)")
    return problems


def changelog_problems(text: str, *, version: str, patches: Sequence[str] = ()) -> list[str]:
    """A section of the series that is missing at its version or out of its place, repeats a heading,
    names a private name or keeps more than one entry about archived specs. ``patches`` are the patch
    releases the record names, the oldest first."""
    headings = re.findall(r"^## \[([^\]]+)\]", text, re.MULTILINE)
    series = [*reversed(patches), RELEASED]
    in_series = version == RELEASED or patch_number(version) > 0
    if RELEASED not in headings:
        return [f"no [{RELEASED}] section at version {version}"] if in_series else []
    problems: list[str] = []
    first = min(headings.index(name) for name in series if name in headings)
    wanted = [*series, "0.1.0"]
    found = headings[first : first + len(wanted)]
    if found != wanted:
        problems.append(f"the sections of the series are {found}, not {wanted}")
    if in_series and headings[:first] != ["Unreleased"]:
        problems.append(f"the sections start {headings[:first]}, not Unreleased alone, before [{series[0]}]")
    for name in series:
        released = re.search(
            rf"^## \[{re.escape(name)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL
        )
        if not released:
            continue
        body = released.group(1)
        names = re.findall(r"^### (.+)$", body, re.MULTILINE)
        problems.extend(
            f"[{name}]: the heading '### {h}' appears twice" for h in sorted(set(names)) if names.count(h) > 1
        )
        private = sorted(set(re.findall(r"`(_[A-Za-z0-9_.]+)", body)))
        problems.extend(f"[{name}]: an entry names {word}" for word in private)
        archived = [line for line in body.splitlines() if line.startswith("- ") and "Archived" in line]
        if len(archived) > 1:
            problems.append(f"[{name}]: {len(archived)} entries about archived specs; fold them into one")
        loose = [line for line in body.split("###", 1)[0].splitlines() if line.startswith("- ")]
        if loose:
            problems.append(f"[{name}]: {len(loose)} entries stand before the first '###' heading")
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


def patch_check(text: str, *, version: str = "") -> list[str]:
    """The problems of the patch releases of ``text``, at the package's version unless one is given."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    return patch_problems(text, workflow=workflow, version=version or fenolite.__version__)


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
    without = with_result(record(), "| c0070 | One schematic sheet", "pending")
    assert any("Open rows" in p for p in check(without)), "a pending row without its entry is refused"
    text = without.replace("## Open rows\n", "## Open rows\n\n- **v0.2b item c0070.** Open.\n", 1)
    assert not any("Open rows" in p and "c0070" in p for p in check(text))
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
    """Scenarios "History row required" and "History row of a patch release required"."""
    text = HISTORY.read_text(encoding="utf-8")
    named = patches(record())
    assert history_problems(text, version=fenolite.__version__, patches=named) == []
    for name in named:
        without = "\n".join(line for line in text.splitlines() if f"| v{name} |" not in line)
        assert history_problems(without, version=fenolite.__version__, patches=named) == [
            f"{HISTORY.name}: no v{name} row"
        ]
        claimed = without + f"\n| 2026-10-07 | v{name} | root .. abc | all | 5 | on | 0 |\n"
        assert any("private gate column" in p for p in history_problems(claimed, version=name, patches=named))
    only_old = "\n".join(line for line in text.splitlines() if "| v0.2.0 |" not in line)
    assert history_problems(only_old, version=RELEASED) == [f"{HISTORY.name}: no v0.2.0 row"]
    claimed = only_old + "\n| 2026-10-06 | v0.2.0 | root .. abc | all | 5 | on | 0 |\n"
    assert any("private gate column" in p for p in history_problems(claimed, version=RELEASED))


def test_changelog_section_is_clean() -> None:
    """Scenarios "Versions agree" and "Changelog section is clean"."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert changelog_problems(text, version=fenolite.__version__, patches=patches(record())) == []
    for version in (RELEASED, f"{SERIES}.1"):
        assert changelog_problems("## [Unreleased]\n", version=version) == [
            f"no [{RELEASED}] section at version {version}"
        ]
    assert changelog_problems("## [Unreleased]\n", version="0.3.0") == []
    bad = (
        "## [Unreleased]\n\n## [0.2.0] - pending\n\n- loose\n\n### Added\n\n- Archived a\n- Archived b\n\n"
        "### Added\n\n- c with `_private.name`\n\n## [0.1.0] - 2026-10-05\n"
    )
    problems = changelog_problems(bad, version=RELEASED)
    for words in ("appears twice", "_private.name", "fold them into one", "before the first"):
        assert any(words in p for p in problems), words


def test_patch_sections_stand_in_order() -> None:
    """Scenario "Patch sections out of order"."""
    older = "## [0.2.0] - d\n\n## [0.1.0] - d\n\n## [0.0.1.dev0] - d\n"
    good = "## [Unreleased]\n\n## [0.2.1] - pending the tag\n\n" + older
    assert changelog_problems(good, version="0.2.1", patches=["0.2.1"]) == []
    assert changelog_problems(good, version="0.3.0", patches=["0.2.1"]) == []
    swapped = "## [Unreleased]\n\n## [0.2.0] - d\n\n## [0.2.1] - d\n\n## [0.1.0] - d\n"
    problems = changelog_problems(swapped, version="0.2.1", patches=["0.2.1"])
    assert any("['0.2.0', '0.2.1', '0.1.0']" in p for p in problems)
    absent = "## [Unreleased]\n\n## [0.2.0] - d\n\n## [0.1.0] - d\n"
    problems = changelog_problems(absent, version="0.2.1", patches=["0.2.1"])
    assert any("are ['0.2.0', '0.1.0']" in p for p in problems)
    unnamed = changelog_problems(good, version="0.2.1")
    assert unnamed == ["the sections start ['Unreleased', '0.2.1'], not Unreleased alone, before [0.2.0]"]
    later = "## [Unreleased]\n\n## [0.3.0] - d\n\n## [0.2.1] - d\n\n## [0.2.0] - d\n\n## [0.1.0] - d\n"
    assert changelog_problems(later, version="0.3.0", patches=["0.2.1"]) == []
    problems = changelog_problems(later, version="0.2.1", patches=["0.2.1"])
    assert any("not Unreleased alone" in p for p in problems)
    dirty = good.replace("pending the tag\n", "pending the tag\n\n- loose\n\n### Fixed\n\n### Fixed\n")
    problems = changelog_problems(dirty, version="0.2.1", patches=["0.2.1"])
    assert any(p.startswith("[0.2.1]") and "appears twice" in p for p in problems)
    assert any(p.startswith("[0.2.1]") and "before the first" in p for p in problems)


def test_patch_releases_are_recorded() -> None:
    """Scenarios "Patch release recorded" and "Version without a subsection"."""
    text = record()
    named = patches(text)
    assert patch_check(text) == []
    assert named == [f"{SERIES}.{number}" for number in range(1, len(named) + 1)]
    assert patch_number(fenolite.__version__) <= len(named)
    later = f"{SERIES}.{len(named) + 1}"
    assert patch_check(text, version=later) == [f"patch releases: no subsection for {later}"]
    assert patch_check(text, version="0.3.0") == []
    skipped = text.replace("### 0.2.1\n", "### 0.2.2\n", 1)
    assert any("the subsections are" in p for p in patch_check(skipped, version=RELEASED))


def test_patch_rows_are_held_to_the_rules() -> None:
    """Scenarios "Patch row with a missing proof" and "Patch row taken from the acceptance"."""
    text = record()
    body = subsection(text, "0.2.1")
    row = next(line for line in body.splitlines() if line.startswith("| c"))
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    item, proof = cells[0], cells[2]

    def with_row(new: str) -> str:
        return text.replace(body, body.replace(row, new, 1), 1)

    missing = with_row(row.replace(proof, "tests/unit/lens/test_missing.py", 1))
    assert any(
        p.startswith("0.2.1, ") and "test_missing.py does not exist" in p for p in patch_check(missing)
    )
    taken = with_row(row.replace(f"| {item} |", "| c0070 |", 1))
    assert f"0.2.1: c0070 is an item of the tables of {RELEASED}" in patch_check(taken)
    numbered = with_row(row.replace(f"| {item} |", "| 1 |", 1))
    assert any("the item is not a change id" in p for p in patch_check(numbered))
    job = with_row(row.rsplit("|", 3)[0] + "| kicad-11 | met |")
    assert any("no job 'kicad-11' in ci.yml" in p for p in patch_check(job))
    assert any("no table" in p for p in patch_check(text.replace(body, body.replace(HEADER, "", 1), 1)))
    for words in ("cut from the tag", "`v0.2.0`", "`main` into `dev`"):
        assert f"0.2.1: {words!r} is missing" in patch_check(text.replace(body, body.replace(words, "x"), 1))


def test_patch_verdict() -> None:
    """Scenario "Verdict of a patch release"."""
    text = record()
    body = subsection(text, "0.2.1")
    row = next(line for line in body.splitlines() if line.startswith("| c"))
    item = row.strip().strip("|").split("|")[0].strip()
    line = next(found for found in body.splitlines() if found.startswith("**Verdict of 0.2.1.**"))
    open_row = row.rsplit("|", 2)[0] + "| pending |"
    entry = f"## Open rows\n\n- **{item}, a fix.** Open.\n"
    waits, decides = "**Verdict of 0.2.1.** pending", "**Verdict of 0.2.1.** Released as v0.2.1."
    run = "CI run: https://github.com/lgili/Fenolite/actions/runs/1"

    def variant(verdict: str, *, pending: bool) -> str:
        """The record without a linked run in the subsection, with that verdict and that first row."""
        changed = RUN.sub("the run", body).replace(line, verdict, 1)
        changed = changed.replace(row, open_row, 1) if pending else changed
        return text.replace(body, changed, 1).replace("## Open rows\n", entry, 1)

    assert patch_check(variant(waits, pending=True)) == []
    assert f"0.2.1: verdict written while {item} is pending" in patch_check(variant(decides, pending=True))
    assert patch_check(variant(decides, pending=False)) == [
        "0.2.1: a verdict needs a linked CI run in the subsection"
    ]
    assert patch_check(variant(f"{run}\n\n{decides}", pending=False)) == []
    assert any("no line" in p for p in patch_check(text.replace(body, body.replace(line, "", 1), 1)))


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
