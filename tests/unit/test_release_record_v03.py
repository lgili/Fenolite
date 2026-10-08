# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.3 release record says only what exists (capability release-gate, "Release record of v0.3" and
"Version 0.3.0"; change c0150). The rules of the rows are those of ``test_release_record_v02.py``; this
guard adds the graduation table of the Altium write, which must agree with the evidence matrix, the
exception the maintainer made for the kit and the revalidation it owes, and the list of what is not in
the release."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fenolite
from fenolite.backends.altium.claims import MATRIX

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.3.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RESULTS = ("met", "met with a recorded limit", "not met", "pending")
HEADER = "| item | statement | proof | job | result |"
RELEASED = "0.3.0"
RELEASE_CHANGE = "c0150"
ITEMS = ("1", "2", "3", "4", "5")
"""The items of the roadmap's block "v0.3 acceptance"."""
GRADUATION_HEADER = "| kind | file |"
VERDICTS = ("experimental", "graduated")
RUN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+")
CHANGE_ID = re.compile(r"c\d{4}")
NOT_IN_RELEASE = (
    "c0137",
    "v0.4",
    "c0151",
    "c0152",
    "Part G",
    "X8",
    "Part V",
)
"""What the section "Not in 0.3.0" must name: the deferred change, the parked milestone, the two open
defects with their proposed follow-ups, and the owed Altium parts."""
EXCEPTION_WORDS = ("exception", "condition (d)", "fenolite kit verify", "fenolite kit record", "c0148")
"""What "Graduation of the Altium write" must say about the maintainer's decision on the kit."""


def section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def table(body: str, header: str = HEADER) -> list[list[str]]:
    """The rows of the first table of ``body`` whose header line starts with ``header``."""
    lines = body.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(header)), None)
    if start is None:
        return []
    found: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        found.append(cells(line))
    return found


def rows(text: str, title: str) -> list[dict[str, str]]:
    found = table(section(text, title))
    assert found, f"the table of '## {title}' is missing"
    for row in found:
        assert len(row) == 5, row
    return [dict(zip(("item", "statement", "proof", "job", "result"), row, strict=True)) for row in found]


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


def label(item: str) -> str:
    """How an entry names a row: ``v0.3 item 3`` for an item of the acceptance, the change id otherwise."""
    return item if CHANGE_ID.fullmatch(item) else f"v0.3 item {item}"


def entries(text: str, title: str, name: str) -> str:
    """The list entries of ``## <title>`` whose bold head starts with ``name`` (or, for an item of the
    acceptance, with its number)."""
    heads = (name, name.removeprefix("v0.3 item ")) if name.startswith("v0.3 item ") else (name,)
    found = [
        e
        for e in section(text, title).split("\n- ")
        if any(re.match(rf"\*\*{re.escape(head)}[.,]", e) for head in heads)
    ]
    return "\n".join(found)


def row_problems(text: str, row: dict[str, str], known_jobs: set[str]) -> list[str]:
    name = label(row["item"])
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


def graduation_problems(text: str) -> list[str]:
    """The table of "Graduation of the Altium write" against the write cells of the Altium matrix: one row
    per kind, and a kind is `graduated` exactly when the matrix no longer lists its write as experimental."""
    body = section(text, "Graduation of the Altium write")
    problems: list[str] = []
    found = {row[0].strip("`"): row for row in table(body, GRADUATION_HEADER)}
    kinds = {row.kind: row for row in MATRIX if row.write is not None}
    problems.extend(f"graduation: no row for {kind}" for kind in sorted(set(kinds) - set(found)))
    problems.extend(
        f"graduation: {kind} is not an Altium write kind" for kind in sorted(set(found) - set(kinds))
    )
    for kind, row in sorted(found.items()):
        verdict = row[-1]
        if verdict not in VERDICTS:
            problems.append(f"graduation: {kind} has the verdict {verdict!r}")
            continue
        if kind in kinds:
            experimental = "write" in kinds[kind].experimental
            if experimental != (verdict == "experimental"):
                problems.append(f"graduation: {kind} says {verdict!r}, the matrix disagrees")
            if len(row) > 2 and row[2].isdigit() and int(row[2]) != len(kinds[kind].write.hypotheses):
                problems.append(
                    f"graduation: {kind} counts {row[2]} ids, the write cell names another number"
                )
    problems.extend(
        f"graduation: the words {words!r} are missing" for words in EXCEPTION_WORDS if words not in body
    )
    return problems


