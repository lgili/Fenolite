# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit tests import ``_simulate`` (here) and share one built kit."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


@pytest.fixture(scope="session")
def built_kit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A kit built once from the checkout's sample scripts; tests copy it and never change it."""
    from fenolite.cli._kit import kit_sources
    from fenolite.verify.kit.manifest import build_kit

    folder = tmp_path_factory.mktemp("kit") / "kit"
    build_kit(folder, sources=kit_sources())
    return folder


@pytest.fixture
def kit(built_kit: Path, tmp_path: Path) -> Path:
    """A fresh copy of the built kit that a test may fill and change."""
    folder = tmp_path / "run" / "kit"
    shutil.copytree(built_kit, folder)
    return folder
