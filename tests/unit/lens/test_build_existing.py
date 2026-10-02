# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Edited outputs are not overwritten (capability design-dsl; change c0011), at the function level."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _buildhelp import blink, build

from fenolite.lens.build import RECORD_FILE, LayoutExistsError, check_existing, read_record


def written(tmp_path: Path) -> dict[str, bytes]:
    files = dict(build(blink()).files)
    for rel, data in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(data)
    return files


def test_identical_rewrite_allowed(tmp_path: Path) -> None:
    files = written(tmp_path)
    check_existing(tmp_path, files, record=read_record(tmp_path), discard_layout=False)


def test_recorded_hash_allows_a_dsl_edit(tmp_path: Path) -> None:
    written(tmp_path)
    d = blink()
    d.parts["R1"].request = None
    d.parts["R1"].place("33mm", "9mm")
    new = build(d).files
    check_existing(tmp_path, new, record=read_record(tmp_path), discard_layout=False)


def test_edited_board_refused(tmp_path: Path) -> None:
    files = written(tmp_path)
    board = tmp_path / "blink.kicad_pcb"
    board.write_bytes(board.read_bytes() + b"\n")
    with pytest.raises(LayoutExistsError) as caught:
        check_existing(tmp_path, files, record=read_record(tmp_path), discard_layout=False)
    error = caught.value
    assert error.cli_code == "FEN-7001" and [i.code for i in error.issues] == ["build.layout-exists"]
    assert "blink.kicad_pcb" in error.issues[0].where and "--discard-layout" in error.hint
    check_existing(tmp_path, files, record=read_record(tmp_path), discard_layout=True)


def test_lost_record(tmp_path: Path) -> None:
    files = written(tmp_path)
    (tmp_path / RECORD_FILE).unlink()
    assert read_record(tmp_path) is None
    check_existing(tmp_path, files, record=None, discard_layout=False)
    d = blink()
    d.parts["R1"].request = None
    d.parts["R1"].place("33mm", "9mm")
    with pytest.raises(LayoutExistsError) as caught:
        check_existing(tmp_path, build(d).files, record=None, discard_layout=False)
    assert any("blink.kicad_pcb" in i.where for i in caught.value.issues)


@pytest.mark.parametrize(
    "text", ["not json", '{"schema": "other", "files": {}}', "[]", '{"schema": "fenolite.build-record.v0"}']
)
def test_unreadable_record(tmp_path: Path, text: str) -> None:
    (tmp_path / ".fenolite").mkdir()
    (tmp_path / RECORD_FILE).write_text(text, encoding="utf-8")
    assert read_record(tmp_path) is None


def test_record_read(tmp_path: Path) -> None:
    written(tmp_path)
    record = read_record(tmp_path)
    assert record is not None and record == json.loads((tmp_path / RECORD_FILE).read_text())["files"]
