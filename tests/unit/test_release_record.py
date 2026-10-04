# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.1 release record says only what exists (capability release-gate, "Release record", "Release
build and local checks" and "Version 0.1.0"; change c0025)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fenolite

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.1.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
RESULTS = ("met", "met with a recorded limit", "not met", "pending")
HEADER = "| item | statement | proof | job | result |"
SCHEMA_SENTENCE = "envelope, error and manifest schemas only"
RELEASED = "0.1.0"


def section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def rows(text: str) -> list[dict[str, str]]:
    """The rows of the acceptance table."""
    lines = section(text, "Acceptance").splitlines()
    assert HEADER in lines, "the acceptance table is missing"
    found: list[dict[str, str]] = []
    for line in lines[lines.index(HEADER) + 2 :]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 5, line
        found.append(dict(zip(("item", "statement", "proof", "job", "result"), cells, strict=True)))
    return found


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


def limit_for(text: str, item: str) -> str:
    """The entries of ``## Recorded limits`` that name ``Item <n>``."""
    return "\n".join(
        entry for entry in section(text, "Recorded limits").split("\n- ") if f"Item {item}" in entry
    )


def record_problems(text: str, *, version: str) -> list[str]:
    """Everything the guard refuses in a record."""
    problems: list[str] = []
    table = rows(text)
    for row in table:
        label = f"item {row['item']} ({row['statement'][:40]})"
        why = proof_problem(row["proof"])
        if why:
            problems.append(f"{label}: proof {why}")
        if row["result"] not in RESULTS:
            problems.append(f"{label}: result {row['result']!r}")
        if row["result"] == "pending" and version == RELEASED:
            problems.append(f"{label}: still pending at version {RELEASED}")
        if row["result"] == "met with a recorded limit" and not limit_for(text, row["item"]):
            problems.append(f"{label}: no entry under '## Recorded limits'")
    missing = sorted({str(n) for n in range(1, 9)} - {row["item"] for row in table})
    problems.extend(f"item {item}: no row" for item in missing)

    limits = section(text, "Recorded limits")
    item2 = limit_for(text, "2")
    for word in ("heavy", "not judged", "rt2-9"):
        if word not in item2:
            problems.append(f"item 2: the limit lacks {word!r}")
    if SCHEMA_SENTENCE not in limit_for(text, "5"):
        problems.append(f"item 5: the limit lacks the sentence {SCHEMA_SENTENCE!r}")
    for row in table:
        if row["result"] == "met" and (row["item"] == "2" or "schemas" in row["statement"]):
            problems.append(f"item {row['item']}: a row with a fixed limit says 'met' ({SCHEMA_SENTENCE})")
    for words in ("public gate only", "private gate was not run"):
        if words not in limits:
            problems.append(f"limits: the residue scan entry lacks {words!r}")
    docker = next((e for e in limits.split("\n- ") if "H-K-CLI-DOCKER" in e), "")
    if "verified locally only" not in docker or "test_docker_cli.py" not in docker:
        problems.append("limits: H-K-CLI-DOCKER must say 'verified locally only' and name its test")
    for name in ("H-G-EDGE-EXACT", "H-G-PLACE-OUTLINE", "place.no-outline"):
        if name not in limits:
            problems.append(f"limits: the board outline entry lacks {name}")

    deferred = section(text, "Deferred after v0.1")
    for name in ("per-command result schemas", "outline snapping tolerance"):
        if name not in deferred:
            problems.append(f"deferred: {name} is not listed")
    if "rule constructor" in deferred:
        problems.append("deferred: the DSL rule constructor is delivered in v0.1 (c0054)")

    build = section(text, "Release build")
    for words in ("git worktree add", "never from the working tree"):
        if words not in build:
            problems.append(f"release build: the section lacks {words!r}")
    if not section(text, "Verdict").strip():
        problems.append("verdict: the section is missing")
    if "## Manual checks" not in text or "UNVERIFIED" not in section(text, "Manual checks"):
        problems.append("manual checks: the section must hold both checks, the agent session as UNVERIFIED")
    return problems


def history_problems(text: str, *, version: str) -> list[str]:
    """Why the residue history page does not allow ``version``."""
    row = next((line for line in text.splitlines() if line.startswith("|") and "| v0.1.0 |" in line), "")
    if not row:
        return [f"{HISTORY.name}: no v0.1.0 row"] if version == RELEASED else []
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    problems: list[str] = []
    if len(cells) != 7:
        return [f"{HISTORY.name}: the v0.1.0 row needs 7 cells"]
    if cells[5] != "not run":
        problems.append(f"{HISTORY.name}: the private gate column of v0.1.0 says {cells[5]!r}, not 'not run'")
    if cells[6] != "0":
        problems.append(f"{HISTORY.name}: the v0.1.0 row reports {cells[6]} hit(s)")
    return problems


