# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copyleft software is used only across a process boundary, never as a dependency (ADR-0004)."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Closed list of copyleft (GPL/AGPL/LGPL) or share-alike packages that must never be dependencies.
# Public statement of the process-boundary rule; extend it when a new neighbour appears.
COPYLEFT = {
    "altium-monkey",  # AGPL-3.0-or-later
    "altium-cruncher",  # AGPL-3.0
    "easyeda2kicad",  # AGPL-3.0
    "kiutils",  # GPL-3.0
    "kicad-skip",  # LGPL-2.1
    "kicad-library-tools",  # GPL-3.0-or-later
    "kicad-library-generators",  # GPL-3.0-or-later
    "kicadmodtree",  # GPL-3.0 fork of the footprint generator
    "cgal",  # GPL-3.0-or-later bindings
    "lcapy",  # LGPL-2.1
    "pyaltium",  # GPL-3.0
    "edea",  # EUPL-1.2
}


def _name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    assert match, requirement
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def declared_packages() -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    found = {_name(r): "dependencies" for r in project.get("dependencies", [])}
    for extra, requirements in project.get("optional-dependencies", {}).items():
        for requirement in requirements:
            found.setdefault(_name(requirement), f"extra '{extra}'")
    return found


def test_no_copyleft_dependency() -> None:
    bad = {name: where for name, where in declared_packages().items() if name in COPYLEFT}
    assert not bad, "copyleft packages must run as external processes, not dependencies: " + ", ".join(
        f"{name} ({where})" for name, where in sorted(bad.items())
    )


def test_name_normalisation() -> None:
    assert _name("KicadModTree>=1.1") == "kicadmodtree"
    assert _name("kicad_skip ; python_version>='3.11'") == "kicad-skip"
