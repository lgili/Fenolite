# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene cache of the viewer (capability viewer-performance, scenario "A second open"; change c0182)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.view.cache import SceneCache, user_folder

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"


def test_corrupt_entry_is_rebuilt(tmp_path: Path) -> None:
    store = SceneCache(tmp_path)
    key = store.key(BOARD, "")
    (tmp_path / f"{key}.json.gz").write_bytes(b"not gzip")
    assert store.scene(BOARD, "", lambda: {"meta": {}}) == {"meta": {}}
    assert store.misses == 1 and store.get(key) == {"meta": {}}


def test_user_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_CACHE_DIR", str(tmp_path))
    assert user_folder() == tmp_path / "view"
