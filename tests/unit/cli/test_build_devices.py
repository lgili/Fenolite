# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Devices in the build result (change c0248; capability design-dsl, "Devices in the build result", and
capability fenolite-component-catalog, "Device sources and precedence" and "Device files are build
inputs")."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "devices"
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def test_result_lists_the_devices(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, err = run(
        monkeypatch, str(EXAMPLE / "design.py"), "--out", str(tmp_path / "B"), "--dry-run"
    )
    assert code == 0, err
    result = envelope["result"]
    rows = {row["id"]: row for row in result["devices"]}  # type: ignore[index]
    assert list(rows) == sorted(rows)
    buck = rows["Example:BUCK_6V_2A"]
    assert (buck["origin"], buck["evidence"], buck["edited"], buck["parts"]) == (
        "authored",
        "UNVERIFIED",
        False,
        ["U1"],
    )
    assert len(buck["sha256"]) == 64
    assert rows["Fenolite:R_0603"]["origin"] == "builtin" and rows["Fenolite:R_0603"]["parts"] == [
        "R1",
        "R2",
        "R3",
    ]
    evidence = envelope["evidence"]
    assert "H-K-BUILD-DEVICE" in evidence["hypotheses"] and evidence["level"] == "INFERRED"  # type: ignore[index]
    assert not [issue for issue in envelope["issues"] if issue["severity"] == "error"]  # type: ignore[union-attr, index]


def test_no_devices_no_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, err = run(monkeypatch, str(BLINK), "--out", str(tmp_path / "B"), "--dry-run")
    assert code == 0, err
    assert envelope["result"]["devices"] == [] and envelope["result"]["device_files"] == []  # type: ignore[index]
    assert "H-K-BUILD-DEVICE" not in envelope["evidence"]["hypotheses"]  # type: ignore[index]


def test_device_file_in_the_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "devices_example"
    shutil.copytree(EXAMPLE, folder)
    script, out = str(folder / "design.py"), str(tmp_path / "B")
    code, envelope, _ = run(monkeypatch, script, "--out", out, "--dry-run")
    assert code == 0
    (row,) = envelope["result"]["device_files"]  # type: ignore[index]
    assert row["path"] == "devices/example_buck.toml" and len(row["sha256"]) == 64
    assert str(tmp_path) not in json.dumps(envelope["result"]["device_files"])  # type: ignore[index]
    first = envelope["result"]["plan_id"]  # type: ignore[index]
    record = folder / "devices" / "example_buck.toml"
    record.write_text(
        record.read_text(encoding="utf-8").replace("(illustrative)", "(illustrative, edited)"),
        encoding="utf-8",
    )
    code, envelope, _ = run(monkeypatch, script, "--out", out, "--dry-run")
    assert code == 0 and envelope["result"]["plan_id"] != first  # type: ignore[index]
    assert envelope["result"]["device_files"][0]["sha256"] != row["sha256"]  # type: ignore[index]


def test_one_id_in_two_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "devices_example"
    shutil.copytree(EXAMPLE, folder)
    shutil.copy(folder / "devices" / "example_buck.toml", folder / "devices" / "copy.toml")
    code, _, err = run(monkeypatch, str(folder / "design.py"), "--out", str(tmp_path / "B"), "--dry-run")
    error = json.loads(err.strip().splitlines()[-1])
    assert code == 3 and error["code"] == "FEN-3004"
    assert "devices/copy.toml" in error["message"] and "devices/example_buck.toml" in error["message"]
