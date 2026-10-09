# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The guide tests import ``_sandbox`` (here) and share the fixture ``no_tools``."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


@pytest.fixture
def no_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """The test runs with no external tool to find or to start (``_sandbox.hermetic``)."""
    from _sandbox import hermetic

    from fenolite.cli import cmd_capabilities

    hermetic(monkeypatch, tmp_path)
    yield
    cmd_capabilities.detect_tools.cache_clear()
