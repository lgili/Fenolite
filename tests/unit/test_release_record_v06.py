# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.6 release record says only what exists (capability release-gate, "Release record of v0.6",
"Open tasks in the record of v0.6", "Sections of the record of v0.6", "Scope of 0.6.0 of 2026-10-29",
"Version 0.6.0" and "History row and roadmap of 0.6.0"; change c0242). As for v0.5, the record has one row
per change, named by its folder, and this guard holds each row to that folder's task list, so that no open
task goes unnamed and no row ships with a task left open."""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import fenolite

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.6.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHANGES = ROOT / "openspec" / "changes"
RELEASED = "0.6.0"
PREVIOUS = "0.5.0"
RELEASE_CHANGE = "c0242"
HEADER = "| change | what ships | proof | job | open tasks | result |"
FIELDS = ("change", "ships", "proof", "job", "open", "result")
SHIPS, DEFERRED, PENDING = "ships", "ships with deferred tasks", "pending"
RESULTS = (SHIPS, DEFERRED, PENDING)
PLACEHOLDER = "TODO(coordinator)"
V06_CHANGES = (
    "c0175-board-engineering-tools",
    "c0195-mcp-server",
    "c0196-mcp-design-and-images",
    "c0197-router-input",
    "c0198-ground-ties",
    "c0199-barrier-crossings",
    "c0200-inferred-hypotheses",
    "c0201-file-safety",
    "c0202-return-paths",
    "c0203-fabrication-readback",
    "c0204-practice-checks",
    "c0205-region-placement",
    "c0206-python-api",
    "c0207-diff-gates",
    "c0208-copper-tidy",
    "c0209-drc-trials",
    "c0210-layout-reuse",
    "c0211-region-renders",
    "c0212-assembly-marks",
    "c0213-pour-shapes",
    "c0214-tidy-straighten",
    "c0215-altium-repour",
    "c0221-release-automation",
    "c0223-library-fidelity",
    "c0224-generated-copper",
    "c0225-drc-gate",
    "c0226-silk-clip",
    "c0227-reuse-moves",
    "c0228-octilinear-router",
    "c0229-testpoint-place",
    "c0232-snapshot-consistency",
    "c0233-viewer-review-reliability",
    "c0234-catalog-visual-browser",
    "c0235-viewer-navigation-consistency",
    "c0236-documentation-reconciliation",
    "c0237-public-presentation",
    "c0238-write-recovery",
    "c0239-project-review-status",
    "c0240-catalog-selection",
    "c0241-altium-edit-sessions",
)
"""The changes of 0.6.0: what ``dev`` implemented after 0.5.0 (the maintainer's decision of 2026-10-29):
the MCP server and ``fenolite edit``, the board engineering tools of c0175 and their packages, the computed
Altium pours, the release from a tag, the reliability, viewer, catalog and presentation work and kit Part J
of the Altium edit sessions."""
HELD_FREEZE = ("c0216", "c0217", "c0218", "c0219", "c0220")
"""The v1.0 freeze, held on 2026-10-29: not changes of 0.6.0."""
EARLIER = (
    "c0081",
    "c0105",
    "c0092",
    "c0160",
    "c0166",
    "c0168",
    "c0170",
    "c0172",
    "c0173",
    "c0177",
    "c0178",
    "c0179",
    "c0180",
    "c0181",
    "c0186",
)
"""Open changes of earlier releases whose open tasks "Open changes of earlier releases" must name: the two
of 0.4.0 and before, and the changes of 0.5.0 that shipped with deferred tasks or wait for an archive."""
DEFERRED_AFTER = (
    "c0160",
    "Part T",
    "c0166",
    "c0168",
    "Part S",
    "c0172",
    "c0173",
    "c0092",
    "c0215",
    "K6",
    "c0241",
    "Part J",
    "c0177",
    "c0186",
    "c0105",
    "c0081",
    "c0195",
    "5.4",
    "v0.7",
    "v1.0",
)
"""What "Deferred after v0.6" must name."""
NOT_IN_RELEASE = ("c0216", "c0217", "c0218", "c0219", "c0220", "c0222", "v1.0")
"""What "Not in 0.6.0" must name; it must name no change of the release."""
PROTOCOL_NAMES = ("_meta",)
"""Names with a leading underscore that are not private Python names: ``_meta`` is the field of the Model
Context Protocol where the MCP server puts the exit code (c0195)."""
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
    """The task list of ``change``: its open folder, or its folder in the archive once it is archived.
    A row names a folder (``c0195-mcp-server``); an earlier change is named by its id (``c0081``)."""
    folder = change if "-" in change else f"{change}-*"
    found = sorted(CHANGES.glob(f"{folder}/tasks.md")) or sorted(
        (CHANGES / "archive").glob(f"*-{folder}/tasks.md")
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


def earlier_problems(text: str) -> list[str]:
    """Each open change of an earlier release has an entry that names every one of its open tasks."""
    problems: list[str] = []
    entries = section(text, "Open changes of earlier releases").split("\n- ")
    for change in EARLIER:
        found = next((e for e in entries if e.startswith(f"**{change}.")), None)
        if found is None:
            problems.append(f"{change}: no entry under '## Open changes of earlier releases'")
            continue
        listed = tasks(change)
        if not listed:
            problems.append(f"{change}: no tasks.md")
        problems.extend(
            f"{change}: task {number} is open and not named"
            for number, ticked in listed.items()
            if not ticked and not re.search(rf"\b{re.escape(number)}\b", found)
        )
    return problems


def record_problems(text: str, *, workflow: str) -> list[str]:
    """Everything the guard refuses in the record of ``0.6.0``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    found = rows(text)
    if not found:
        return ["the table of '## Verdict per change' is missing"]
    changes = [row["change"] for row in found]
    problems.extend(f"{change}: no row" for change in V06_CHANGES if change not in changes)
    problems.extend(
        f"{change}: not a change of {RELEASED}" for change in changes if change not in V06_CHANGES
    )
    problems.extend(
        f"{change}: more than one row" for change in sorted(set(changes)) if changes.count(change) > 1
    )
    for row in found:
        problems.extend(row_problems(text, row, known_jobs))
    problems.extend(earlier_problems(text))
    after = section(text, "Deferred after v0.6")
    problems.extend(
        f"deferred after v0.6: {words!r} is missing" for words in DEFERRED_AFTER if words not in after
    )
    absent = section(text, f"Not in {RELEASED}")
    problems.extend(
        f"not in {RELEASED}: {words!r} is missing" for words in NOT_IN_RELEASE if words not in absent
    )
    problems.extend(
        f"not in {RELEASED}: {change} is a change of the release"
        for change in sorted({folder.split("-", 1)[0] for folder in V06_CHANGES})
        if re.search(rf"\b{change}\b", absent)
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
        for words in ("9.0.9", "10.0.6", "release candidate", "release-0.6.0")
        if words not in runs
    )
    build = section(text, "Release build")
    problems.extend(
        f"release build: the section lacks {words!r}"
        for words in (
            "git worktree add",
            "never from the working tree",
            f"v{RELEASED}",
            "tools/release.py check",
        )
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
            "c0195-mcp-server",
        )
        if words not in steps
    )
    for title in ("Archive order", "Deferred after v0.6"):
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
    """At ``0.6.0`` the row ``v0.6.0`` exists with 0 hits; its private gate is ``not run``, or ``on`` once
    the maintainer records his run (c0220 task 1.3)."""
    row = next(
        (line for line in text.splitlines() if line.startswith("|") and f"| v{RELEASED} |" in line), ""
    )
    if not row:
        return [f"{HISTORY.name}: no v{RELEASED} row"] if version == RELEASED else []
    found = cells(row)
    if len(found) != 7:
        return [f"{HISTORY.name}: the v{RELEASED} row needs 7 cells"]
    problems = []
    if found[5] != "not run" and not found[5].startswith("on"):
        problems.append(
            f"{HISTORY.name}: the private gate column of v{RELEASED} says {found[5]!r}, not 'not run' or 'on'"
        )
    if found[6] != "0":
        problems.append(f"{HISTORY.name}: the v{RELEASED} row reports {found[6]} hit(s)")
    return problems


