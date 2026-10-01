# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers for tests that run kicad-cli as an oracle (marker ``needs_kicad``)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from _resources import kicad_cli

SUPPORTED_MAJORS = (9, 10)


def cli() -> str:
    found = kicad_cli()
    if found is None:  # the needs_kicad marker skips before this is reached
        pytest.skip("kicad-cli not found")
    return found


def supported_version() -> str:
    """The exact ``kicad-cli version``; the test fails unless the major is 9 or 10."""
    out = subprocess.run([cli(), "version"], capture_output=True, text=True, check=False, timeout=120)
    version = out.stdout.strip().splitlines()[-1].strip() if out.stdout.strip() else ""
    major = version.split(".")[0]
    if not major.isdigit() or int(major) not in SUPPORTED_MAJORS:
        pytest.fail(
            f"kicad-cli reports version {version!r}; supported majors are "
            + ", ".join(str(m) for m in SUPPORTED_MAJORS)
        )
    print(f"kicad-cli {version}")
    return version


def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run kicad-cli; fail the test with its output on a non-zero exit code."""
    result = subprocess.run(
        [cli(), *map(str, args)], capture_output=True, text=True, check=False, timeout=300
    )
    if result.returncode != 0:
        command = " ".join(map(str, args))
        pytest.fail(f"kicad-cli {command} exited {result.returncode}:\n{result.stdout}\n{result.stderr}")
    return result


def mm(nm: int) -> str:
    """Nanometres as a KiCad millimetre number (at most 6 decimals, no exponent)."""
    sign = "-" if nm < 0 else ""
    whole, frac = divmod(abs(nm), 1_000_000)
    return f"{sign}{whole}" + (f".{frac:06d}".rstrip("0") if frac else "")
