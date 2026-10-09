# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.4 release record says only what exists (capability release-gate, "Release record of v0.4",
"Sections of the record of v0.4", "Version 0.4.0" and "History row and roadmap of 0.4.0"; change c0154).
v0.4 has no acceptance block: the record has one row per change, and this guard holds each row to the
change's own task list, so that no open task goes unnamed and no row ships with a task left open."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fenolite

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.4.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHANGES = ROOT / "openspec" / "changes"
RELEASED = "0.4.0"
PREVIOUS = "0.3.0"
RELEASE_CHANGE = "c0154"
HEADER = "| change | what ships | proof | job | open tasks | result |"
FIELDS = ("change", "ships", "proof", "job", "open", "result")
SHIPS, DEFERRED, PENDING = "ships", "ships with deferred tasks", "pending"
RESULTS = (SHIPS, DEFERRED, PENDING)
PLACEHOLDER = "TODO(coordinator)"
V04_CHANGES = (
    *(f"c{n:04d}" for n in range(77, 82)),
    *(f"c{n:04d}" for n in range(96, 121)),
    "c0137",
    "c0140",
    "c0141",
    "c0145",
    "c0152",
    "c0153",
)
"""The changes of v0.4: the three groups of the roadmap and the changes written on ``v04`` after 0.3.0."""
FOLLOW_UPS = (
    "c0110",
    "route.escape-skipped",
    "c0105",
    "c0108",
    "c0109",
    "c0112",
    "c0081",
    "c0091",
    "c0148",
    "X8",
    "Part V",
    "Part G",
    "R2",
    "agent_eval",
    ".cmd",
    "c0151",
)
"""What "Follow-ups found on 2026-10-08" must name."""
NOT_IN_RELEASE = ("c0151", "c0092")
RUN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+")
TASK = re.compile(r"^- \[( |x)\] (\d+\.\d+|[A-Z]\d+)\b", re.MULTILINE)


def section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def rows(text: str) -> list[dict[str, str]]:
    lines = section(text, "Verdict per change").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(HEADER)), None)
    if start is None:
        return []
    found: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        values = cells(line)
        assert len(values) == len(FIELDS), values
        found.append(dict(zip(FIELDS, values, strict=True)))
    return found


def jobs(workflow: str) -> set[str]:
    body = workflow.split("\njobs:\n", 1)[1] if "\njobs:\n" in workflow else ""
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", body, re.MULTILINE))


def proof_problem(proof: str) -> str:
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


def tasks_file(change: str) -> Path | None:
    """The task list of ``change``: its open folder, or its folder in the archive once it is archived."""
    found = sorted(CHANGES.glob(f"{change}-*/tasks.md")) or sorted(
        (CHANGES / "archive").glob(f"*-{change}-*/tasks.md")
    )
    return found[0] if found else None


def tasks(change: str) -> dict[str, bool]:
    """Task number to ticked, from the change's ``tasks.md``."""
    file = tasks_file(change)
    if file is None:
        return {}
    return {number: mark == "x" for mark, number in TASK.findall(file.read_text(encoding="utf-8"))}


def named(cell: str) -> list[str]:
    return [] if cell in ("—", "-", "") else [part.strip() for part in cell.split(",")]


def entry(text: str, title: str, change: str) -> bool:
    return any(e.startswith(f"**{change}.") for e in section(text, title).split("\n- "))


def row_problems(text: str, row: dict[str, str], known_jobs: set[str]) -> list[str]:
    change = row["change"]
    problems: list[str] = []
    why = proof_problem(row["proof"])
    if why:
        problems.append(f"{change}: proof {why}")
    problems.extend(
        f"{change}: no job {job!r} in ci.yml" for job in named(row["job"]) if job not in known_jobs
    )
    result = row["result"]
    if result not in RESULTS:
        problems.append(f"{change}: result {result!r}")
    listed = tasks(change)
    if not listed:
        problems.append(f"{change}: no tasks.md")
    given = named(row["open"])
    problems.extend(
        f"{change}: {number} is not a task of its tasks.md" for number in given if number not in listed
    )
    problems.extend(
        f"{change}: task {number} is open and not named"
        for number, ticked in listed.items()
        if not ticked and number not in given
    )
    if result == SHIPS and given:
        problems.append(f"{change}: a row that ships names open tasks")
    if result in (DEFERRED, PENDING) and not given:
        problems.append(f"{change}: a row that is {result} names no open task")
    if result == DEFERRED and not entry(text, "Deferred to the next release", change):
        problems.append(f"{change}: no entry under '## Deferred to the next release'")
    if result == PENDING and not entry(text, "Pending on the release branch", change):
        problems.append(f"{change}: no entry under '## Pending on the release branch'")
    return problems