def changelog_problems(text: str, *, version: str) -> list[str]:
    """At ``0.6.0`` the headings start ``Unreleased``, ``0.6.0`` and ``0.5.0``; the ``[0.6.0]`` section has
    exactly one ``Added``, ``Changed`` and ``Fixed`` and is clean by the rules of ``[0.2.0]``."""
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
    if released and sorted(names) != ["Added", "Changed", "Fixed"]:
        problems.append(f"[{RELEASED}]: the headings are {names}, not one Added, Changed and Fixed each")
    problems.extend(
        f"[{RELEASED}]: the heading '### {h}' appears twice" for h in sorted(set(names)) if names.count(h) > 1
    )
    problems.extend(
        f"[{RELEASED}]: an entry names {word}"
        for word in sorted(set(re.findall(r"`(_[A-Za-z0-9_.]+)", body)))
        if word not in PROTOCOL_NAMES
    )
    entries = [line for line in body.splitlines() if line.startswith("- ")]
    problems.extend(
        f"[{RELEASED}]: the entry {line[:60]!r} appears twice"
        for line in sorted(set(entries))
        if entries.count(line) > 1
    )
    titles = [m for line in entries for m in re.findall(r"^- \*\*(.+?)\*\*", line)]
    problems.extend(
        f"[{RELEASED}]: the entry titled {title!r} appears twice"
        for title in sorted(set(titles))
        if titles.count(title) > 1
    )
    loose = [line for line in body.split("###", 1)[0].splitlines() if line.startswith("- ")]
    if loose:
        problems.append(f"[{RELEASED}]: {len(loose)} entries stand before the first '###' heading")
    return problems


