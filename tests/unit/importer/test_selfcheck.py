# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Self-check of an import (capability board-to-code, "Self-check of an import"; change c0275)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _importcode import PROJECT, imported

from fenolite.cli import cmd_import
from fenolite.importer import tables


def test_equal_at_five_levels(tmp_path: Path) -> None:
    reply = imported(tmp_path, PROJECT, "--json")
    assert reply.exit_code == 0, reply.error
    assert reply.result["equivalence"] == {"levels": [1, 2, 3, 4, 5], "equivalent": True}


def test_emitter_bug_caught(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = tables.copper_tables

    def drop_one_via(*args: object, **kwargs: object) -> tables.Tables:
        found = real(*args, **kwargs)  # type: ignore[arg-type]
        first = next(t for t in found.tables if t.kind == "via")
        shorter = dataclasses.replace(first, rows=first.rows[1:])
        return dataclasses.replace(found, tables=tuple(shorter if t is first else t for t in found.tables))

    import fenolite.importer.emit.design as emitter

    monkeypatch.setattr(emitter, "copper_tables", drop_one_via)
    reply = imported(tmp_path, PROJECT)
    assert reply.exit_code == 5
    unequal = [i for i in (reply.envelope or {})["issues"] if i["code"] == "import.unequal"]
    assert unequal and all(i["where"].startswith("level 5") for i in unequal)
    assert any("GND" in i["where"] or "GND" in i["message"] for i in unequal)
    assert "plan" not in reply.result
    assert cmd_import.COMMAND.mutates
