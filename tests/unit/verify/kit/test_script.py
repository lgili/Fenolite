# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit script (capability altium-verification, "Kit script")."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pytest
from _simulate import simulate, simulated_judge

from fenolite.core.io import sha256_bytes
from fenolite.verify.kit import script
from fenolite.verify.kit.manifest import load_kit
from fenolite.verify.kit.results import verify_results
from fenolite.verify.kit.steps import STEPS

ROOT = Path(__file__).resolve().parents[4]
SOURCES = (ROOT / "docs" / "evidence" / "sources.md").read_text(encoding="utf-8")
PAGE = (ROOT / "docs" / "altium-kit.md").read_text(encoding="utf-8")


def test_script_and_steps_agree() -> None:
    """Scenario "Script and steps agree": one block per scripted step, in step order, none for a form
    step."""
    text = script.script_text()
    scripted = [step.id for step in STEPS if step.scripted]
    assert list(script.block_ids(text)) == scripted and scripted
    assert all(step.kind == "file" for step in script.scripted_steps())
    for step in STEPS:
        assert (f"'{step.id}'" in text) is step.scripted
    fewer = script.script_text([step for step in STEPS if step.id != scripted[0]])
    assert list(script.block_ids(fewer)) == scripted[1:]


def test_only_documented_calls() -> None:
    """Scenario "Only documented calls": every name of the script is a listed call with a registered
    source, a listed keyword, or a name the script declares."""
    text = script.script_text()
    assert script.undocumented_names(text) == ()
    used = {name.casefold() for name in script.used_names(text)}
    assert {name.casefold() for name in script.SCRIPT_CALLS} <= used
    for source in {*script.SCRIPT_CALLS.values(), script.KEYWORD_SOURCE}:
        assert re.search(
            rf"^\| {source} \| https://www\.altium\.com/documentation/", SOURCES, re.MULTILINE
        ), source
    assert script.undocumented_names(text + "\r\nClient.OpenDocument('PCB', X);") == (
        "Client",
        "OpenDocument",
        "X",
    )


def test_the_page_shows_every_call() -> None:
    for name, source in script.SCRIPT_CALLS.items():
        assert re.search(rf"\| `{name}` \|[^\n]*{source}", PAGE), name
    for what in script.NOT_SCRIPTED:
        assert what in PAGE, what


def test_the_script_writes_only_under_results() -> None:
    text = script.script_text()
    assert text.isascii() and "\r\n" in text and "\n" not in text.replace("\r\n", "")
    written = re.findall(r"AssignFile\(F, ([^)]*)\)", text)
    assert written and all(target.startswith("Root + 'results\\") for target in written)
    for forbidden in ("RunProcess", "DoFileSave", "SetFileName", "OpenDocument", "DM_OpenProject", "Erase"):
        assert forbidden not in text
    assert f"Procedure {script.PROCEDURE};" in text


def test_a_step_that_is_not_a_compile_step_is_refused() -> None:
    typed = next(step for step in STEPS if step.kind == "form")
    with pytest.raises(ValueError, match="compile step"):
        script.script_text([dataclasses.replace(typed, scripted=True)])


def test_the_script_is_in_the_manifest(built_kit: Path) -> None:
    kit = load_kit(built_kit)
    data = (built_kit / script.SCRIPT_NAME).read_bytes()
    assert data == script.script_text().encode("ascii")
    assert kit.script_sha256 == sha256_bytes(data) == kit.files[script.SCRIPT_NAME]
    assert kit.data["script"]["calls"] == dict(sorted(script.SCRIPT_CALLS.items()))


def test_log_outcomes() -> None:
    log = "K2.1 done\nnoise\nK2.2 error: the project was not compiled\nK2.1 done\n\n"
    assert script.log_outcomes(log) == {"K2.1": "done", "K2.2": "error: the project was not compiled"}


def test_a_manual_run_still_passes(kit: Path) -> None:
    """Scenario "Manual run still passes": without ``script.log`` every step passes and none is marked
    scripted; the script's own row is then not settled."""
    simulate(kit)
    verdict = verify_results(kit, judge=simulated_judge)
    assert [step.id for step in verdict.steps if step.outcome != "pass"] == []
    assert not any(step.scripted for step in verdict.steps)
    assert {h.id: h.outcome for h in verdict.hypotheses}["H-A-KIT-SCRIPT"] == "skipped"


def test_a_scripted_run(kit: Path) -> None:
    simulate(kit, script=True)
    verdict = verify_results(kit, judge=simulated_judge)
    assert [step.id for step in verdict.steps if step.outcome != "pass"] == []
    assert [step.id for step in verdict.steps if step.scripted] == [
        step.id for step in STEPS if step.scripted
    ]
    assert {h.id: h.outcome for h in verdict.hypotheses}["H-A-KIT-SCRIPT"] == "pass"


def test_the_script_says_how_its_calls_were_read() -> None:
    """Every source of a call has its page, and the script tells its reader to compile it first."""
    from fenolite.verify.kit.script import KEYWORD_SOURCE, READ_AS, SCRIPT_CALLS, SOURCE_PAGES, script_text
    from fenolite.verify.kit.steps import STEPS, steps_markdown

    assert set(SOURCE_PAGES) == {*SCRIPT_CALLS.values(), KEYWORD_SOURCE}
    assert READ_AS.startswith("read as rendered on 2026-10-06")
    head = script_text(STEPS).split("Function", 1)[0]
    assert "text rendering" in head and "compile it" in head and "has not run in Altium" in head
    assert "compile it" in steps_markdown()


def test_the_script_names_the_documentation_version_and_the_version_of_the_first_run() -> None:
    """No registered page states the version of Altium Designer it describes, and the script says so,
    with the version it runs on first (change c0139)."""
    from fenolite.verify.kit.script import FIRST_RUN_ON, PAGE_VERSIONS, READ_AS, SOURCE_PAGES, script_text

    assert FIRST_RUN_ON == "Altium Designer 26" and FIRST_RUN_ON in READ_AS
    assert "no page states the version" in READ_AS
    assert set(PAGE_VERSIONS) == set(SOURCE_PAGES)
    for source, page in SOURCE_PAGES.items():
        family = "Altium DXP Developer" if page.startswith("altium-dxp-developer/") else "Altium Designer"
        assert PAGE_VERSIONS[source].startswith(family + " documentation"), source
        assert "26" not in PAGE_VERSIONS[source]
    head = script_text().split("Function", 1)[0]
    assert "states the version of Altium Designer" in head and "on Altium Designer 26." in head
    assert all(line.startswith("{ ") and line.endswith("}") for line in head.strip().splitlines())
    page = (ROOT / "docs" / "altium-kit.md").read_text(encoding="utf-8")
    assert "first run of the script is on Altium Designer 26" in page
