# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from fenolite.core import io as fio


def test_new_file_receipt(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "a.txt"
    receipt = fio.atomic_write(target, b"hello\n")
    assert target.read_bytes() == b"hello\n"
    assert receipt.sha256 == fio.sha256_of(target) == fio.sha256_bytes(b"hello\n")
    assert receipt.backup_path is None
    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode & 0o044, "new files must not be private (0600) like mkstemp's default"


def test_backup_of_previous_content(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")
    receipt = fio.atomic_write(target, b"new")
    assert target.read_bytes() == b"new"
    assert receipt.backup_path == tmp_path / "a.txt.bak"
    assert receipt.backup_path.read_bytes() == b"old"


def test_no_backup(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"old")
    assert fio.atomic_write(target, b"new", backup=False).backup_path is None
    assert not (tmp_path / "a.txt.bak").exists()


def test_failure_before_rename_leaves_original_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"original")

    def boom(_src: object, _dst: object) -> None:
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(fio.os, "replace", boom)
    with pytest.raises(OSError, match="simulated"):
        fio.atomic_write(target, b"new content")
    assert target.read_bytes() == b"original"
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []


def test_permissions_of_existing_file_are_kept(tmp_path: Path) -> None:
    target = tmp_path / "script.sh"
    target.write_bytes(b"#!/bin/sh\n")
    os.chmod(target, 0o750)
    fio.atomic_write(target, b"#!/bin/sh\necho hi\n")
    assert stat.S_IMODE(target.stat().st_mode) == 0o750