def record_problems(text: str, *, workflow: str) -> list[str]:
    """Everything the guard refuses in the record of ``0.3.0``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    pending: list[str] = []
    for title, needed in (("Acceptance of v0.3", ITEMS), ("Also in this package", ())):
        found = rows(text, title)
        for row in found:
            if row["item"] not in needed and not CHANGE_ID.fullmatch(row["item"]):
                problems.append(
                    f"{label(row['item'])}: the item is neither a number of the acceptance nor a change id"
                )
            problems.extend(row_problems(text, row, known_jobs))
            if row["result"] == "pending":
                pending.append(label(row["item"]))
        missing = sorted(set(needed) - {row["item"] for row in found})
        problems.extend(f"v0.3 item {item}: no row" for item in missing)
    problems.extend(graduation_problems(text))
    absent = section(text, "Not in 0.3.0")
    problems.extend(f"not in 0.3.0: {words!r} is missing" for words in NOT_IN_RELEASE if words not in absent)
    limits = section(text, "Recorded limits")
    for words in ("public gate only", "private gate was not run"):
        if words not in limits:
            problems.append(f"limits: {words!r} is missing")
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
    for words in ("verdict", "`dev` to `main`", "v0.3.0", "clean checkout", "Publish", "`main` into `dev`"):
        if words not in steps:
            problems.append(f"maintainer's steps: {words!r} is missing")
    if not section(text, "Deferred after v0.3").strip():
        problems.append("deferred: the section is missing")
    verdict = section(text, "Verdict").strip()
    if not verdict:
        problems.append("verdict: the section is missing")
    elif pending and verdict != "pending":
        problems.append(f"verdict: written while {', '.join(pending)} is pending")
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
    """At ``0.3.0`` the headings start ``Unreleased``, ``0.3.0`` and a section of the 0.2 series, the newest
    patch first; the ``[0.3.0]`` section is clean by the rules of ``[0.2.0]``."""
    headings = re.findall(r"^## \[([^\]]+)\]", text, re.MULTILINE)
    if RELEASED not in headings:
        return [f"no [{RELEASED}] section at version {version}"] if version == RELEASED else []
    problems: list[str] = []
    if version == RELEASED:
        if headings[:2] != ["Unreleased", RELEASED]:
            problems.append(f"the sections start {headings[:2]}, not ['Unreleased', '{RELEASED}']")
        after = headings[headings.index(RELEASED) + 1 : headings.index(RELEASED) + 2]
        if not after or not after[0].startswith("0.2."):
            problems.append(f"the section after [{RELEASED}] is {after}, not one of the 0.2 series")
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
    archived = [line for line in body.splitlines() if line.startswith("- ") and "Archived" in line]
    if len(archived) > 1:
        problems.append(f"[{RELEASED}]: {len(archived)} entries about archived specs; fold them into one")
    loose = [line for line in body.split("###", 1)[0].splitlines() if line.startswith("- ")]
    if loose:
        problems.append(f"[{RELEASED}]: {len(loose)} entries stand before the first '###' heading")
    return problems


def roadmap_problems(text: str) -> list[str]:
    """The milestone row of v0.3 may not say ``proposed``, and the roadmap names the release change."""
    problems: list[str] = []
    milestones = section(text, "Milestones")
    row = next((line for line in milestones.splitlines() if "| v0.3 |" in line), "")
    if not row:
        problems.append("roadmap: no milestone row for v0.3")
    elif "proposed" in cells(row)[-1]:
        problems.append("roadmap: the row of v0.3 still says 'proposed'")
    if RELEASE_CHANGE not in text:
        problems.append(f"roadmap: the release change {RELEASE_CHANGE} is not named")
    return problems


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def check(text: str) -> list[str]:
    return record_problems(text, workflow=WORKFLOW.read_text(encoding="utf-8"))


def with_result(text: str, start: str, result: str) -> str:
    line = next(row for row in text.splitlines() if row.startswith(start))
    return text.replace(line, line.rsplit("|", 2)[0] + f"| {result} |", 1)


def test_record_is_consistent() -> None:
    """Scenario "Every item present"."""
    assert check(record()) == []


def test_missing_proof_and_unknown_job_are_named() -> None:
    """Scenarios "Missing proof" and "Unknown job"."""
    text = record().replace("tests/unit/model/test_pin_pad_map.py", "tests/unit/model/test_missing.py", 1)
    assert any("test_missing.py does not exist" in p for p in check(text))
    text = record().replace("::test_several_pads_of_one_pin", "::test_gone", 1)
    assert any("has no function test_gone" in p for p in check(text))
    line = next(row for row in record().splitlines() if row.startswith("| c0123 |"))
    text = record().replace(line, line.replace("| unit |", "| kicad-11 |"), 1)
    assert any("no job 'kicad-11' in ci.yml" in p for p in check(text))


def test_results_limits_and_open_rows() -> None:
    """Scenarios "Another word", "Limit without an entry" and "Open row without a reason"."""
    text = record()
    assert any("result 'mostly met'" in p for p in check(with_result(text, "| c0123 |", "mostly met")))
    assert any(
        p.startswith("c0123") and "Open rows" in p for p in check(with_result(text, "| c0123 |", "not met"))
    )
    assert any(
        p.startswith("c0123") and "Recorded limits" in p
        for p in check(with_result(text, "| c0123 |", "met with a recorded limit"))
    )
    without = text.replace("- **v0.3 item 2, RT-A3.**", "- **Round trips.**", 1)
    assert any(p.startswith("v0.3 item 2") and "Recorded limits" in p for p in check(without))


def test_missing_item_is_named() -> None:
    """Scenario "Missing item"."""
    text = "\n".join(line for line in record().splitlines() if not line.startswith("| 4 |"))
    assert "v0.3 item 4: no row" in check(text)


def test_graduation_agrees_with_the_matrix() -> None:
    """Scenario "Graduation table agrees with the matrix"."""
    text = record()
    assert graduation_problems(text) == []
    line = next(row for row in text.splitlines() if row.startswith("| `altium_pcbdoc` |"))
    graduated = text.replace(line, line.rsplit("|", 2)[0] + "| graduated |", 1)
    assert "graduation: altium_pcbdoc says 'graduated', the matrix disagrees" in graduation_problems(
        graduated
    )
    assert "graduation: no row for altium_pcbdoc" in graduation_problems(text.replace(line + "\n", "", 1))
    unexplained = text.replace("fenolite kit record", "the record", 1)
    assert "graduation: the words 'fenolite kit record' are missing" in graduation_problems(unexplained)


@pytest.mark.parametrize("words", NOT_IN_RELEASE)
def test_what_is_not_in_the_release_is_named(words: str) -> None:
    """Scenario "What is not in the release"."""
    body = section(record(), "Not in 0.3.0")
    text = record().replace(body, body.replace(words, "x"), 1)
    assert f"not in 0.3.0: {words!r} is missing" in check(text)


def test_verdict_over_a_pending_row() -> None:
    """Scenario "Verdict over a pending row"."""
    assert not [p for p in check(record()) if p.startswith("verdict")]
    text = with_result(record(), "| c0123 |", "pending").replace(
        "## Open rows\n", "## Open rows\n\n- **c0123.** Open.\n", 1
    )
    waits = re.sub(r"## Verdict\n\n.*\Z", "## Verdict\n\npending\n", text, flags=re.DOTALL)
    assert not [p for p in check(waits) if p.startswith("verdict")]
    decided = re.sub(r"## Verdict\n\n.*\Z", "## Verdict\n\nReleased as v0.3.0.\n", text, flags=re.DOTALL)
    assert any(p.startswith("verdict: written while c0123") for p in check(decided))


def test_steps_and_build_are_stated() -> None:
    """Scenario "Maintainer's steps"."""
    text = record()
    assert any(p.startswith("release build") for p in check(text.replace("never from the working tree", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("`main` into `dev`", "x")))


def test_history_row() -> None:
    """Scenario "History row required"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    without = "\n".join(line for line in text.splitlines() if f"| v{RELEASED} |" not in line)
    assert history_problems(without, version=RELEASED) == [f"{HISTORY.name}: no v{RELEASED} row"]
    claimed = without + f"\n| 2026-10-08 | v{RELEASED} | root .. abc | all | 5 | on | 0 |\n"
    assert any("private gate column" in p for p in history_problems(claimed, version=RELEASED))


