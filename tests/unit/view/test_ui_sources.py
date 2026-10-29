# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sources of the viewer page (change c0245, decision 13; board-viewer, "Viewer page", scenario
"Assembly from the UI sources")."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from fenolite.view import export

UI = Path(export.__file__).resolve().parent / "ui"


def test_assembly() -> None:
    """Scenario "Assembly from the UI sources": twice the same page, every file of ui/ once."""
    first, second = export.template(), export.template()
    assert first == second
    files = sorted(p.relative_to(UI).as_posix() for p in UI.rglob("*") if p.is_file())
    assert sorted(export.PARTS) == files
    assert len(set(export.PARTS)) == len(export.PARTS)
    assert first.startswith("<!doctype html>") and first.rstrip().endswith("</html>")
    assert first.count("<script>") == 1 and first.count("</script>") == 1
    assert "http://" not in first.replace('["http:", "", "www.w3.org"', "")


def test_parts_end_with_a_newline() -> None:
    for part in export.PARTS:
        assert (UI / part).read_text(encoding="utf-8").endswith("\n"), part


def _scripts() -> dict[str, str]:
    return {part: (UI / part).read_text(encoding="utf-8") for part in export.PARTS if part.endswith(".js")}


MODAL = re.compile(r"\b(?:window\.)?(?:alert|confirm|prompt)\s*\(")
CATALOG = "panels/catalog.js"
"""The catalog selection of c0240 keeps its modal dialog: it is a separate catalog mode, not a routine action
of the viewer (design, decision 9, M4)."""


def test_modal() -> None:
    """M4: no alert, confirm or prompt, and a modal dialog only in the catalog selection."""
    for part, text in _scripts().items():
        assert not MODAL.search(text), f"{part}: {MODAL.search(text)}"
        if part != CATALOG:
            assert "showModal(" not in text, part


COMMAND = re.compile(
    r'command\(\{ id: "([a-z0-9.-]+)", menu: "([A-Za-z]+)",(?: group: "[a-z-]*",)?(?: sub: "[^"]+",)?'
    r' label: "([^"]+)"'
)


def test_registry() -> None:
    """M9: every registered command has an id, a menu of the menu bar and a label; the markup holds no
    menu item of its own (the menus are generated from the registry)."""
    registry = (UI / "shell" / "registry.js").read_text(encoding="utf-8")
    menus = re.search(r"const MENUS = \[([^\]]+)\]", registry)
    assert menus
    names = re.findall(r'"([A-Za-z]+)"', menus.group(1))
    assert names == [
        "File",
        "Edit",
        "View",
        "Place",
        "Design",
        "Roles",
        "Route",
        "Tools",
        "Reports",
        "Window",
        "Help",
    ]
    calls = [
        line for text in _scripts().values() for line in text.splitlines() if line.startswith("command({")
    ]
    assert len(calls) >= 18
    ids = []
    for line in calls:
        found = COMMAND.match(line)
        assert found, line
        ids.append(found.group(1))
        assert found.group(2) in names, line
    assert len(ids) == len(set(ids))
    for part in export.PARTS:
        if part.endswith(".html"):
            assert 'role="menuitem' not in (UI / part).read_text(encoding="utf-8"), part


def test_the_page_script_parses(tmp_path: Path) -> None:
    """The joined script is valid JavaScript (node --check), so a slip in one part cannot stop the page."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    page = export.template()
    script = tmp_path / "page.js"
    script.write_text(page[page.index("<script>") + 8 : page.index("</script>")], encoding="utf-8")
    done = subprocess.run(
        [node, "--check", str(script)], capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stderr