def record_problems(text: str, *, workflow: str) -> list[str]:
    """Everything the guard refuses in the record of ``0.4.0``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    found = rows(text)
    if not found:
        return ["the table of '## Verdict per change' is missing"]
    changes = [row["change"] for row in found]
    problems.extend(f"{change}: no row" for change in V04_CHANGES if change not in changes)
    problems.extend(f"{change}: not a change of v0.4" for change in changes if change not in V04_CHANGES)
    problems.extend(
        f"{change}: more than one row" for change in sorted(set(changes)) if changes.count(change) > 1
    )
    for row in found:
        problems.extend(row_problems(text, row, known_jobs))
    follow = section(text, "Follow-ups found on 2026-10-08")
    problems.extend(f"follow-ups: {words!r} is missing" for words in FOLLOW_UPS if words not in follow)
    absent = section(text, f"Not in {RELEASED}")
    problems.extend(
        f"not in {RELEASED}: {words!r} is missing" for words in NOT_IN_RELEASE if words not in absent
    )
    if "experimental" not in section(text, "Altium write"):
        problems.append("altium write: the section does not say that the write stays experimental")
    limits = section(text, "Recorded limits")
    problems.extend(
        f"limits: {words!r} is missing"
        for words in ("public gate only", "private gate was not run")
        if words not in limits
    )
    runs = section(text, "Runs and versions")
    if not RUN.search(runs):
        problems.append("runs: no CI run is linked")
    problems.extend(
        f"runs: {words!r} is missing"
        for words in ("9.0.9", "10.0.6", "release candidate", "yardstick")
        if words not in runs
    )
    build = section(text, "Release build")
    problems.extend(
        f"release build: the section lacks {words!r}"
        for words in ("git worktree add", "never from the working tree", f"v{RELEASED}")
        if words not in build
    )
    steps = section(text, "Maintainer's steps")
    problems.extend(
        f"maintainer's steps: {words!r} is missing"
        for words in (
            "verdict",
            "`dev` to `main`",
            f"v{RELEASED}",
            "clean checkout",
            "Publish",
            "`main` into `dev`",
        )
        if words not in steps
    )
    for title in ("Archive order", "Deferred after v0.4"):
        if not section(text, title).strip():
            problems.append(f"{title.lower()}: the section is missing")
    verdict = section(text, "Verdict").strip()
    pending = [row["change"] for row in found if row["result"] == PENDING]
    if not verdict:
        problems.append("verdict: the section is missing")
    elif verdict != "pending":
        if pending:
            problems.append(f"verdict: written while {', '.join(pending)} is pending")
        if PLACEHOLDER in text:
            problems.append(f"verdict: written while a {PLACEHOLDER} placeholder stands")
    return problems


def history_problems(text: str, *, version: str) -> list[str]:
    row = next(
        (line for line in text.splitlines() if line.startswith("|") and f"| v{RELEASED} |" in line), ""
    )
    if not row:
        return [f"{HISTORY.name}: no v{RELEASED} row"] if version == RELEASED else []
    found = cells(row)
    if len(found) != 7:
        return [f"{HISTORY.name}: the v{RELEASED} row needs 7 cells"]
    problems = []
    if found[5] != "not run":
        problems.append(
            f"{HISTORY.name}: the private gate column of v{RELEASED} says {found[5]!r}, not 'not run'"
        )
    if found[6] != "0":
        problems.append(f"{HISTORY.name}: the v{RELEASED} row reports {found[6]} hit(s)")
    return problems


def changelog_problems(text: str, *, version: str) -> list[str]:
    """At ``0.4.0`` the headings start ``Unreleased``, ``0.4.0`` and ``0.3.0``; the ``[0.4.0]`` section is
    clean by the rules of ``[0.2.0]``."""
    headings = re.findall(r"^## \[([^\]]+)\]", text, re.MULTILINE)
    if RELEASED not in headings:
        return [f"no [{RELEASED}] section at version {version}"] if version == RELEASED else []
    problems: list[str] = []
    if version == RELEASED and headings[:3] != ["Unreleased", RELEASED, PREVIOUS]:
        problems.append(f"the sections start {headings[:3]}, not ['Unreleased', '{RELEASED}', '{PREVIOUS}']")
    unreleased = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    if version == RELEASED and unreleased and unreleased.group(1).strip():
        problems.append("[Unreleased] is not empty at the release")
    released = re.search(
        rf"^## \[{re.escape(RELEASED)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    body = released.group(1) if released else ""
    names = re.findall(r"^### (.+)$", body, re.MULTILINE)
    problems.extend(
        f"[{RELEASED}]: the heading '### {h}' appears twice" for h in sorted(set(names)) if names.count(h) > 1
    )
    problems.extend(
        f"[{RELEASED}]: an entry names {word}"
        for word in sorted(set(re.findall(r"`(_[A-Za-z0-9_.]+)", body)))
    )
    entries = [line for line in body.splitlines() if line.startswith("- ")]
    problems.extend(
        f"[{RELEASED}]: the entry {line[:60]!r} appears twice"
        for line in sorted(set(entries))
        if entries.count(line) > 1
    )
    loose = [line for line in body.split("###", 1)[0].splitlines() if line.startswith("- ")]
    if loose:
        problems.append(f"[{RELEASED}]: {len(loose)} entries stand before the first '###' heading")
    return problems


def roadmap_problems(text: str) -> list[str]:
    """The milestone row of v0.4 names the release and no longer says that its changes are not on `dev`."""
    problems: list[str] = []
    milestones = section(text, "Milestones")
    row = next((line for line in milestones.splitlines() if "| v0.4 |" in line), "")
    if not row:
        problems.append("roadmap: no milestone row for v0.4")
    else:
        state = cells(row)[-1]
        if RELEASED not in state:
            problems.append(f"roadmap: the row of v0.4 does not name {RELEASED}")
        if "not on `dev`" in state:
            problems.append("roadmap: the row of v0.4 still says 'not on `dev`'")
    if RELEASE_CHANGE not in text:
        problems.append(f"roadmap: the release change {RELEASE_CHANGE} is not named")
    return problems


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def check(text: str) -> list[str]:
    return record_problems(text, workflow=WORKFLOW.read_text(encoding="utf-8"))


def row_line(text: str, change: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(f"| {change} |"))


def with_cell(text: str, change: str, field: str, value: str) -> str:
    line = row_line(text, change)
    values = cells(line)
    values[FIELDS.index(field)] = value
    return text.replace(line, "| " + " | ".join(values) + " |", 1)


def with_verdict(text: str, verdict: str) -> str:
    return re.sub(r"## Verdict\n\n.*\Z", f"## Verdict\n\n{verdict}\n", text, flags=re.DOTALL)


def test_record_is_consistent() -> None:
    """Scenario "Every change present"."""
    assert check(record()) == []


def test_missing_change_proof_and_job_are_named() -> None:
    text = record()
    without = text.replace(row_line(text, "c0145") + "\n", "", 1)
    assert "c0145: no row" in check(without)
    gone = with_cell(text, "c0145", "proof", "tests/unit/backends/kicad/test_missing.py")
    assert any("test_missing.py does not exist" in p for p in check(gone))
    named_gone = with_cell(text, "c0109", "proof", "tests/routing/test_krt_gate.py::test_gone")
    assert any("has no function test_gone" in p for p in check(named_gone))
    assert "c0145: no job 'kicad-11' in ci.yml" in check(with_cell(text, "c0145", "job", "kicad-11"))


def test_open_task_must_be_named() -> None:
    """Scenario "An open task not named"."""
    text = with_cell(record(), "c0081", "open", "4.3")
    assert "c0081: task 4.2 is open and not named" in check(text)
    assert "c0081: 9.9 is not a task of its tasks.md" in check(
        with_cell(record(), "c0081", "open", "4.2, 4.3, 9.9")
    )


def test_results_need_their_entries() -> None:
    text = record()
    assert "c0081: a row that ships names open tasks" in check(with_cell(text, "c0081", "result", "ships"))
    assert "c0081: result 'mostly ships'" in check(with_cell(text, "c0081", "result", "mostly ships"))
    no_entry = text.replace("- **c0081.** Tasks 4.2", "- **The agent.** Tasks 4.2", 1)
    assert "c0081: no entry under '## Deferred to the next release'" in check(no_entry)
    pending = with_cell(text, "c0081", "result", "pending")
    assert "c0081: no entry under '## Pending on the release branch'" in check(pending)
    assert "c0077: a row that is pending names no open task" in check(
        with_cell(text, "c0077", "result", "pending")
    )


@pytest.mark.parametrize("words", FOLLOW_UPS)
def test_follow_ups_are_named(words: str) -> None:
    """Scenario "A follow-up missing"."""
    body = section(record(), "Follow-ups found on 2026-10-08")
    text = record().replace(body, body.replace(words, "x"), 1)
    assert f"follow-ups: {words!r} is missing" in check(text)


def test_verdict_over_pending_rows_and_placeholders() -> None:
    """Scenario "Verdict over a placeholder"."""
    text = record()
    assert not [p for p in check(text) if p.startswith("verdict")]
    decided = with_verdict(text, f"Released as v{RELEASED}.")
    problems = check(decided)
    if PLACEHOLDER in text:
        assert f"verdict: written while a {PLACEHOLDER} placeholder stands" in problems
    pending = with_verdict(with_cell(text, "c0153", "result", "pending"), f"Released as v{RELEASED}.")
    assert any(p.startswith("verdict: written while") and "c0153" in p for p in check(pending))
    clean = with_verdict(text.replace(PLACEHOLDER, "run"), f"Released as v{RELEASED}.")
    for change in [row["change"] for row in rows(clean) if row["result"] == PENDING]:
        clean = with_cell(clean, change, "result", DEFERRED)
    assert not [p for p in check(clean) if p.startswith("verdict")]


def test_steps_and_build_are_stated() -> None:
    text = record()
    assert any(p.startswith("release build") for p in check(text.replace("never from the working tree", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("`main` into `dev`", "x")))
    assert any(p.startswith("runs: 'yardstick'") for p in check(text.replace("yardstick", "x")))


def test_history_row() -> None:
    """Scenario "History row required"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    without = "\n".join(line for line in text.splitlines() if f"| v{RELEASED} |" not in line)
    assert history_problems(without, version=RELEASED) == [f"{HISTORY.name}: no v{RELEASED} row"]
    claimed = without + f"\n| 2026-10-08 | v{RELEASED} | root .. abc | all | 5 | on | 0 |\n"
    assert any("private gate column" in p for p in history_problems(claimed, version=RELEASED))


