# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Files kept only online (change c0201; capability file-safety, "Open sessions and placeholders").

The attributes are those the operating systems document; a ``stat`` result is faked, since no platform of
the test suites holds an online-only file."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from fenolite.safety import placeholders
from fenolite.safety.placeholders import (
    FILE_ATTRIBUTE_OFFLINE,
    FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS,
    FILE_ATTRIBUTE_RECALL_ON_OPEN,
    SF_DATALESS,
    is_online_only,
    online_only,
)


@dataclass
class FakeStat:
    st_mode: int = 0o100644
    st_file_attributes: int = 0
    st_flags: int = 0


@pytest.mark.parametrize(
    "attribute", [FILE_ATTRIBUTE_OFFLINE, FILE_ATTRIBUTE_RECALL_ON_OPEN, FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS]
)
def test_windows_attributes(attribute: int) -> None:
    assert is_online_only(FakeStat(st_file_attributes=attribute | 0x20))
    assert not is_online_only(FakeStat(st_file_attributes=0x20))  # an archive bit alone


def test_macos_dataless() -> None:
    assert SF_DATALESS == 0x40000000
    assert is_online_only(FakeStat(st_flags=SF_DATALESS)) and not is_online_only(FakeStat(st_flags=0x20))


def test_plain_stat_has_neither(tmp_path: Path) -> None:
    path = tmp_path / "a.kicad_pcb"
    path.write_text("x", encoding="utf-8")
    assert online_only([path, tmp_path / "missing"]) == ()


def test_online_only_reads_attributes_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "a.kicad_pcb"
    path.write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        placeholders.os, "stat", lambda p, follow_symlinks=True: FakeStat(st_flags=SF_DATALESS)
    )
    assert online_only([path]) == (path,)


@pytest.mark.skipif(
    sys.platform != "darwin" or sys.version_info < (3, 13), reason="stat.SF_DATALESS is macOS 3.13+"
)
def test_stdlib_value_on_macos() -> None:
    import stat

    assert stat.SF_DATALESS == SF_DATALESS
