# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The agent guide and the README stay true to the command line (capability release-gate, "Agent guide
is executable" and "README describes the released version"; changes c0025 and c0093)."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from fenolite.cli.api import discover
from fenolite.cli.errors import CliError
from fenolite.cli.main import build_parser

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "agent" / "SKILL.md"
README = ROOT / "README.md"
RELEASE = "0.2"
"""The version the README describes: the newest release record under ``docs/release/``."""
BLOCK = re.compile(r"^```fenolite-loop\n(.*?)^```$", re.MULTILINE | re.DOTALL)
TARGETS = ("examples/blink_2layer/design.py", "build/blink")


def loop_block(text: str) -> list[str]:
    """The lines of the one ``fenolite-loop`` block of ``text``."""
    blocks = BLOCK.findall(text)
    assert len(blocks) == 1, f"expected one fenolite-loop block, found {len(blocks)}"
    return [line for line in blocks[0].splitlines() if line.strip()]


def block_problems(lines: list[str]) -> list[str]:
    """Why the block is not a valid loop: an empty list when every line parses."""
    problems: list[str] = []
    if not 1 <= len(lines) <= 10:
        problems.append(f"{len(lines)} lines; the loop holds at most ten")
    parser = build_parser(discover())
    for line in lines:
        words = shlex.split(line)
        if not words or words[0] != "fenolite":
            problems.append(f"not a fenolite command: {line}")
            continue
        if words[1:2] != ["capabilities"] and not any(target in word for word in words for target in TARGETS):
            problems.append(f"names neither the example nor build/blink: {line}")
        try:
            parser.parse_args(words[1:])
        except CliError as error:
            problems.append(f"the parser refuses ({error.message}): {line}")
    return problems


def readme_problems(text: str) -> list[str]:
    """Why a README does not describe the released version."""
    problems = [
        f"holds the words {words!r}" for words in ("pre-alpha", "being bootstrapped") if words in text
    ]
    paragraph = re.search(r"^> \*\*Status:.*?(?=^[^>]|\Z)", text, re.MULTILINE | re.DOTALL)
    status = paragraph.group(0) if paragraph else ""
    if f"**Status: version {RELEASE}.**" not in status:
        problems.append(f"the status line does not name the version {RELEASE}")
    if f"docs/release/v{RELEASE}.md" not in status:
        problems.append(f"no link to docs/release/v{RELEASE}.md")
    if "experimental" not in status:
        problems.append("the status paragraph does not say what is experimental")
    install = re.search(r"^## Install\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL)
    if install is None or "pip install fenolite" not in install.group(1):
        problems.append("no 'pip install fenolite' under '## Install'")
    elif "no other package" not in install.group(1):
        problems.append("'## Install' does not say that no other package is installed")
    if re.search(r"byte[- ]identical", text, re.IGNORECASE):
        problems.append("claims byte identity; only tree identity is claimed (H-K-FMT-INDENT)")
    return problems


def test_skill_front_matter_and_size() -> None:
    text = SKILL.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == "---" and "---" in lines[1:]
    front = lines[1 : lines.index("---", 1)]
    assert any(line.startswith("name: ") for line in front)
    assert any(line.startswith("description: ") for line in front)
    assert len(lines) < 200


def test_skill_states_the_rules() -> None:
    text = SKILL.read_text(encoding="utf-8")
    for needed in ("capabilities` first", "--dry-run", "--confirm", "KICAD-VERIFIED", "unconfirmed"):
        assert needed in text, needed
    for code in range(8):
        assert re.search(rf"^\s*\| {code} \| ", text, re.MULTILINE), f"exit code {code} is not explained"


def test_block_parses() -> None:
    """Scenario "Block parses"."""
    lines = loop_block(SKILL.read_text(encoding="utf-8"))
    assert block_problems(lines) == []
    assert loop_block(README.read_text(encoding="utf-8")) == lines
    assert "agent/SKILL.md" in (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def test_a_stale_flag_fails() -> None:
    """Scenario "A stale flag fails"."""
    problems = block_problems(["fenolite route build/blink --engine x"])
    assert problems and "--engine" in problems[0]
    assert block_problems(["fenolite frobnicate build/blink"])
    assert block_problems(["kicad-cli pcb drc build/blink"])
    assert block_problems(["fenolite check build/blink"] * 11)


def test_guide_names_no_private_place() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert not re.search(r"/(Users|home)/|[A-Za-z]:\\\\Users", text)


def test_readme_describes_the_release() -> None:
    """Scenario "Status and install present"."""
    assert readme_problems(README.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("old", "new", "named"),
    [
        ("**Status: version 0.2.**", "**Status: pre-alpha.**", "pre-alpha"),
        ("**Status: version 0.2.**", "**Status: version 0.1.**", "version 0.2"),
        ("experimental", "new", "what is experimental"),
        ("pip install fenolite\n", "uv sync\n", "pip install fenolite"),
        ("`docs/release/v0.2.md`", "the release notes", "docs/release/v0.2.md"),
        ("It installs no other package.", "It is byte-identical to KiCad's own files.", "byte identity"),
    ],
)
def test_readme_stale_text_is_rejected(old: str, new: str, named: str) -> None:
    """Scenario "Stale status rejected"."""
    text = README.read_text(encoding="utf-8")
    assert old in text
    problems = readme_problems(text.replace(old, new))
    assert any(named in problem for problem in problems), problems
