# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The recovery recipes of the agent guide behave as written (capability agent-guide, "Recovery
recipes").

Each ``fenolite-recipe`` block of the page ``recovery`` is run line by line in its sandbox, in an empty
folder, with no external tool to find or to start: the exit code of every line and, where the line
names one, the code of the error object or of an issue are compared with what the page says.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from _sandbox import BAD_LIB_ID, SANDBOXES, SCRIPT_ERROR, STEP, inside, recipe_problems, run, starter_script

from fenolite.agent import guide

PAGE = "recovery"
NEEDED = {
    "FEN-4001": "starter",
    "FEN-2001": "starter",
    "FEN-3001": "bad-lib-id",
    "FEN-3004": "script-error",
    "copper.short": "crossed",
    "FEN-6001": "starter",
    "FEN-7001": "lossy",
}
"""The code each recipe of the requirement is about → its sandbox."""
SENTENCE_END = re.compile(r"[.:!?](?=\s|$)")


def recipes(page: guide.Page) -> list[guide.Block]:
    return [block for block in guide.blocks(page) if block.tag == "fenolite-recipe"]


def _first_code(block: guide.Block) -> str:
    """The first code that a line of the recipe names."""
    for line in block.lines:
        step = STEP.fullmatch(line.strip())
        if step is not None and step["code"] is not None:
            return step["code"]
    return ""


def form_problems(page: guide.Page) -> list[str]:
    """Why a recipe of ``page`` is not a heading that names its code, at most three sentences and one
    block."""
    rows = page.text.split("\n")
    problems: list[str] = []
    for block in recipes(page):
        where = f"{page.topic}: line {block.line_number}"
        start = max(i for i in range(block.line_number - 1) if rows[i].startswith("## "))
        code = _first_code(block)
        if not code or f"`{code}`" not in rows[start]:
            problems.append(f"{where}: the heading {rows[start]!r} does not name the code {code!r}")
        between, fenced = [], False
        for row in rows[start + 1 : block.line_number - 1]:
            if row.strip().startswith(guide.FENCE):
                fenced = not fenced
            elif not fenced:
                between.append(re.sub(r"`[^`]*`", "x", row))
        sentences = len(SENTENCE_END.findall(" ".join(between)))
        if not 1 <= sentences <= 3:
            problems.append(f"{where}: {sentences} sentences before the block; a recipe has at most three")
        if any(
            other.line_number > start and other.line_number < block.line_number for other in recipes(page)
        ):
            problems.append(f"{where}: a second recipe under one heading")
    return problems


RECIPES = [
    pytest.param(block, id=f"{block.argument}:{_first_code(block)}:{block.line_number}")
    for block in recipes(guide.page(PAGE))
]


@pytest.mark.parametrize("block", RECIPES)
def test_recipes_behave_as_written(block: guide.Block, tmp_path: Path, no_tools: None) -> None:
    """Scenario "Recipes behave as written"."""
    assert recipe_problems(block, tmp_path / "sandbox") == []


def test_recipes_of_the_requirement_are_on_the_page() -> None:
    """The seven recipes exist, each in its sandbox, and each is a heading, at most three sentences and
    one block."""
    page = guide.page(PAGE)
    found = {_first_code(block): block.argument for block in recipes(page)}
    assert found == NEEDED
    assert form_problems(page) == []
    long = page.text.replace(
        "Look at the plan, then\nconfirm.", "Look at it. Think. Then confirm. Then go on."
    )
    assert long != page.text
    assert any("5 sentences" in problem for problem in form_problems(dataclasses.replace(page, text=long)))
    renamed = page.text.replace("## Exit 4, `FEN-4001`", "## Exit 4")
    assert any(
        "does not name the code 'FEN-4001'" in p
        for p in form_problems(dataclasses.replace(page, text=renamed))
    )
    for block in recipes(page):
        for line in block.lines:
            assert STEP.fullmatch(line.strip()) is not None, line


def test_recipes_show_the_lines_that_differ() -> None:
    """The two lines that the page shows for a broken and a fixed script are those of the sandboxes."""
    text = guide.page(PAGE).text
    for fixed, broken in (BAD_LIB_ID, SCRIPT_ERROR):
        assert f"broken:  {broken}\nfixed:   {fixed}\n" in text
        assert fixed in starter_script() and broken not in starter_script()


