# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What KiCad's own checks say about the design scripts of the agent guide (capability agent-guide,
"Guide pages": a page states only what a run shows).

The pages say which findings ``fenolite check`` still reports for their scripts: an unrouted board has
open connections, a regulator fed by a connector has undriven supply pins, a part with free pins has
unconnected pins. These tests run the whole check with ``kicad-cli`` 10 and compare the codes of the
errors with what the pages say, so that a script cannot start to fail for another reason unnoticed.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from _sandbox import inside, run

from fenolite.agent import guide

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]

OPEN = "kicad.drc.unconnected-items"
ERRORS: dict[tuple[str, int], set[str]] = {
    ("design-script", 0): {OPEN},
    ("footprints", 0): {OPEN},
    ("parts", 0): {OPEN, "kicad.erc.power-pin-not-driven"},
    ("parts", 1): {OPEN, "kicad.erc.pin-not-connected"},
    ("placement", 0): {OPEN},
    ("routing", 0): {OPEN},
    ("rules", 0): {OPEN},
}
"""(topic, index of the KiCad design block on its page) → the codes of the errors that the whole check
reports for the script as it is built, before any routing."""
SAID = {
    "design-script": ("`kicad.drc.unconnected-items`",),
    "parts": ("`kicad.erc.power-pin-not-driven`", "`kicad.erc.pin-not-connected`"),
    "routing": ("exits 0",),
}
"""Topic → what its page says about those findings."""


def _blocks() -> dict[tuple[str, int], guide.Block]:
    found: dict[tuple[str, int], guide.Block] = {}
    for page in guide.pages():
        kicad = [b for b in guide.blocks(page) if b.tag == "fenolite-design" and not b.argument]
        found.update({(page.topic, index): block for index, block in enumerate(kicad)})
    return found


def _build(block: guide.Block, folder: Path) -> None:
    folder.mkdir(parents=True)
    script = textwrap.dedent("\n".join(block.lines)) + "\n"
    (folder / "design.py").write_text(script, encoding="utf-8", newline="\n")
    with inside(folder):
        assert run("fenolite build design.py --out out --kicad-version 10 --confirm --json").code == 0


def _errors(folder: Path) -> tuple[int, set[str]]:
    with inside(folder):
        outcome = run("fenolite check out --json")
    assert outcome.envelope is not None, outcome.error
    return outcome.code, {i["code"] for i in outcome.envelope["issues"] if i["severity"] == "error"}


def test_kicad_table_names_every_design_block() -> None:
    assert set(ERRORS) == set(_blocks())
    for topic, words in SAID.items():
        for needed in words:
            assert needed in guide.page(topic).text, f"{topic}: {needed}"


@pytest.mark.parametrize("key", sorted(ERRORS), ids=lambda key: f"{key[0]}:{key[1]}")
def test_kicad_check_reports_what_the_page_says(key: tuple[str, int], tmp_path: Path) -> None:
    """The whole check of each script, as built, gives exactly the errors of ``ERRORS``."""
    _build(_blocks()[key], tmp_path / "work")
    assert _errors(tmp_path / "work") == (5, ERRORS[key])


def test_kicad_routed_script_passes_after_fill(tmp_path: Path) -> None:
    """The script of the page ``routing`` declares all its copper: after ``fill`` the check exits 0."""
    folder = tmp_path / "work"
    _build(_blocks()[("routing", 0)], folder)
    with inside(folder):
        assert run("fenolite fill out --confirm --json").code == 0
    assert _errors(folder) == (0, set())
