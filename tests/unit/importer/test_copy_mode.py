# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The import record marks a copy (capability board-to-code, "Import record marks a copy"; change c0281,
issue 1 of the board library's conversion report)."""

from __future__ import annotations

import json
from pathlib import Path

from _importcode import PROJECT, imported

from fenolite.importer.provenance import LIBRARY_SCHEMA, SCHEMA, copy_mode


def test_written_and_read(tmp_path: Path) -> None:
    """Scenario "Written and read"."""
    reply = imported(tmp_path, PROJECT, "--confirm")
    assert reply.exit_code == 0, reply.error
    record = json.loads((tmp_path / "out" / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert record["copy"] is True and copy_mode(record)
    assert copy_mode({"schema": LIBRARY_SCHEMA, "import": record})
    assert not copy_mode({**record, "copy": False})
    assert not copy_mode({"schema": LIBRARY_SCHEMA, "import": {**record, "copy": False}})


def test_a_record_before_c0281_is_a_copy() -> None:
    assert copy_mode({"schema": SCHEMA, "design": "board"})


def test_no_import_record_is_no_copy() -> None:
    assert not copy_mode({"schema": LIBRARY_SCHEMA, "fidelity": {"accepted": []}})
    assert not copy_mode({"schema": LIBRARY_SCHEMA})
    assert not copy_mode([])
    assert not copy_mode({"schema": "other", "import": {"schema": "other"}})
