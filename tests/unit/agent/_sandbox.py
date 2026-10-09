# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the guide tests share (capability agent-guide, "Executable blocks" and "Recovery recipes"): the
sandboxes that the recipes of the page ``recovery`` run in, a way to run one command line in this
process, and the fence that keeps every run away from external tools.

A sandbox is a small project made in code from the starter ``blink``: no file under ``tests/data``
belongs to it. Where a recipe has to edit a script, the sandbox holds two folders, ``broken/`` and
``fixed/``, because a recipe cannot edit a file.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shlex
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from fenolite.agent import guide
from fenolite.cli.main import main

STARTER = "blink"
TOOL_VARIABLES = (
    "FENOLITE_KICAD_CLI",
    "FENOLITE_FREEROUTING_JAR",
    "FENOLITE_FREEROUTING_IMAGE",
    "FENOLITE_JAVA",
    "FENOLITE_KRT",
    "FENOLITE_LIBS_CACHE",
)
"""The variables that name a tool, a jar or a library cache; a sandbox clears them."""

BAD_LIB_ID = (
    'r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="330")',
    'r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0630", value="330")',
)
SCRIPT_ERROR = ("d1.place(mm(15), mm(6), rot=180)", "d1.place(15, mm(6), rot=180)")
"""The fixed line of the starter and its broken form, for the sandboxes ``bad-lib-id`` and
``script-error``; the page ``recovery`` shows both pairs."""
_R1_PLACE = ("r1.place(mm(15), mm(14))", "r1.place(mm(15), mm(6))")
_D1_PLACE = ("d1.place(mm(15), mm(6), rot=180)", "d1.place(mm(15), mm(14), rot=180)")
_IMPORT = (
    "from fenolite.dsl import Design, Net, Part, connect, mm",
    "from fenolite.dsl import Design, Net, Part, connect, mm, select",
)
_CREEPAGE = (
    'design.rules.rule("creep", "creepage", where=select.net(vin), between=select.net(gnd), min=mm(1))\n'
)


def starter_script() -> str:
    """The design script that ``fenolite init blink`` writes."""
    return guide.render_starter(STARTER, STARTER)["design.py"].decode("utf-8")


def _swap(text: str, pair: tuple[str, str]) -> str:
    old, new = pair
    assert text.count(old) == 1, f"the starter no longer holds exactly one line {old!r}"
    return text.replace(old, new)


def _write(folder: Path, text: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "design.py").write_text(text, encoding="utf-8", newline="\n")


def _starter(folder: Path) -> None:
    """``blink/``, as ``fenolite init blink --confirm`` leaves it."""
    target = folder / STARTER
    target.mkdir(parents=True, exist_ok=True)
    for name, data in guide.render_starter(STARTER, STARTER).items():
        (target / name).write_bytes(data)


def _bad_lib_id(folder: Path) -> None:
    """``broken/`` names a footprint the catalog does not have; ``fixed/`` is the starter."""
    _write(folder / "broken", _swap(starter_script(), BAD_LIB_ID))
    _write(folder / "fixed", starter_script())


def _script_error(folder: Path) -> None:
    """``broken/`` passes a bare number as a length, which raises; ``fixed/`` is the starter."""
    _write(folder / "broken", _swap(starter_script(), SCRIPT_ERROR))
    _write(folder / "fixed", starter_script())


def _crossed(folder: Path) -> None:
    """``blink/`` with R1 and D1 exchanged, so that the straight tracks of VIN and GND cross."""
    _write(folder / STARTER, _swap(_swap(starter_script(), _R1_PLACE), _D1_PLACE))


def _lossy(folder: Path) -> None:
    """``blink/`` with a creepage rule, which a build for KiCad 9 refuses with ``FEN-7001``."""
    _write(folder / STARTER, _swap(starter_script(), _IMPORT) + _CREEPAGE)


SANDBOXES: Mapping[str, Callable[[Path], None]] = MappingProxyType(
    {
        "starter": _starter,
        "bad-lib-id": _bad_lib_id,
        "script-error": _script_error,
        "crossed": _crossed,
        "lossy": _lossy,
    }
)
"""Sandbox name → the function that prepares it in an empty folder."""


def hermetic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """No external tool can be found or started for the rest of the test: an empty ``PATH``, no
    variable that names a tool, an empty tools folder, and subprocess creation patched to raise."""
    from fenolite.backends.kicad import cli as kicad_cli
    from fenolite.cli import cmd_capabilities

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a guide block started a subprocess: {args[:1]}")

    empty = tmp_path / "empty-path"
    tools = tmp_path / "empty-tools"
    empty.mkdir(exist_ok=True)
    tools.mkdir(exist_ok=True)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("FENOLITE_TOOLS_DIR", str(tools))
    for name in TOOL_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    cmd_capabilities.detect_tools.cache_clear()


@dataclass(frozen=True, slots=True)
class Outcome:
    """What one command line gave: the exit code, the envelope of stdout and the error object of stderr
    (each ``None`` when that stream held no JSON object)."""

    code: int
    envelope: dict[str, Any] | None
    error: dict[str, Any] | None

    def codes(self) -> set[str]:
        """The code of the error object and the codes of the envelope's issues."""
        found: set[str] = set()
        if self.error is not None and isinstance(self.error.get("code"), str):
            found.add(self.error["code"])
        for issue in (self.envelope or {}).get("issues", []):
            found.add(issue["code"])
        return found


def _object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def run(line: str) -> Outcome:
    """Run the command line ``fenolite …`` in this process, in the current directory."""
    words = shlex.split(line)
    assert words[:1] == ["fenolite"], line
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(words[1:])
    return Outcome(code, _object(out.getvalue()), _object(err.getvalue()))


@contextlib.contextmanager
def inside(folder: Path) -> Iterator[None]:
    """Run the body with ``folder`` as the working directory."""
    before = Path.cwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(before)


STEP = re.compile(r"^(?P<command>fenolite \S.*?)\s+# exit (?P<exit>\d)(?:, has (?P<code>\S+))?$")
"""One line of a ``fenolite-recipe`` block: the command, the exit code it must give and, optionally,
a code that its error object or one of its issues must carry."""


def recipe_problems(block: guide.Block, folder: Path) -> list[str]:
    """Why the recipe ``block`` does not behave as written: an empty list when every line, run in order
    in its sandbox prepared under ``folder``, gives its exit code and its code. ``folder`` is empty."""
    where = f"line {block.line_number}"
    prepare = SANDBOXES.get(block.argument)
    if prepare is None:
        return [f"{where}: unknown sandbox {block.argument!r}; the sandboxes are {', '.join(SANDBOXES)}"]
    lines = [line.strip() for line in block.lines if line.strip()]
    if not lines:
        return [f"{where}: the recipe holds no command"]
    prepare(folder)
    problems: list[str] = []
    with inside(folder):
        for number, line in enumerate(lines, start=block.line_number + 1):
            step = STEP.fullmatch(line)
            if step is None:
                problems.append(f"line {number}: not '<command>  # exit N[, has <code>]': {line}")
                break
            outcome = run(step["command"])
            expected = int(step["exit"])
            if outcome.code != expected:
                problems.append(
                    f"line {number}: exit code {expected} expected, {outcome.code} found: {step['command']}"
                )
                break
            if step["code"] is not None and step["code"] not in outcome.codes():
                problems.append(
                    f"line {number}: no {step['code']} among {sorted(outcome.codes())}: {step['command']}"
                )
                break
    return problems
