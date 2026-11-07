# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tool-free benches used by the shipped plain-function self-tests."""

import ast
import shutil
from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from fenolite.dsl import Range
from fenolite.testing import TestDesign, load

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def bench(
    name: str, params: str | None = None, extra: str = "", device_text: str | None = None
) -> Generator[TestDesign]:
    """Build an authored usage privately, optionally replacing explicit parameters."""
    with TemporaryDirectory(prefix="fenolite-starter-") as temp:
        folder = Path(temp)
        text = (ROOT / "usage" / f"{name}.py").read_text()
        if params is not None:
            assignment = next(
                node
                for node in ast.parse(text).body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "dut" for t in node.targets)
            )
            lines = text.splitlines(keepends=True)
            lines[assignment.lineno - 1 : assignment.end_lineno] = [
                f'dut = design.use({name}, "dut"{", " + params if params else ""})\n'
            ]
            text = "".join(lines)
        (folder / "design.py").write_text(text + extra)
        shutil.copytree(ROOT / "usage" / "devices", folder / "devices")
        if device_text is not None:
            (folder / "devices" / "extra.toml").write_text(device_text)
        with load(folder / "design.py") as design:
            yield design


def part(design: TestDesign, name: str):
    return next(
        c for c in design.model.circuit.components if c.properties.get("fenolite.path") == f"dut/{name}"
    )


def refused(call: Callable[[], AbstractContextManager[object]], text: str) -> None:
    try:
        with call():
            pass
    except Exception as error:
        assert text in str(error), str(error)
    else:
        raise AssertionError(f"expected refusal containing {text}")


def low(value: Range | None) -> Fraction:
    assert value is not None and value.low is not None
    return value.low


def high(value: Range | None) -> Fraction:
    assert value is not None and value.high is not None
    return value.high
