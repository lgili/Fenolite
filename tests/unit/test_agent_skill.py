# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The agent guide and the README stay true to the command line (capability release-gate, "Agent guide
is executable" and "README describes the released version"; capability agent-guide, "Start page";
changes c0025, c0079 and c0093)."""

from __future__ import annotations

import io
import json
import re
import shlex
import subprocess
from pathlib import Path

import pytest

from fenolite.cli.api import discover
from fenolite.cli.errors import CliError
from fenolite.cli.main import build_parser, main

ROOT = Path(__file__).resolve().parents[2]
GUIDE_PATH = "src/fenolite/agent/skill/SKILL.md"
SKILL = ROOT / GUIDE_PATH
README = ROOT / "README.md"
RELEASE = "0.3"
"""The version the README describes: the newest release record under ``docs/release/``."""
BLOCK = re.compile(r"^```fenolite-loop\n(.*?)^```$", re.MULTILINE | re.DOTALL)
PROJECT = "blink"
"""The folder that the second line of the block makes; every later line works inside it."""
ORDER = (
    ("capabilities", "--brief"),
    ("init", PROJECT),
    ("build", "--dry-run"),
    ("build", "--confirm"),
    ("place", ""),
    ("route", "--router direct"),
    ("fill", ""),
    ("check", ""),
    ("export", ""),
    ("render", ""),
)
"""The commands of the block in order, each with words its line must hold."""
HERMETIC_LINES = 6
"""The lines up to ``route``: they run without any tool."""
KEPT_COMMANDS = (
    "build", "capabilities", "check", "diff", "doctor", "explain", "export", "fill", "fmt", "inspect", "kit",
    "manifest", "neighbors", "net", "netlist", "pads", "place", "region", "render", "restore", "roundtrip",
    "route",
)  # fmt: skip
"""The 22 public commands that the guide named at the commit before it moved into the package."""
NEW_COMMANDS = ("guide", "skill", "init")
STATEMENTS = (
    "fenolite capabilities --brief --json` first",
    "fenolite guide <topic> --text",
    "--dry-run",
    "--confirm",
    "KICAD-VERIFIED",
    "unconfirmed",
    "One fix per iteration",
    "fenolite check",
    "result.matrix",
    "belong to the\ninstalled version",
    "names the version it came from",
    "The Altium verification kit (`fenolite kit`) is a run that a person performs in Altium Designer",
    "changes nothing here",
)
"""What the start page must state (agent-guide, "Start page")."""


def loop_block(text: str) -> list[str]:
    """The lines of the one ``fenolite-loop`` block of ``text``."""
    blocks = BLOCK.findall(text)
    assert len(blocks) == 1, f"expected one fenolite-loop block, found {len(blocks)}"
    return [line for line in blocks[0].splitlines() if line.strip()]


def block_problems(lines: list[str]) -> list[str]:
    """Why the block is not a valid loop: an empty list when every line parses and names the project."""
    problems: list[str] = []
    if not 1 <= len(lines) <= 10:
        problems.append(f"{len(lines)} lines; the loop holds at most ten")
    parser = build_parser(discover())
    for line in lines:
        words = shlex.split(line)
        if not words or words[0] != "fenolite":
            problems.append(f"not a fenolite command: {line}")
            continue
        inside = any(word == f"{PROJECT}/design.py" or word.startswith(f"{PROJECT}/") for word in words)
        if words[1:2] not in (["capabilities"], ["init"]) and not inside:
            problems.append(f"names neither {PROJECT}/design.py nor a folder under {PROJECT}/: {line}")
        try:
            parser.parse_args(words[1:])
        except CliError as error:
            problems.append(f"the parser refuses ({error.message}): {line}")
    return problems


def order_problems(lines: list[str]) -> list[str]:
    """Why the block is not the loop of the release gate: the commands of ``ORDER``, in that order."""
    problems: list[str] = []
    if len(lines) != len(ORDER):
        problems.append(f"{len(lines)} lines; the loop has {len(ORDER)} commands")
    for number, (line, (command, needed)) in enumerate(zip(lines, ORDER, strict=False), start=1):
        words = shlex.split(line)
        if words[1:2] != [command] or needed not in " ".join(words[2:]):
            problems.append(f"line {number} is not '{command} {needed}'".rstrip() + f": {line}")
    return problems


def rules_problems(text: str) -> list[str]:
    """What the start page does not state, and what it must not hold."""
    problems = [f"does not state {needed!r}" for needed in STATEMENTS if needed not in text]
    problems += [
        f"exit code {code} is not explained"
        for code in range(8)
        if not re.search(rf"^\s*\| {code} \| ", text, re.MULTILINE)
    ]
    if len(text.splitlines()) >= 200:
        problems.append(f"{len(text.splitlines())} lines; the page stays under 200")
    if re.search(r"/(Users|home)/|[A-Za-z]:\\\\Users", text):
        problems.append("names a private path")
    return problems


def missing_commands(text: str) -> list[str]:
    """The commands of ``KEPT_COMMANDS`` and ``NEW_COMMANDS`` that the page no longer names."""
    return [
        name
        for name in (*KEPT_COMMANDS, *NEW_COMMANDS)
        if re.search(rf"\bfenolite {re.escape(name)}\b", text) is None
    ]


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
    assert sorted(line.split(":", 1)[0] for line in front) == ["description", "name"]
    assert len(lines) < 200


def test_start_page_states_the_rules() -> None:
    """Scenario "Start page states the rules"."""
    text = SKILL.read_text(encoding="utf-8")
    assert rules_problems(text) == []
    assert rules_problems(text.replace("| 6 | an external tool", "| six | an external tool")) == [
        "exit code 6 is not explained"
    ]
    assert rules_problems(text.replace("One fix per iteration", "Several fixes")) == [
        "does not state 'One fix per iteration'"
    ]
    assert "names a private path" in rules_problems(text + "\nsee /" + "home" + "/someone/notes\n")
    assert any("under 200" in problem for problem in rules_problems(text + "\n" * 200))


def test_start_page_gives_no_fixed_status_for_the_altium_target() -> None:
    """The status of an Altium write kind is read in ``result.matrix``; the page states none itself."""
    text = SKILL.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "altium" in line.lower():
            assert not re.search(r"experimental|INFERRED|VERIFIED|unverified|stable", line), line
    assert "fenolite fetch freerouting --confirm" in text  # change c0078
    assert "check.report-limit" in text and "--require-complete" in text  # changes c0141 and c0108


def test_commands_kept() -> None:
    """Scenario "No command is lost"."""
    text = SKILL.read_text(encoding="utf-8")
    assert len(KEPT_COMMANDS) == 22 and set(KEPT_COMMANDS) <= set(discover())
    assert missing_commands(text) == []
    assert missing_commands(text.replace("fenolite roundtrip", "fenolite round-trip")) == ["roundtrip"]
    assert missing_commands(text.replace("fenolite net ", "fenolite nets ")) == ["net"]


def test_block_parses() -> None:
    """Scenario "Block parses"."""
    lines = loop_block(SKILL.read_text(encoding="utf-8"))
    assert block_problems(lines) == []
    assert order_problems(lines) == []
    assert loop_block(README.read_text(encoding="utf-8")) == lines
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert GUIDE_PATH in agents and "fenolite guide" in agents
    assert GUIDE_PATH in README.read_text(encoding="utf-8") and "fenolite guide" in README.read_text(
        encoding="utf-8"
    )


def test_a_stale_flag_fails() -> None:
    """Scenario "A stale flag fails"."""
    problems = block_problems(["fenolite route blink/build --engine x"])
    assert problems and "--engine" in problems[0]
    assert block_problems(["fenolite frobnicate blink/build"])
    assert block_problems(["kicad-cli pcb drc blink/build"])
    assert block_problems(["fenolite check blink/build"] * 11)
    assert block_problems(["fenolite check build/blink"]) == [
        "names neither blink/design.py nor a folder under blink/: fenolite check build/blink"
    ]


def test_a_changed_order_fails() -> None:
    lines = loop_block(SKILL.read_text(encoding="utf-8"))
    swapped = [*lines[:4], lines[5], lines[4], *lines[6:]]
    assert len(order_problems(swapped)) == 2
    assert order_problems(lines[:-1]) == ["9 lines; the loop has 10 commands"]
    freerouting = [line.replace("--router direct", "--router freerouting") for line in lines]
    assert order_problems(freerouting) == [f"line 6 is not 'route --router direct': {freerouting[5]}"]
    assert order_problems([lines[0].replace(" --brief", ""), *lines[1:]])


def test_hermetic_prefix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "First six lines need no tool": the lines up to ``route`` run in an empty folder with
    subprocess creation patched to raise."""
    from fenolite.backends.kicad import cli as kicad_cli
    from fenolite.cli import cmd_capabilities

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("the loop's first lines started a subprocess")

    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    for name in ("FENOLITE_KICAD_CLI", "FENOLITE_FREEROUTING_JAR", "FENOLITE_FREEROUTING_IMAGE",
                 "FENOLITE_JAVA", "FENOLITE_KRT"):  # fmt: skip
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    cmd_capabilities.detect_tools.cache_clear()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    lines = loop_block(SKILL.read_text(encoding="utf-8"))
    assert shlex.split(lines[HERMETIC_LINES - 1])[1] == "route"
    envelopes: list[dict[str, object]] = []
    try:
        for line in lines[:HERMETIC_LINES]:
            out, err = io.StringIO(), io.StringIO()
            monkeypatch.setattr("sys.stdout", out)
            monkeypatch.setattr("sys.stderr", err)
            code = main(shlex.split(line)[1:])
            assert code == 0, f"{line}\n{err.getvalue()}"
            envelope = json.loads(out.getvalue())
            assert envelope["evidence"]["level"], line
            envelopes.append(envelope)
    finally:
        cmd_capabilities.detect_tools.cache_clear()
    assert (work / PROJECT / "build" / f"{PROJECT}.kicad_pcb").is_file()
    route = envelopes[-1]["result"]
    assert isinstance(route, dict) and route["unrouted"] == [] and len(route["routed"]) == 3
    built = envelopes[3]["result"]
    assert isinstance(built, dict) and built["staged"] == []


def test_guide_names_no_private_place() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert not re.search(r"/(Users|home)/|[A-Za-z]:\\\\Users", text)


def test_readme_describes_the_release() -> None:
    """Scenario "Status and install present"."""
    assert readme_problems(README.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("old", "new", "named"),
    [
        ("**Status: version 0.3.**", "**Status: pre-alpha.**", "pre-alpha"),
        ("**Status: version 0.3.**", "**Status: version 0.2.**", "version 0.3"),
        ("experimental", "new", "what is experimental"),
        ("pip install fenolite\n", "uv sync\n", "pip install fenolite"),
        ("`docs/release/v0.3.md`", "the release notes", "docs/release/v0.3.md"),
        ("It installs no other package.", "It is byte-identical to KiCad's own files.", "byte identity"),
    ],
)
def test_readme_stale_text_is_rejected(old: str, new: str, named: str) -> None:
    """Scenario "Stale status rejected"."""
    text = README.read_text(encoding="utf-8")
    assert old in text
    problems = readme_problems(text.replace(old, new))
    assert any(named in problem for problem in problems), problems
