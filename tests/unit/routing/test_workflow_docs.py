# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The published completion recipe parses and keeps post-fill checks ahead of output (c0370)."""

import re
import shlex
from pathlib import Path

from fenolite.agent import guide
from fenolite.cli.api import discover
from fenolite.cli.main import build_parser

ROOT = Path(__file__).resolve().parents[3]


def recipe():
    page = guide.page("board-completion").text
    section = page.split("## Reviewed routing completion recipe", 1)[1].split("## What the proposal run", 1)[
        0
    ]
    block = re.search(r"```fenolite-cmd\n(.*?)```", section, re.S)
    assert block is not None
    return section, [shlex.split(line)[1:] for line in block[1].splitlines() if line.strip()]


def test_documented_recipe_is_executable_and_keeps_reviewed_stages_in_order():
    section, commands = recipe()
    parser = build_parser(discover())
    for command in commands:
        parser.parse_args(command)
    assert [c[0] for c in commands] == [
        "capabilities",
        "roles",
        "route",
        "copper",
        "route",
        "tidy",
        "fill",
        "net",
        "check",
        "export",
        "render",
    ]
    assert "--roles" in commands[2] and "critical" in commands[2]
    assert "--propose" in commands[4] and "--confirm" not in commands[4]
    assert "--nets" in commands[5] and "SIG" in commands[5]
    for command in (commands[2], commands[3], *commands[5:7], *commands[9:]):
        assert "--dry-run" in command and "--confirm" not in command
    for phrase in (
        "explicitly accept",
        "post-fill connectivity",
        "unattempted subjects",
        "unknown checks",
        "separate transactions",
        "manual/locked copper",
        "not native validation",
    ):
        assert phrase in section


def test_roles_and_roadmap_distinguish_phases_from_execution_without_old_recipe():
    roles = (ROOT / "docs/roles.md").read_text(encoding="utf-8")
    roadmap = (ROOT / "docs/router-roadmap.md").read_text(encoding="utf-8")
    assert "Phase 1 (`design.role_copper()`" not in roles
    assert "Development phase numbers are not a board recipe" in roles
    assert "route critical" in roles and "explicitly accept ordinary alternatives" in roles
    execution = roadmap.split("## Per-board execution order", 1)[1].split("## Boundaries", 1)[0]
    assert execution.index("Route critical") < execution.index("Generate power/ground")
    assert execution.index("scoped tidy") < execution.index("Fill, check")
