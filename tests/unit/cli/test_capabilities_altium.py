# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium capabilities derive graduation and missing evidence from the matrix (c0092)."""

from __future__ import annotations

import json

from fenolite.backends import matrix
from fenolite.backends.base import graduated, graduation_context
from fenolite.cli.main import main


def test_altium_kinds_and_missing_conditions(capsys) -> None:
    assert main(["capabilities", "--no-tools", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    support, runs = graduation_context()
    rows = [row for row in matrix.rows() if row.backend == "altium" and row.write]
    backend = next(backend for backend in result["backends"] if backend["name"] == "altium")
    assert backend["write_kinds"] == [row.kind for row in rows if graduated(row, support, runs)[0]]
    missing = {
        kind: reasons for entry in result["experimental"] for kind, reasons in entry["missing"].items()
    }
    for row in rows:
        ok, reasons = graduated(row, support, runs)
        if not ok:
            assert missing[row.kind] == list(reasons)
