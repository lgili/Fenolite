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


# -- project devices (change c0248, capability fenolite-component-catalog, "Device sources and precedence")

DEVICE = """\
# Authored for Fenolite as test data.
schema = "fenolite.device.v0"
id = "{id}"
summary = "Two-pin test device"
symbol = "Fenolite:Resistor"
footprint = "Fenolite:Chip_0603"
evidence = "UNVERIFIED"
sources = ["S-0314"]

[pins]
A = "1"
B = "2"
"""


def test_devices_beside_the_script(tmp_path: Path) -> None:
    (tmp_path / "devices").mkdir()
    (tmp_path / "devices" / "x.toml").write_text(DEVICE.format(id="Proj:X"), encoding="utf-8")
    path = script(tmp_path, 'r1 = Part("R1", device="Proj:X")\ndesign = Design("x")\ndesign.add(r1)\n')
    path.write_text("from fenolite.dsl import Part\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    run = run_design_script(path)
    part = run.design.parts["R1"]
    assert part.device is not None and part.device.id == "Proj:X" and part.device_origin == "authored"
    assert [file.path for file in run.device_files] == ["devices/x.toml"]
    assert len(run.device_files[0].sha256) == 64 and run.devices.files == {"Proj:X": "devices/x.toml"}
    # the devices are installed for the run only
    with pytest.raises(fenolite.dsl.DslError):
        fenolite.dsl.Part("R1", device="Proj:X")


def test_devices_override_a_shipped_id(tmp_path: Path) -> None:
    (tmp_path / "devices").mkdir()
    (tmp_path / "devices" / "r0603.toml").write_text(DEVICE.format(id="Fenolite:R_0603"), encoding="utf-8")
    path = script(tmp_path, 'design = Design("x")\nr1 = design.part("R1", device="Fenolite:R_0603")\n')
    part = run_design_script(path).design.parts["R1"]
    assert part.device_origin == "authored" and part.device_overrides


def test_devices_one_id_in_two_files(tmp_path: Path) -> None:
    (tmp_path / "devices").mkdir()
    for name in ("a.toml", "b.toml"):
        (tmp_path / "devices" / name).write_text(DEVICE.format(id="Proj:X"), encoding="utf-8")
    with pytest.raises(FormatError) as caught:
        run_design_script(script(tmp_path, 'design = Design("x")\n'))
    assert "devices/a.toml" in str(caught.value) and "devices/b.toml" in str(caught.value)
    assert getattr(caught.value, "cli_code", "") == "FEN-3004"


def test_devices_without_a_folder(tmp_path: Path) -> None:
    run = run_design_script(script(tmp_path, 'design = Design("x")\n'))
    assert run.device_files == () and run.devices.devices == ()