def milestone_row(text: str, milestone: str) -> str:
    milestones = section(text, "Milestones")
    return next(
        (
            line
            for line in milestones.splitlines()
            if line.startswith("|") and len(cells(line)) > 1 and cells(line)[1] == milestone
        ),
        "",
    )


def roadmap_problems(text: str) -> list[str]:
    """The milestone row of v0.6 says released as 0.6.0, v0.7 has a row, and v1.0 is held."""
    problems: list[str] = []
    row = milestone_row(text, "v0.6")
    if not row:
        problems.append("roadmap: no milestone row for v0.6")
    elif f"released as `{RELEASED}`" not in cells(row)[-1]:
        problems.append(f"roadmap: the row of v0.6 does not say released as `{RELEASED}`")
    if not milestone_row(text, "v0.7"):
        problems.append("roadmap: no milestone row for v0.7")
    freeze = milestone_row(text, "v1.0")
    if not freeze:
        problems.append("roadmap: no milestone row for v1.0")
    elif "held" not in cells(freeze)[-1] or "2026-10-29" not in cells(freeze)[-1]:
        problems.append("roadmap: the row of v1.0 does not say it is held by the decision of 2026-10-29")
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


EDIT = "c0241-altium-edit-sessions"
SHIPPED = "c0206-python-api"
REPOUR = "c0215-altium-repour"


def test_missing_change_proof_and_job_are_named() -> None:
    text = record()
    without = text.replace(row_line(text, SHIPPED) + "\n", "", 1)
    assert f"{SHIPPED}: no row" in check(without)
    gone = with_cell(text, SHIPPED, "proof", "tests/unit/api/test_missing.py")
    assert any("test_missing.py does not exist" in p for p in check(gone))
    named_gone = with_cell(text, SHIPPED, "proof", "tests/unit/api/test_run_api.py::test_gone")
    assert any("has no function test_gone" in p for p in check(named_gone))
    assert f"{SHIPPED}: no job 'kicad-11' in ci.yml" in check(with_cell(text, SHIPPED, "job", "kicad-11"))


@pytest.mark.parametrize("folder", ("c0216-contract-v1", "c0220-legal-history-1-0", "c0222-net-roles"))
def test_held_or_proposed_changes_are_not_rows(folder: str) -> None:
    """Scenario "A held change named as a row": the freeze is held on 2026-10-29, c0222 is a proposal."""
    text = record()
    stray = text.replace(
        row_line(text, SHIPPED),
        row_line(text, SHIPPED) + "\n" + row_line(text, SHIPPED).replace(SHIPPED, folder),
    )
    assert f"{folder}: not a change of {RELEASED}" in check(stray)


