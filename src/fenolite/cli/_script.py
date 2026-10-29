# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Running a design script in-process (``docs/dsl.md``, "Scripts").

``build`` executes ``design.py`` as the user's own code: there is no sandbox, and it must never be run
on an untrusted script. The run writes no bytecode, captures the script's output, and restores
``sys.path``, ``sys.argv``, ``sys.dont_write_bytecode`` and the module cache of the script folder.
"""

from __future__ import annotations

import contextlib
import io
import os
import runpy
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.errors import FormatError
from fenolite.dsl import Design, Panel

SCRIPT_OUTPUT_LIMIT = 4000
TRUNCATED = "…[truncated]"
RUN_NAME = "__fenolite_build__"


class DesignScriptError(FormatError):
    """A design script raised, or binds no module-level ``design`` (FEN-3004)."""


@dataclass(frozen=True)
class ScriptRun:
    design: Design
    output: str


def _inside(path: str | None, folder: Path) -> bool:
    if not path:
        return False
    try:
        return Path(path).resolve().is_relative_to(folder)
    except OSError:
        return False


def _locator(error: BaseException, script: Path) -> str:
    line = None
    for frame in traceback.extract_tb(error.__traceback__):
        if Path(frame.filename).resolve() == script:
            line = frame.lineno
    return f"line:{line}" if line is not None else ""


def _capped(text: str) -> str:
    if len(text) <= SCRIPT_OUTPUT_LIMIT:
        return text
    return text[: SCRIPT_OUTPUT_LIMIT - len(TRUNCATED)] + TRUNCATED


def _run_script(path: Path, what: str) -> tuple[dict[str, object], str]:
    """The namespace of the script at ``path`` and its captured stdout and stderr; ``what`` names the
    script in errors."""
    script = Path(path).resolve()
    if not script.is_file():
        raise DesignScriptError(f"{what} script {path} does not exist", file=os.fspath(path))
    folder = script.parent
    saved_path, saved_argv, saved_bytecode = list(sys.path), list(sys.argv), sys.dont_write_bytecode
    # a module already loaded under the name of a file beside the script (``copper`` of an imported board,
    # change c0275) would shadow that file: it is set aside for the run and put back after it
    siblings = {p.stem for p in folder.glob("*.py")} | {
        p.name for p in folder.iterdir() if p.is_dir() and (p / "__init__.py").is_file()
    }
    shadowed = {
        name: module
        for name, module in list(sys.modules.items())
        if name.partition(".")[0] in siblings and not _inside(getattr(module, "__file__", None), folder)
    }
    for name in shadowed:
        del sys.modules[name]
    before = set(sys.modules)
    output = io.StringIO()
    sys.dont_write_bytecode = True
    sys.argv = [os.fspath(script)]
    sys.path.insert(0, os.fspath(folder))
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            namespace = runpy.run_path(os.fspath(script), run_name=RUN_NAME)
    except KeyboardInterrupt:
        raise
    except BaseException as error:  # SystemExit and DslError included: the script failed
        raise DesignScriptError(
            f"{what} script failed: {type(error).__name__}: {error}",
            file=os.fspath(path),
            locator=_locator(error, script),
        ) from error
    finally:
        sys.path[:] = saved_path
        sys.argv = saved_argv
        sys.dont_write_bytecode = saved_bytecode
        for name in set(sys.modules) - before:
            module = sys.modules.get(name)
            if module is not None and _inside(getattr(module, "__file__", None), folder):
                del sys.modules[name]
        sys.modules.update(shadowed)
    return namespace, _capped(output.getvalue())


def run_design_script(path: Path) -> ScriptRun:
    """The module-level ``design`` of the script at ``path`` and its captured stdout and stderr."""
    namespace, output = _run_script(path, "design")
    design = namespace.get("design")
    if not isinstance(design, Design):
        found = "nothing" if design is None else type(design).__name__
        raise DesignScriptError(
            f"design script binds no module-level 'design' of type fenolite.dsl.Design (found {found})",
            file=os.fspath(path),
        )
    return ScriptRun(design, output)


@dataclass(frozen=True)
class PanelRun:
    panel: Panel
    output: str


def run_panel_script(path: Path) -> PanelRun:
    """The module-level ``panel`` of the panel script at ``path`` and its captured output (change c0173)."""
    namespace, output = _run_script(path, "panel")
    panel = namespace.get("panel")
    if not isinstance(panel, Panel):
        found = "nothing" if panel is None else type(panel).__name__
        raise DesignScriptError(
            f"panel script binds no module-level 'panel' of type fenolite.dsl.Panel (found {found})",
            file=os.fspath(path),
        )
    return PanelRun(panel, output)


__all__ = [
    "SCRIPT_OUTPUT_LIMIT",
    "DesignScriptError",
    "PanelRun",
    "ScriptRun",
    "run_design_script",
    "run_panel_script",
]
