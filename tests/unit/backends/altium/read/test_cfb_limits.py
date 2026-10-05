# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Limits checked before allocation and work proportional to untrusted input."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from _cfb_build import build

from fenolite.backends.altium.read.cfb import CompoundError, Limits, open_compound, read_compound


def test_entry_depth_and_file_limits() -> None:
    many = build([{"path": f"S{i}", "data": b"x"} for i in range(8)]).data
    with pytest.raises(CompoundError, match="max_entries"):
        open_compound(many, limits=Limits(max_entries=4))

    path = "/".join(["S"] * 100 + ["Data"])
    deep = build([{"path": path, "data": b"x"}]).data
    with pytest.raises(CompoundError, match="max_depth"):
        open_compound(deep)
    assert open_compound(deep, limits=Limits(max_depth=128)).node(path[:-5]).kind == "storage"

    with pytest.raises(CompoundError, match="max_file_bytes"):
        open_compound(many, limits=Limits(max_file_bytes=1))


def test_disk_size_is_checked_before_read_bytes(tmp_path: Path) -> None:
    path = tmp_path / "oversized.PcbDoc"
    path.write_bytes(bytes(2000))
    with patch.object(Path, "read_bytes", side_effect=AssertionError("read_bytes must not run")):
        with pytest.raises(CompoundError, match="max_file_bytes"):
            read_compound(path, limits=Limits(max_file_bytes=1000))