def test_open_task_must_be_named() -> None:
    """Scenario "An open task not named"."""
    open_now = [number for number, ticked in tasks(EDIT).items() if not ticked]
    if "1.2" in open_now:
        kept = ", ".join(number for number in open_now if number != "1.2")
        assert f"{EDIT}: task 1.2 is open and not named" in check(with_cell(record(), EDIT, "open", kept))
    current = row_line(record(), EDIT).split(" | ")[4]
    assert f"{EDIT}: 9.9 is not a task of its tasks.md" in check(
        with_cell(record(), EDIT, "open", f"{current}, 9.9")
    )


def test_results_need_their_entries() -> None:
    text = record()
    assert f"{SHIPPED}: result 'mostly ships'" in check(with_cell(text, SHIPPED, "result", "mostly ships"))
    assert f"{SHIPPED}: a row that is pending names no open task" in check(
        with_cell(text, SHIPPED, "result", "pending")
    )
    if not all(tasks(REPOUR).values()):
        assert f"{REPOUR}: a row that ships names open tasks" in check(
            with_cell(text, REPOUR, "result", "ships")
        )
        no_entry = text.replace(f"- **{REPOUR}.**", "- **The pours.**", 1)
        assert f"{REPOUR}: no entry under '## Deferred to the next release'" in check(no_entry)
        pending = with_cell(text, REPOUR, "result", "pending")
        assert f"{REPOUR}: no entry under '## Pending on the release branch'" in check(pending)


@pytest.mark.parametrize("change", EARLIER)
def test_earlier_changes_name_their_open_tasks(change: str) -> None:
    """Scenario "An open change of 0.5.0 without its entry"."""
    text = record()
    entry_start = f"- **{change}.**"
    assert f"{change}: no entry under '## Open changes of earlier releases'" in check(
        text.replace(entry_start, "- **gone.**", 1)
    )
    open_now = [number for number, ticked in tasks(change).items() if not ticked]
    if open_now:
        body = section(text, "Open changes of earlier releases")
        found = next(e for e in body.split("\n- ") if e.startswith(f"**{change}."))
        hidden = re.sub(rf"\b{re.escape(open_now[0])}\b", "x", found)
        assert f"{change}: task {open_now[0]} is open and not named" in check(text.replace(found, hidden, 1))


@pytest.mark.parametrize("words", DEFERRED_AFTER)
def test_deferred_items_are_named(words: str) -> None:
    """Scenario "A deferred item missing"."""
    body = section(record(), "Deferred after v0.6")
    text = record().replace(body, body.replace(words, "x"), 1)
    assert f"deferred after v0.6: {words!r} is missing" in check(text)


def test_not_in_release_and_altium_write() -> None:
    text = record()
    body = section(text, f"Not in {RELEASED}")
    for change in HELD_FREEZE:
        assert f"not in {RELEASED}: {change!r} is missing" in check(
            text.replace(body, body.replace(change, "x"), 1)
        )
    for change in ("c0195", "c0215", "c0241"):
        late = text.replace(body, body + f"- **{change}**: after `{RELEASED}`.\n", 1)
        assert f"not in {RELEASED}: {change} is a change of the release" in check(late)
    altium = section(text, "Altium write")
    assert any(
        p.startswith("altium write")
        for p in check(text.replace(altium, altium.replace("experimental", "x"), 1))
    )


def test_verdict_over_pending_rows_and_placeholders() -> None:
    """Scenario "Verdict over a placeholder"."""
    text = record()
    assert not [p for p in check(text) if p.startswith("verdict")]
    decided = with_verdict(text, f"Released as v{RELEASED}.")
    if PLACEHOLDER in text:
        assert f"verdict: written while a {PLACEHOLDER} placeholder stands" in check(decided)
    pending = with_verdict(with_cell(text, EDIT, "result", "pending"), f"Released as v{RELEASED}.")
    if not all(tasks(EDIT).values()):
        assert any(p.startswith("verdict: written while") and EDIT in p for p in check(pending))
    clean = with_verdict(text.replace(PLACEHOLDER, "run"), f"Released as v{RELEASED}.")
    for change in [row["change"] for row in rows(clean) if row["result"] == PENDING]:
        clean = with_cell(clean, change, "result", DEFERRED)
    assert not [p for p in check(clean) if p.startswith("verdict")]


