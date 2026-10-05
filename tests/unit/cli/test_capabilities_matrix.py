# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix in ``fenolite capabilities`` (capability cli-contract, "Evidence matrix in
capabilities"; change c0067)."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from typing import Any

import _schema
import pytest

from fenolite.backends import matrix
from fenolite.backends.base import MATRIX_OPERATIONS
from fenolite.cli import cmd_capabilities
from fenolite.cli.main import main

ENVELOPE = _schema.load("fenolite.envelope.v0.json")
KEYS = ["backend", "kind", *MATRIX_OPERATIONS, "verified_by", "experimental"]


@pytest.fixture(autouse=True)
def _fresh_detection() -> Iterator[None]:
    cmd_capabilities.detect_tools.cache_clear()
    yield
    cmd_capabilities.detect_tools.cache_clear()


def _result(capsys: pytest.CaptureFixture[str], *extra: str) -> dict[str, Any]:
    assert main(["capabilities", "--json", *extra]) == 0
    data: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert _schema.validate(data, ENVELOPE) == []
    result: dict[str, Any] = data["result"]
    return result


def _row(rows: list[dict[str, Any]], backend: str, kind: str) -> dict[str, Any]:
    (found,) = [row for row in rows if (row["backend"], row["kind"]) == (backend, kind)]
    return found


def test_matrix_listed(capsys: pytest.CaptureFixture[str]) -> None:
    rows = _result(capsys, "--no-tools")["matrix"]
    assert rows == [row.to_json() for row in matrix.rows()]
    assert [(r["backend"], r["kind"]) for r in rows] == sorted((r["backend"], r["kind"]) for r in rows)
    assert all(list(row) == KEYS for row in rows)
    board = _row(rows, "kicad", "kicad_pcb")
    assert all(board[op] for op in ("read", "write", "roundtrip_exact", "roundtrip_modified"))
    assert {"H-K-PCB-READ", "H-K-PCB-WRITE"} <= set(board["verified_by"])
    for row in rows:
        assert row["verified_by"] == sorted(row["verified_by"])
        for operation in MATRIX_OPERATIONS:
            assert row[operation] is None or isinstance(row[operation], str)
            if row[operation] == "UNVERIFIED":
                assert operation in row["experimental"], row["kind"]


def test_missing_operation_is_null(capsys: pytest.CaptureFixture[str]) -> None:
    row = _row(_result(capsys, "--no-tools")["matrix"], "specctra", "specctra_dsn")
    assert isinstance(row["write"], str)
    assert row["read"] is None and row["roundtrip_exact"] is None and row["roundtrip_modified"] is None


def test_board_row_and_backend_report_agree(capsys: pytest.CaptureFixture[str]) -> None:
    result = _result(capsys, "--no-tools")
    (entry,) = [b for b in result["backends"] if b["name"] == "kicad"]
    row = _row(result["matrix"], "kicad", "kicad_pcb")
    assert row["roundtrip_modified"].startswith(entry["evidence"]["level"])
    assert set(entry["evidence"]["hypotheses"]) <= set(row["verified_by"])


def test_experimental_writers_are_marked(capsys: pytest.CaptureFixture[str]) -> None:
    result = _result(capsys, "--no-tools")
    kinds = [kind for entry in result["experimental"] for kind in entry["write_kinds"]]
    assert kinds
    for kind in kinds:
        row = _row(result["matrix"], "altium", kind)
        assert row["write"] is not None and "write" in row["experimental"], kind


def test_same_matrix_without_tool_detection(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet = _result(capsys, "--no-tools")
    monkeypatch.setattr(cmd_capabilities, "detect_tools", lambda: {"kicad-cli": None})
    assert _result(capsys)["matrix"] == quiet["matrix"]


def test_adds_a_key_and_changes_none(capsys: pytest.CaptureFixture[str]) -> None:
    result = _result(capsys, "--no-tools")
    assert {"backends", "experimental", "matrix"} <= set(result)
    assert all("matrix" not in backend for backend in result["backends"])
    assert all(len(backend) == 8 for backend in result["backends"])


def test_field_projection(capsys: pytest.CaptureFixture[str]) -> None:
    result = _result(capsys, "--no-tools", "--fields", "matrix")
    assert list(result) == ["matrix"] and result["matrix"]


def test_importing_the_command_stays_light() -> None:
    code = (
        "import sys, fenolite.cli.cmd_capabilities; "
        "print(sorted(m for m in sys.modules if m.endswith('.claims')))"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "[]"
