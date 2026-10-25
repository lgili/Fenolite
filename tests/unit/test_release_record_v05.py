# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.5 release record says only what exists (capability release-gate, "Release record of v0.5",
"Open tasks in the record of v0.5", "Sections of the record of v0.5", "Scope of 0.5.0 of 2026-10-16",
"Version 0.5.0" and "History row and roadmap of 0.5.0"; change c0171). As for v0.4, the record has one row
per change, named by its folder (two archived changes hold the id c0164), and this guard holds each row to
that folder's task list, so that no open task goes unnamed and no row ships with a task left open."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fenolite

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.5.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHANGES = ROOT / "openspec" / "changes"
RELEASED = "0.5.0"
PREVIOUS = "0.4.0"
RELEASE_CHANGE = "c0171"
HEADER = "| change | what ships | proof | job | open tasks | result |"
FIELDS = ("change", "ships", "proof", "job", "open", "result")
SHIPS, DEFERRED, PENDING = "ships", "ships with deferred tasks", "pending"
RESULTS = (SHIPS, DEFERRED, PENDING)
PLACEHOLDER = "TODO(coordinator)"
V05_CHANGES = (
    "c0092-altium-write-graduation",
    "c0155-altium-bodies-default",
    "c0156-kicad-cli-docker-user",
    "c0157-yardstick-route-order",
    "c0158-equivalent-public",
    "c0159-convert-command",
    "c0160-convert-to-altium",
    "c0161-convert-to-kicad",
    "c0162-kicad-downgrade",
    "c0163-opaque-net-stored-name",
    "c0164-altium-schematic-layout",
    "c0164-native-altium-template",
    "c0165-schematic-block-composition",
    "c0166-altium-native-acceptance",
    "c0167-board-slots",
    "c0168-altium-slots-cutouts",
    "c0169-edge-clearance-check",
    "c0170-convert-slots-obstacles",
    "c0172-altium-draftsman",
    "c0173-board-panels",
    "c0174-board-design-guide",
    "c0176-board-viewer",
    "c0177-schematic-viewer",
    "c0178-native-themes",
    "c0179-libraries-and-units",
    "c0180-draftsman-viewer",
    "c0181-altium-native-layers",
    "c0182-viewer-performance",
    "c0183-board-rule-areas",
    "c0184-visual-diff",
    "c0185-project-nets",
    "c0186-variants-view",
    "c0187-review-panels",
    "c0188-check-overlay",
    "c0189-review-tools",
    "c0190-documentation-views",
    "c0191-viewer-visual-tests",
)
"""The changes of 0.5.0: v0.5a, the changes on ``dev`` after 0.4.0, c0092's rule, the slot changes c0167 to
c0170 (c0167 and c0169 placed on 2026-10-15, c0168 and c0170 on 2026-10-16), c0172 and c0173, which the
maintainer added on 2026-10-16, and by his decision of 2026-10-25 everything done since: the agent guide's
practice pages (c0174) and the viewer (c0176 to c0191)."""
PLACED_2026_10_16 = (
    "c0168-altium-slots-cutouts",
    "c0170-convert-slots-obstacles",
    "c0172-altium-draftsman",
    "c0173-board-panels",
)
HELD: tuple[str, ...] = ()
"""The changes 0.5.0 is held for. From 2026-10-16 it held c0172 and c0173 until their native parts passed the
maintainer's Altium kits; his decision of 2026-10-25 releases 0.5.0 without them, so their open tasks are
deferred to v0.6 like every other test of his, and nothing is held."""
EARLIER = ("c0081", "c0105", "c0146")
"""Open changes of earlier releases whose open tasks "Open changes of earlier releases" must name (c0146 has
none since 2026-10-16; its entry stays until its folder is archived)."""
DEFERRED_AFTER = (
    "Part T",
    "c0166",
    "R1",
    "R5",
    "c0092",
    "5.2",
    "6.2",
    "kit run",
    "c0081",
    "c0105",
    "c0168",
    "Part S",
    "c0172",
    "c0173",
    "v0.6",
)
"""What "Deferred after v0.5" must name."""
NOT_IN_RELEASE = ("c0151", "c0175", "v0.5b")
"""What "Not in 0.5.0" must name; it must name no change of the release."""
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
    A row names a folder (``c0159-convert-command``); an earlier change is named by its id (``c0081``)."""
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
    if change in HELD and given and result != PENDING:
        problems.append(f"{change}: 0.5.0 is held for it, so a row with open tasks is {PENDING}")
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
    """Everything the guard refuses in the record of ``0.5.0``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    found = rows(text)
    if not found:
        return ["the table of '## Verdict per change' is missing"]
    changes = [row["change"] for row in found]
    problems.extend(f"{change}: no row" for change in V05_CHANGES if change not in changes)
    problems.extend(f"{change}: not a change of 0.5.0" for change in changes if change not in V05_CHANGES)
    problems.extend(
        f"{change}: more than one row" for change in sorted(set(changes)) if changes.count(change) > 1
    )
    for row in found:
        problems.extend(row_problems(text, row, known_jobs))
    problems.extend(earlier_problems(text))
    after = section(text, "Deferred after v0.5")
    problems.extend(
        f"deferred after v0.5: {words!r} is missing" for words in DEFERRED_AFTER if words not in after
    )
    absent = section(text, f"Not in {RELEASED}")
    problems.extend(
        f"not in {RELEASED}: {words!r} is missing" for words in NOT_IN_RELEASE if words not in absent
    )
    problems.extend(
        f"not in {RELEASED}: {change} is a change of the release"
        for change in sorted({folder.split("-", 1)[0] for folder in V05_CHANGES})
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
        for words in ("9.0.9", "10.0.6", "release candidate", "release-0.5.0")
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
    for title in ("Archive order", "Deferred after v0.5"):
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
    """At ``0.5.0`` the headings start ``Unreleased``, ``0.5.0`` and ``0.4.0``; the ``[0.5.0]`` section has
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
    """The milestone row of v0.5a says it is released as 0.5.0."""
    problems: list[str] = []
    milestones = section(text, "Milestones")
    row = next((line for line in milestones.splitlines() if "| v0.5a" in line), "")
    if not row:
        problems.append("roadmap: no milestone row for v0.5a")
    elif f"released as `{RELEASED}`" not in cells(row)[-1]:
        problems.append(f"roadmap: the row of v0.5a does not say released as `{RELEASED}`")
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


SLOTS = "c0167-board-slots"
ALTIUM = "c0160-convert-to-altium"
SHIPPED = "c0156-kicad-cli-docker-user"


def test_missing_change_proof_and_job_are_named() -> None:
    text = record()
    without = text.replace(row_line(text, SHIPPED) + "\n", "", 1)
    assert f"{SHIPPED}: no row" in check(without)
    gone = with_cell(text, SHIPPED, "proof", "tests/unit/backends/kicad/test_missing.py")
    assert any("test_missing.py does not exist" in p for p in check(gone))
    named_gone = with_cell(text, SHIPPED, "proof", "tests/unit/backends/kicad/test_docker_cli.py::test_gone")
    assert any("has no function test_gone" in p for p in check(named_gone))
    assert f"{SHIPPED}: no job 'kicad-11' in ci.yml" in check(with_cell(text, SHIPPED, "job", "kicad-11"))
    stray = text.replace(
        row_line(text, SHIPPED), row_line(text, SHIPPED).replace(SHIPPED, "c0151-repeat-bus-split")
    )
    assert "c0151-repeat-bus-split: not a change of 0.5.0" in check(stray)


@pytest.mark.parametrize("change", PLACED_2026_10_16)
def test_changes_placed_on_2026_10_16_need_their_rows(change: str) -> None:
    """c0168 and c0170 are in 0.5.0 since 2026-10-16, and so are c0172 and c0173."""
    text = record()
    assert f"{change}: no row" in check(text.replace(row_line(text, change) + "\n", "", 1))


def test_open_task_must_be_named() -> None:
    """Scenario "An open task not named"."""
    open_now = [number for number, ticked in tasks(ALTIUM).items() if not ticked]
    if "5.3" in open_now:
        kept = ", ".join(number for number in open_now if number != "5.3")
        assert f"{ALTIUM}: task 5.3 is open and not named" in check(with_cell(record(), ALTIUM, "open", kept))
    named = row_line(record(), ALTIUM).split(" | ")[4]
    assert f"{ALTIUM}: 9.9 is not a task of its tasks.md" in check(
        with_cell(record(), ALTIUM, "open", f"{named}, 9.9")
    )


def test_two_folders_of_one_id_are_told_apart() -> None:
    """The two archived changes c0164 are read from their own task lists."""
    layout = tasks("c0164-altium-schematic-layout")
    template = tasks("c0164-native-altium-template")
    assert layout and template and layout != template


def test_results_need_their_entries() -> None:
    text = record()
    assert f"{SHIPPED}: result 'mostly ships'" in check(with_cell(text, SHIPPED, "result", "mostly ships"))
    assert f"{SHIPPED}: a row that is pending names no open task" in check(
        with_cell(text, SHIPPED, "result", "pending")
    )
    graduation = "c0092-altium-write-graduation"
    assert f"{graduation}: a row that ships names open tasks" in check(
        with_cell(text, graduation, "result", "ships")
    )
    no_entry = text.replace(f"- **{graduation}.**", "- **The rule.**", 1)
    assert f"{graduation}: no entry under '## Deferred to the next release'" in check(no_entry)
    pending = with_cell(text, graduation, "result", "pending")
    assert f"{graduation}: no entry under '## Pending on the release branch'" in check(pending)


def test_nothing_is_held_since_2026_10_25() -> None:
    """The maintainer's decision of 2026-10-25 lifts the hold of 2026-10-16: c0172 and c0173 ship with their
    open tasks deferred to v0.6, and a held change would still have to stay pending."""
    assert HELD == ()
    text = record()
    for change in ("c0172-altium-draftsman", "c0173-board-panels"):
        assert row_line(text, change).rstrip(" |").endswith(DEFERRED)


@pytest.mark.parametrize("change", EARLIER)
def test_earlier_changes_name_their_open_tasks(change: str) -> None:
    text = record()
    entry_start = f"- **{change}.**"
    assert f"{change}: no entry under '## Open changes of earlier releases'" in check(
        text.replace(entry_start, "- **gone.**", 1)
    )
    open_now = [number for number, ticked in tasks(change).items() if not ticked]
    if open_now:
        body = section(text, "Open changes of earlier releases")
        entry = next(e for e in body.split("\n- ") if e.startswith(f"**{change}."))
        hidden = re.sub(rf"\b{re.escape(open_now[0])}\b", "x", entry)
        assert f"{change}: task {open_now[0]} is open and not named" in check(text.replace(entry, hidden, 1))


@pytest.mark.parametrize("words", DEFERRED_AFTER)
def test_deferred_items_are_named(words: str) -> None:
    """Scenario "A deferred item missing"."""
    body = section(record(), "Deferred after v0.5")
    text = record().replace(body, body.replace(words, "x"), 1)
    assert f"deferred after v0.5: {words!r} is missing" in check(text)


def test_not_in_release_and_altium_write() -> None:
    text = record()
    body = section(text, f"Not in {RELEASED}")
    assert f"not in {RELEASED}: 'c0151' is missing" in check(
        text.replace(body, body.replace("c0151", "x"), 1)
    )
    for change in ("c0168", "c0170", "c0172", "c0173"):
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
    problems = check(decided)
    if PLACEHOLDER in text:
        assert f"verdict: written while a {PLACEHOLDER} placeholder stands" in problems
    held = [row["change"] for row in rows(text) if row["change"] in HELD and row["result"] == PENDING]
    if held:
        assert f"verdict: written while {', '.join(held)} is pending" in problems
    pending = with_verdict(with_cell(text, SLOTS, "result", "pending"), f"Released as v{RELEASED}.")
    if tasks(SLOTS) and not all(tasks(SLOTS).values()):
        assert any(p.startswith("verdict: written while") and SLOTS in p for p in check(pending))
    clean = with_verdict(text.replace(PLACEHOLDER, "run"), f"Released as v{RELEASED}.")
    for change in [row["change"] for row in rows(clean) if row["result"] == PENDING]:
        clean = with_cell(clean, change, "result", DEFERRED)
    assert not [p for p in check(clean) if p.startswith("verdict")]


def test_steps_and_build_are_stated() -> None:
    text = record()
    assert any(p.startswith("release build") for p in check(text.replace("never from the working tree", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("`main` into `dev`", "x")))
    assert any(p.startswith("runs: 'release-0.5.0'") for p in check(text.replace("release-0.5.0", "x")))


def test_history_row() -> None:
    """Scenario "History row required"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    without = "\n".join(line for line in text.splitlines() if f"| v{RELEASED} |" not in line)
    assert history_problems(without, version=RELEASED) == [f"{HISTORY.name}: no v{RELEASED} row"]
    claimed = without + f"\n| 2026-10-15 | v{RELEASED} | root .. abc | all | 5 | on | 0 |\n"
    assert any("private gate column" in p for p in history_problems(claimed, version=RELEASED))


def test_changelog_section() -> None:
    """Scenario "Versions agree": the order of the sections and a clean ``[0.5.0]``."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert changelog_problems(text, version=fenolite.__version__) == []
    assert changelog_problems("## [Unreleased]\n", version=RELEASED) == [
        f"no [{RELEASED}] section at version {RELEASED}"
    ]
    full = "### Added\n\n- a\n\n### Changed\n\n- b\n\n### Fixed\n\n- c\n\n"
    good = f"## [Unreleased]\n\n## [0.5.0] - d\n\n{full}## [0.4.0] - d\n"
    assert changelog_problems(good, version=RELEASED) == []
    swapped = f"## [Unreleased]\n\n## [0.4.0] - d\n\n## [0.5.0] - d\n\n{full}"
    assert any("not ['Unreleased'" in p for p in changelog_problems(swapped, version=RELEASED))
    left = f"## [Unreleased]\n\n- b\n\n## [0.5.0] - d\n\n{full}## [0.4.0] - d\n"
    assert "[Unreleased] is not empty at the release" in changelog_problems(left, version=RELEASED)
    odd = f"## [Unreleased]\n\n## [0.5.0] - d\n\n### Altium to KiCad\n\n- z\n\n{full}## [0.4.0] - d\n"
    assert any("not one Added, Changed and Fixed" in p for p in changelog_problems(odd, version=RELEASED))
    bad = (
        "## [Unreleased]\n\n## [0.5.0] - d\n\n- loose\n\n### Added\n\n- a\n- a\n\n"
        "### Added\n\n- `_x`\n\n## [0.4.0] - d\n"
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
    row = next(line for line in section(text, "Milestones").splitlines() if "| v0.5a" in line)
    stale = text.replace(row, row.rsplit("|", 2)[0] + "| estimate |")
    assert f"roadmap: the row of v0.5a does not say released as `{RELEASED}`" in roadmap_problems(stale)
    assert f"roadmap: the release change {RELEASE_CHANGE} is not named" in roadmap_problems(
        stale.replace(RELEASE_CHANGE, "c9999")
    )
