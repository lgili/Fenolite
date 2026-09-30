# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Shared pytest configuration: helper import path and skip rules for optional resources."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from _resources import (  # noqa: E402  (imported after the sys.path setup above)
    CORPUS_HINT,
    corpus_cache_dir,
    kicad_cli,
    kicad_library_dirs,
)


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("needs_corpus"):
        cache = corpus_cache_dir()
        if not cache.is_dir() or not any(cache.iterdir()):
            pytest.skip(CORPUS_HINT)
    if item.get_closest_marker("needs_libs") and not kicad_library_dirs():
        pytest.skip("official KiCad libraries not found (set KICAD10_FOOTPRINT_DIR or install KiCad)")
    if item.get_closest_marker("needs_kicad") and kicad_cli() is None:
        pytest.skip("kicad-cli not found (install KiCad or set FENOLITE_KICAD_CLI)")