def test_crossed_tracks_are_repaired(tmp_path: Path, no_tools: None) -> None:
    """Scenario "Crossed tracks are repaired"."""
    block = next(block for block in recipes(guide.page(PAGE)) if block.argument == "crossed")
    steps = [STEP.fullmatch(line.strip()) for line in block.lines]
    assert all(step is not None for step in steps)
    checks = [step for step in steps if step is not None and " check " in step["command"]]
    assert [(step["exit"], step["code"]) for step in checks] == [("5", "copper.short"), ("0", None)]
    assert "fenolite explain copper.short --json" in [step["command"] for step in steps if step is not None]
    commands = " ".join(step["command"] for step in steps if step is not None)
    assert "place blink/build --move" in commands and "--rip" in commands
    assert steps.index(checks[0]) < steps.index(checks[1])
    folder = tmp_path / "sandbox"
    SANDBOXES["crossed"](folder)
    with inside(folder):
        assert run("fenolite build blink/design.py --out blink/build --confirm --json").code == 0
        assert run("fenolite route blink/build --router direct --confirm --json").code == 0
        before = run(checks[0]["command"])
        assert before.code == 5 and "copper.short" in before.codes()
        assert before.error is not None and before.error["code"] == "FEN-5001"
    assert recipe_problems(block, tmp_path / "again") == []


def test_script_error_is_located_by_its_line(tmp_path: Path, no_tools: None) -> None:
    """The error object of a script that raises ends with ``line:<n>``, the line that the sandbox broke."""
    folder = tmp_path / "sandbox"
    SANDBOXES["script-error"](folder)
    script = (folder / "broken" / "design.py").read_text(encoding="utf-8").split("\n")
    with inside(folder):
        outcome = run("fenolite build broken/design.py --out broken/build --confirm --json")
    assert outcome.code == 3 and outcome.error is not None and outcome.error["code"] == "FEN-3004"
    assert outcome.error["where"].endswith(f"design.py:line:{script.index(SCRIPT_ERROR[1]) + 1}")
    assert "line:N" in guide.page(PAGE).text


def test_runner_sandboxes(tmp_path: Path) -> None:
    """Every sandbox prepares a folder, and an unknown one fails."""
    assert set(SANDBOXES) == {"starter", "bad-lib-id", "script-error", "crossed", "lossy"}
    for name, prepare in SANDBOXES.items():
        folder = tmp_path / name
        prepare(folder)
        scripts = sorted(path.relative_to(folder).as_posix() for path in folder.rglob("design.py"))
        assert scripts in (["blink/design.py"], ["broken/design.py", "fixed/design.py"]), name
        for path in folder.rglob("design.py"):
            assert path.read_text(encoding="utf-8").startswith("# SPDX-License-Identifier: CC0-1.0\n")
    assert (tmp_path / "starter" / "blink" / "design.py").read_text(encoding="utf-8") == starter_script()
    assert (tmp_path / "bad-lib-id" / "fixed" / "design.py").read_text(encoding="utf-8") == starter_script()
    block = guide.Block("fenolite-recipe", "nowhere", ("fenolite guide --json  # exit 0",), 7)
    assert recipe_problems(block, tmp_path / "unknown") == [
        "line 7: unknown sandbox 'nowhere'; the sandboxes are " + ", ".join(SANDBOXES)
    ]
    assert not (tmp_path / "unknown").exists()
    assert recipe_problems(guide.Block("fenolite-recipe", "starter", (), 3), tmp_path / "empty") == [
        "line 3: the recipe holds no command"
    ]


def test_runner_reports_a_malformed_line(tmp_path: Path, no_tools: None) -> None:
    """A line without its exit code stops the recipe, and a missing code is named."""
    block = guide.Block("fenolite-recipe", "starter", ("fenolite guide --json",), 3)
    assert recipe_problems(block, tmp_path / "a") == [
        "line 4: not '<command>  # exit N[, has <code>]': fenolite guide --json"
    ]
    line = "fenolite build blink/design.py --out blink/build --json  # exit 4, has FEN-7001"
    problems = recipe_problems(guide.Block("fenolite-recipe", "starter", (line,), 3), tmp_path / "b")
    assert problems == [f"line 4: no FEN-7001 among ['FEN-4001']: {line.split('  #')[0]}"]


def test_a_recipe_that_lies_fails(tmp_path: Path, no_tools: None) -> None:
    """Scenario "A recipe that lies fails"."""
    page = guide.page(PAGE)
    honest = "fenolite build blink/design.py --out blink/build --json  # exit 4, has FEN-4001"
    assert page.text.count(honest) == 1
    lying = dataclasses.replace(page, text=page.text.replace(honest, honest.split("  #")[0] + "  # exit 0"))
    first = recipes(lying)[0]
    assert first.argument == "starter" and first.lines[0].endswith("# exit 0")
    assert recipe_problems(first, tmp_path / "sandbox") == [
        f"line {first.line_number + 1}: exit code 0 expected, 4 found: {honest.split('  #')[0]}"
    ]
    assert recipe_problems(recipes(page)[0], tmp_path / "honest") == []