def test_steps_and_build_are_stated() -> None:
    text = record()
    assert any(p.startswith("release build") for p in check(text.replace("never from the working tree", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("`main` into `dev`", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("c0195-mcp-server", "x")))
    assert any(p.startswith("runs: 'release-0.6.0'") for p in check(text.replace("release-0.6.0", "x")))


def test_history_row() -> None:
    """Scenario "History row required"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    without = "\n".join(line for line in text.splitlines() if f"| v{RELEASED} |" not in line)
    assert history_problems(without, version=RELEASED) == [f"{HISTORY.name}: no v{RELEASED} row"]
    hits = without + f"\n| 2026-10-29 | v{RELEASED} | root .. abc | all | 5 | not run | 2 |\n"
    assert any("2 hit(s)" in p for p in history_problems(hits, version=RELEASED))
    odd = without + f"\n| 2026-10-29 | v{RELEASED} | root .. abc | all | 5 | maybe | 0 |\n"
    assert any("private gate column" in p for p in history_problems(odd, version=RELEASED))
    on = without + f"\n| 2026-10-29 | v{RELEASED} | root .. abc | all | 5 | on (tokens and hashes) | 0 |\n"
    assert history_problems(on, version=RELEASED) == []


def test_changelog_section() -> None:
    """Scenario "Versions agree": the order of the sections and a clean ``[0.6.0]``."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert changelog_problems(text, version=fenolite.__version__) == []
    assert changelog_problems("## [Unreleased]\n", version=RELEASED) == [
        f"no [{RELEASED}] section at version {RELEASED}"
    ]
    full = "### Added\n\n- a\n\n### Changed\n\n- b\n\n### Fixed\n\n- c\n\n"
    good = f"## [Unreleased]\n\n## [0.6.0] - d\n\n{full}## [0.5.0] - d\n"
    assert changelog_problems(good, version=RELEASED) == []
    swapped = f"## [Unreleased]\n\n## [0.5.0] - d\n\n## [0.6.0] - d\n\n{full}"
    assert any("not ['Unreleased'" in p for p in changelog_problems(swapped, version=RELEASED))
    left = f"## [Unreleased]\n\n- b\n\n## [0.6.0] - d\n\n{full}## [0.5.0] - d\n"
    assert "[Unreleased] is not empty at the release" in changelog_problems(left, version=RELEASED)
    dup = "- **T** (c1): one.\n- **T** (c1): two.\n\n"
    twice = f"## [Unreleased]\n\n## [0.6.0] - d\n\n{full}{dup}## [0.5.0] - d\n"
    assert any("titled 'T' appears twice" in p for p in changelog_problems(twice, version=RELEASED))


def test_versions_agree() -> None:
    """Scenario "Versions agree": the package, its alias, the alias pin and the release tool."""
    alias = (ROOT / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    version = fenolite.__version__
    assert f'version = "{version}"' in alias and f"fenolite=={version}" in alias
    if version == RELEASED:
        spec = importlib.util.spec_from_file_location("release_tool_v06", ROOT / "tools" / "release.py")
        assert spec and spec.loader
        tool = importlib.util.module_from_spec(spec)
        sys.modules["release_tool_v06"] = tool
        spec.loader.exec_module(tool)
        assert tool.check(ROOT, f"v{RELEASED}") == []


def test_roadmap_names_the_release() -> None:
    """Scenario "The freeze held"."""
    text = ROADMAP.read_text(encoding="utf-8")
    assert roadmap_problems(text) == []
    row = milestone_row(text, "v0.6")
    stale = text.replace(row, row.rsplit("|", 2)[0] + "| estimate |")
    assert f"roadmap: the row of v0.6 does not say released as `{RELEASED}`" in roadmap_problems(stale)
    freeze = milestone_row(text, "v1.0")
    unheld = text.replace(freeze, freeze.rsplit("|", 2)[0] + "| proposed |")
    assert (
        "roadmap: the row of v1.0 does not say it is held by the decision of 2026-10-29"
        in roadmap_problems(unheld)
    )
    assert f"roadmap: the release change {RELEASE_CHANGE} is not named" in roadmap_problems(
        text.replace(RELEASE_CHANGE, "c9999")
    )