def changelog_problems(text: str) -> list[str]:
    """A released or unreleased top section with a repeated heading, or an entry naming a private name."""
    match = re.search(r"^## \[[^\]]+\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    top = match.group(1) if match else ""
    released = re.search(
        rf"^## \[{re.escape(RELEASED)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    problems: list[str] = []
    for body, name in ((top, "the top section"), (released.group(1) if released else "", f"[{RELEASED}]")):
        headings = re.findall(r"^### (.+)$", body, re.MULTILINE)
        repeated = sorted({h for h in headings if headings.count(h) > 1})
        problems.extend(f"{name}: the heading '### {h}' appears twice" for h in repeated)
    if released:
        private = sorted(set(re.findall(r"`(_[A-Za-z0-9_.]+)", released.group(1))))
        problems.extend(f"[{RELEASED}]: an entry names {name}" for name in private)
    return problems


def test_record_is_consistent() -> None:
    """Scenarios "All eight items present" and "Limits and deferrals are named"."""
    assert record_problems(RECORD.read_text(encoding="utf-8"), version=fenolite.__version__) == []


def test_missing_proof_is_named() -> None:
    """Scenario "Missing proof"."""
    text = RECORD.read_text(encoding="utf-8").replace(
        "tests/kicad/acceptance/test_finished.py::test_check", "tests/kicad/acceptance/test_missing.py", 1
    )
    assert any("test_missing.py does not exist" in p for p in record_problems(text, version="0.0.1"))
    text = RECORD.read_text(encoding="utf-8").replace("::test_rebuild_is_the_identity", "::test_gone", 1)
    assert any("has no function test_gone" in p for p in record_problems(text, version="0.0.1"))


def test_pending_row_blocks_the_version() -> None:
    """Scenario "Pending row blocks the version"."""
    text = RECORD.read_text(encoding="utf-8")
    table = rows(text)
    first = table[0]
    line = (
        f"| {first['item']} | {first['statement']} | {first['proof']} | {first['job']} | {first['result']} |"
    )
    assert line in text
    pending = text.replace(line, line.rsplit("|", 2)[0] + "| pending |", 1)
    assert any("still pending" in p and "item 1" in p for p in record_problems(pending, version=RELEASED))


def test_schema_row_cannot_say_met() -> None:
    """Scenario "Schema row cannot say met"."""
    text = RECORD.read_text(encoding="utf-8")
    line = next(row for row in text.splitlines() if row.startswith("| 5 |") and "schemas" in row)
    changed = text.replace(line, line.rsplit("|", 2)[0] + "| met |")
    assert any(SCHEMA_SENTENCE in p for p in record_problems(changed, version="0.0.1"))


def test_item_2_limits_are_required() -> None:
    """Scenario "Item 2 limits required"."""
    text = RECORD.read_text(encoding="utf-8")
    assert "`not judged`" in text
    assert "item 2: the limit lacks 'not judged'" in record_problems(
        text.replace("`not judged`", "left open"), version="0.0.1"
    )


def test_rule_constructor_is_not_deferred() -> None:
    """Scenario "Rule constructor is not deferred"."""
    text = RECORD.read_text(encoding="utf-8").replace(
        "## Verdict", "| the DSL rule constructor | v0.2a |\n\n## Verdict"
    )
    assert any("rule constructor" in p for p in record_problems(text, version="0.0.1"))


def test_build_rule_is_stated() -> None:
    """Scenario "Record states the build rule"."""
    text = RECORD.read_text(encoding="utf-8")
    assert not [p for p in record_problems(text, version="0.0.1") if p.startswith("release build")]
    changed = text.replace("never from the working tree", "from a clean place")
    assert any(p.startswith("release build") for p in record_problems(changed, version="0.0.1"))


def test_history_row() -> None:
    """Scenarios "History row required" and "Row may not claim the private gate"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    only_old = "\n".join(line for line in text.splitlines() if "| v0.1.0 |" not in line)
    assert history_problems(only_old, version=RELEASED) == [f"{HISTORY.name}: no v0.1.0 row"]
    claimed = only_old + "\n| 2026-10-04 | v0.1.0 | root .. abc | all | 5 | on | 0 |\n"
    assert any("private gate column" in p for p in history_problems(claimed, version=RELEASED))


def test_changelog_section_is_clean() -> None:
    """Scenario "Changelog section is clean"."""
    assert changelog_problems(CHANGELOG.read_text(encoding="utf-8")) == []
    twice = "## [0.1.0] - 2026-10-05\n\n### Fixed\n\n- a\n\n### Fixed\n\n- b with `_private.name`\n"
    problems = changelog_problems(twice)
    assert any("appears twice" in p for p in problems) and any("_private.name" in p for p in problems)


def test_versions_agree() -> None:
    """Scenario "Versions agree": the package, its alias, the alias pin and the changelog."""
    alias = (ROOT / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    version = fenolite.__version__
    assert f'version = "{version}"' in alias and f"fenolite=={version}" in alias
    if version == RELEASED:
        headings = re.findall(r"^## \[([^\]]+)\]", CHANGELOG.read_text(encoding="utf-8"), re.MULTILINE)
        assert headings[:2] == ["Unreleased", RELEASED]


@pytest.mark.parametrize("result", RESULTS)
def test_results_are_the_four_words(result: str) -> None:
    assert result in RESULTS
