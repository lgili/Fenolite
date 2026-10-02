# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Design scripts run in-process (capability design-dsl, "Design scripts"; change c0011)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import fenolite.dsl
from fenolite.cli._script import SCRIPT_OUTPUT_LIMIT, DesignScriptError, run_design_script
from fenolite.core.errors import FormatError

HEADER = "from fenolite.dsl import Design\n"


def script(folder: Path, body: str, name: str = "design.py") -> Path:
    path = folder / name
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_runs_and_captures_output(tmp_path: Path) -> None:
    run = run_design_script(script(tmp_path, 'print("hello")\ndesign = Design("x")\n'))
    assert run.design.name == "x" and "hello" in run.output


def test_no_bytecode_and_fresh_siblings(tmp_path: Path) -> None:
    (tmp_path / "parts.py").write_text('NAME = "one"\n', encoding="utf-8")
    path = script(tmp_path, "import parts\ndesign = Design(parts.NAME)\n")
    assert run_design_script(path).design.name == "one"
    (tmp_path / "parts.py").write_text('NAME = "two"\n', encoding="utf-8")
    assert run_design_script(path).design.name == "two"
    assert not (tmp_path / "__pycache__").exists() and "parts" not in sys.modules


def test_interrupt_propagates(tmp_path: Path) -> None:
    before = list(sys.path)
    with pytest.raises(KeyboardInterrupt):
        run_design_script(script(tmp_path, "raise KeyboardInterrupt\n"))
    assert sys.path == before


def test_packaged_example_keeps_the_dsl_modules() -> None:
    module = sys.modules["fenolite.dsl"]
    minimal = Path(fenolite.dsl.__file__).parent / "_minimal.py"
    first, second = run_design_script(minimal), run_design_script(minimal)
    assert isinstance(first.design, fenolite.dsl.Design) and isinstance(second.design, fenolite.dsl.Design)
    assert sys.modules["fenolite.dsl"] is module


def test_missing_design(tmp_path: Path) -> None:
    with pytest.raises(DesignScriptError, match="design"):
        run_design_script(script(tmp_path, "x = 1\n"))
    with pytest.raises(DesignScriptError, match="does not exist"):
        run_design_script(tmp_path / "nope.py")


def test_error_located_by_line(tmp_path: Path) -> None:
    body = "\n" * 10 + 'raise ValueError("boom")\n'
    with pytest.raises(DesignScriptError) as caught:
        run_design_script(script(tmp_path, body))
    assert caught.value.locator == "line:12" and isinstance(caught.value, FormatError)


def test_system_exit_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(DesignScriptError):
        run_design_script(script(tmp_path, "raise SystemExit(2)\n"))


def test_output_is_capped(tmp_path: Path) -> None:
    run = run_design_script(script(tmp_path, 'print("x" * 9000)\ndesign = Design("x")\n'))
    assert len(run.output) == SCRIPT_OUTPUT_LIMIT and run.output.endswith("…[truncated]")
