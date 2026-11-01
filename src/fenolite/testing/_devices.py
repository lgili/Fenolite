# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Data-only project device context for private design and block benches."""

from __future__ import annotations

import shutil
from pathlib import Path


def vendored_project(source: Path) -> Path | None:
    """The owning project of code inside a vendored block namespace."""
    source = source.resolve()
    for parent in source.parents:
        if parent.name == "fenolite_library":
            parts = source.relative_to(parent).parts
            if len(parts) >= 3 and parts[0] == "blocks":
                return parent.parent
    return None


def copy_device_context(project: Path, folder: Path) -> None:
    """Private benches carry the same data-only records, native references and authored precedence."""
    for relative in (
        "devices",
        "fenolite_library/symbols",
        "fenolite_library/footprints",
        "fenolite_library/devices",
    ):
        source = project / relative
        if source.is_dir():
            shutil.copytree(
                source,
                folder / relative,
                dirs_exist_ok=True,
                symlinks=True,
                ignore=shutil.ignore_patterns("__pycache__", ".git", ".venv", ".fenolite", "*.bak"),
            )
