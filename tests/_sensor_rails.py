# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The illustrative device records of ``examples/sensor_rails/devices`` (authored for Fenolite), loaded for
the tests of change c0252."""

from __future__ import annotations

from pathlib import Path

from fenolite.catalog.devices import parse_device
from fenolite.model.library import DeviceDef

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sensor_rails"
DEVICES = EXAMPLE / "devices"


def sensor_devices() -> tuple[DeviceDef, ...]:
    """The records in file-name order."""
    return tuple(
        parse_device(path.read_text(encoding="utf-8"), file=path.name)
        for path in sorted(DEVICES.glob("*.toml"))
    )


def copy_example(folder: Path) -> Path:
    """The example in ``folder`` (scripts, ``rails/``, ``devices/`` and ``good.lock``), for a build."""
    import shutil

    shutil.copytree(EXAMPLE, folder, ignore=shutil.ignore_patterns("__pycache__"))
    return folder