def test_changelog_section() -> None:
    """Scenario "Versions agree": the order of the sections and a clean ``[0.4.0]``."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert changelog_problems(text, version=fenolite.__version__) == []
    assert changelog_problems("## [Unreleased]\n", version=RELEASED) == [
        f"no [{RELEASED}] section at version {RELEASED}"
    ]
    good = "## [Unreleased]\n\n## [0.4.0] - d\n\n### Fixed\n\n- a\n\n## [0.3.0] - d\n"
    assert changelog_problems(good, version=RELEASED) == []
    swapped = "## [Unreleased]\n\n## [0.3.0] - d\n\n## [0.4.0] - d\n\n### Fixed\n\n- a\n"
    assert any("not ['Unreleased'" in p for p in changelog_problems(swapped, version=RELEASED))
    left = "## [Unreleased]\n\n- b\n\n## [0.4.0] - d\n\n### Fixed\n\n- a\n\n## [0.3.0] - d\n"
    assert "[Unreleased] is not empty at the release" in changelog_problems(left, version=RELEASED)
    bad = (
        "## [Unreleased]\n\n## [0.4.0] - d\n\n- loose\n\n### Added\n\n- a\n- a\n\n"
        "### Added\n\n- `_x`\n\n## [0.3.0] - d\n"
    )
    problems = changelog_problems(bad, version=RELEASED)
    for words in ("'### Added' appears twice", "_x", "the entry '- a' appears twice", "before the first"):
        assert any(words in p for p in problems), words


def test_versions_agree() -> None:
    """Scenario "Versions agree": the package, its alias and the alias pin."""
    alias = (ROOT / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    version = fenolite.__version__
    assert f'version = "{version}"' in alias and f"fenolite=={version}" in alias


def test_roadmap_names_the_release() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    assert roadmap_problems(text) == []
    row = next(line for line in section(text, "Milestones").splitlines() if "| v0.4 |" in line)
    stale = text.replace(row, row.rsplit("|", 2)[0] + "| proposals, not on `dev` |")
    problems = roadmap_problems(stale)
    assert "roadmap: the row of v0.4 still says 'not on `dev`'" in problems
    assert f"roadmap: the row of v0.4 does not name {RELEASED}" in problems
