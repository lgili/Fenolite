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
    kicad_cli_version,
    kicad_library_dirs,
    required_resources,
)

pytest_plugins = ["pytester"]


def _missing(resource: str, message: str) -> None:
    """Skip, or fail when ``FENOLITE_REQUIRE`` lists the resource (required-resource mode)."""
    if resource in required_resources():
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("needs_corpus"):
        cache = corpus_cache_dir()
        if not cache.is_dir() or not any(cache.iterdir()):
            _missing("corpus", CORPUS_HINT)
    if item.get_closest_marker("needs_libs") and not kicad_library_dirs():
        _missing("libs", "official KiCad libraries not found (set KICAD10_FOOTPRINT_DIR or install KiCad)")
    if item.get_closest_marker("needs_kicad") and kicad_cli() is None:
        _missing("kicad", "kicad-cli not found (install KiCad or set FENOLITE_KICAD_CLI)")
    minimum = item.get_closest_marker("kicad_min_major")
    if minimum is not None:
        version = kicad_cli_version()
        needed = int(minimum.args[0])
        if version is not None and version[0] < needed:
            # An older major is present, not missing: required-resource mode never turns this into a failure.
            pytest.skip(f"needs kicad-cli {needed}.x; running {version[0]}.x")
