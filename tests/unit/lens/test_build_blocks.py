# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block checks of a build and the block example (capability design-dsl, "Unused block ports", "Nets that
escape a block" and "Block instances"; change c0251)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import blink, build

import fenolite.cli.main as cli_main
from fenolite.core.errors import Issue
from fenolite.dsl import block, connect
from fenolite.lens.build import BUILD_ISSUE_CODES

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "blocks" / "design.py"
CODES = ("build.port-unused", "build.block-net-escape")


def example_text() -> str:
    return EXAMPLE.read_text(encoding="utf-8")


def cli_issues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> tuple[int, list[dict[str, Any]]]:
    script = tmp_path / "design.py"
    script.write_text(text, encoding="utf-8")
    stdout = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    code = cli_main.main(["build", str(script), "--out", str(tmp_path / "B"), "--dry-run", "--json"])
    return code, json.loads(stdout.getvalue())["issues"]


def found(issues: list[Issue], code: str) -> list[Issue]:
    return [i for i in issues if i.code == code]


def test_codes_are_warnings() -> None:
    assert all(BUILD_ISSUE_CODES[code] == "warning" for code in CODES)


def test_example_builds_without_block_issues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, issues = cli_issues(tmp_path, monkeypatch, example_text())
    assert code == 0 and issues == []


def test_port_nobody_wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = example_text().replace("connect(gnd, ch1.GND)\n", "")
    code, issues = cli_issues(tmp_path, monkeypatch, text)
    unused = [i for i in issues if i["code"] == "build.port-unused"]
    assert code == 0 and len(unused) == 1
    assert "ch1" in unused[0]["message"] and "GND" in unused[0]["message"] and unused[0]["where"] == "ch1/GND"


def test_optional_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # EN of channel is optional and wired to nothing outside ch1
    code, issues = cli_issues(tmp_path, monkeypatch, example_text())
    assert code == 0 and not [
        i for i in issues if i["code"] == "build.port-unused" and "ch1/EN" in i["where"]
    ]
    text = example_text().replace(
        'b.port("EN", direction="out", optional=True)', 'b.port("EN", direction="out")'
    )
    _, issues = cli_issues(tmp_path, monkeypatch, text)
    assert {i["where"] for i in issues if i["code"] == "build.port-unused"} == {"ch0/EN", "ch1/EN"}


RES = '"Fenolite:Resistor", footprint="Fenolite:Chip_0603"'
INNER = f'    connect(VIN48, b.part("R_X", {RES})[1])\n'
OUTER = f'connect(VIN48, design.part("R9", {RES})[1])\n'


def test_global_net_closed_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = example_text()
    text = text.replace('    connect(gnd, c["B"])\n', '    connect(gnd, c["B"])\n' + INNER)
    text = text.replace(
        'design = Design("blocks_demo")\n', 'design = Design("blocks_demo")\nVIN48 = Net("VIN48")\n'
    )
    text = text.replace("j.place(", OUTER + "j.place(")
    code, issues = cli_issues(tmp_path, monkeypatch, text)
    escape = [i for i in issues if i["code"] == "build.block-net-escape"]
    assert code == 0 and {i["where"] for i in escape} == {"ch0:VIN48", "ch1:VIN48"}
    assert all("VIN48" in i["message"] and i["hint"] == "declare a port" for i in escape)


def test_no_block_no_block_issue() -> None:
    output = build(blink())
    assert not [i for i in output.issues if i.code in CODES]


def test_block_net_escape_needs_no_port_binding() -> None:
    design = blink()
    gnd = design.nets["GND"]

    @block
    def sub(b: Any) -> None:
        r = b.part("R", "Mini:Mini_R", footprint="Mini:Mini_R_0603", prefix="R")
        connect(gnd, r[1])
        connect(b.port("GND", direction="in"), r[2])

    inst = design.use(sub, "s")
    connect(gnd, inst.GND)
    issues = build(design).issues
    assert len(found(list(issues), "build.block-net-escape")) == 0  # the port binds GND
    assert not found(list(issues), "build.port-unused")