def test_changelog_section() -> None:
    """Scenarios "Versions agree" and "Changelog section is clean"."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert changelog_problems(text, version=fenolite.__version__) == []
    assert changelog_problems("## [Unreleased]\n", version=RELEASED) == [
        f"no [{RELEASED}] section at version {RELEASED}"
    ]
    merged = "## [Unreleased]\n\n## [0.3.0] - d\n\n### Fixed\n\n- a\n\n## [0.2.2] - d\n\n## [0.2.1] - d\n"
    assert changelog_problems(merged, version=RELEASED) == []
    swapped = "## [Unreleased]\n\n## [0.2.2] - d\n\n## [0.3.0] - d\n\n### Fixed\n\n- a\n\n## [0.2.1] - d\n"
    assert any("not ['Unreleased', '0.3.0']" in p for p in changelog_problems(swapped, version=RELEASED))
    bad = (
        "## [Unreleased]\n\n## [0.3.0] - d\n\n- loose\n\n### Added\n\n- Archived a\n- Archived b\n\n"
        "### Added\n\n- `_x`\n\n## [0.2.1] - d\n"
    )
    problems = changelog_problems(bad, version=RELEASED)
    for words in ("appears twice", "_x", "fold them into one", "before the first"):
        assert any(words in p for p in problems), words


def test_versions_agree() -> None:
    """Scenario "Versions agree": the package, its alias and the alias pin."""
    alias = (ROOT / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    version = fenolite.__version__
    assert f'version = "{version}"' in alias and f"fenolite=={version}" in alias


def test_roadmap_names_the_release() -> None:
    """Scenario "Stale roadmap state rejected"."""
    text = ROADMAP.read_text(encoding="utf-8")
    assert roadmap_problems(text) == []
    row = next(line for line in section(text, "Milestones").splitlines() if "| v0.3 |" in line)
    stale = text.replace(row, row.rsplit("|", 2)[0] + "| proposed |")
    assert "roadmap: the row of v0.3 still says 'proposed'" in roadmap_problems(stale)
