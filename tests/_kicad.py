# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers for tests that run kicad-cli as an oracle (marker ``needs_kicad``)."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from _resources import kicad_cli

from fenolite.backends.kicad.cli import private_state

SUPPORTED_MAJORS = (9, 10)


def cli() -> str:
    found = kicad_cli()
    if found is None:  # the needs_kicad marker skips before this is reached
        pytest.skip("kicad-cli not found")
    return found


def _call(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    """Run ``args`` with private temporary, runtime, cache and state folders (``private_state``, c0153),
    removed afterwards; the configuration folder is the caller's, as before."""
    with tempfile.TemporaryDirectory(prefix="fenolite-kicad-state-") as folder:
        env = {**os.environ, **private_state(Path(folder))}
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout, env=env)


def oracle_env(config: str | os.PathLike[str]) -> dict[str, str]:
    """The caller's environment with ``KICAD_CONFIG_HOME`` set to ``config`` and private temporary,
    runtime, cache and state folders in ``kicad-state`` next to it (``private_state``, c0153), for a test
    that runs ``kicad-cli`` itself in a folder it removes afterwards."""
    state = private_state(Path(config).parent / "kicad-state")
    return {**os.environ, **state, "KICAD_CONFIG_HOME": os.fspath(config)}


def supported_version() -> str:
    """The exact ``kicad-cli version``; the test fails unless the major is 9 or 10."""
    out = _call([cli(), "version"], 120)
    version = out.stdout.strip().splitlines()[-1].strip() if out.stdout.strip() else ""
    major = version.split(".")[0]
    if not major.isdigit() or int(major) not in SUPPORTED_MAJORS:
        pytest.fail(
            f"kicad-cli reports version {version!r}; supported majors are "
            + ", ".join(str(m) for m in SUPPORTED_MAJORS)
        )
    print(f"kicad-cli {version}")
    return version


def major() -> int:
    """The major version of the kicad-cli in use (after the supported-major check)."""
    return int(supported_version().split(".")[0])


def run_raw(*args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run kicad-cli and return the result whatever the exit code."""
    return _call([cli(), *map(str, args)], 600)


def loads(board: Path) -> bool:
    """The load check: ``pcb export svg -l Edge.Cuts --mode-single`` exits 0 and writes the SVG."""
    svg = board.with_suffix(".svg")
    result = run_raw("pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", svg, board)
    return result.returncode == 0 and svg.is_file()


def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    """Run kicad-cli; fail the test with its output on a non-zero exit code."""
    result = _call([cli(), *map(str, args)], 300)
    if result.returncode != 0:
        command = " ".join(map(str, args))
        pytest.fail(f"kicad-cli {command} exited {result.returncode}:\n{result.stdout}\n{result.stderr}")
    return result


def mm(nm: int) -> str:
    """Nanometres as a KiCad millimetre number (at most 6 decimals, no exponent)."""
    sign = "-" if nm < 0 else ""
    whole, frac = divmod(abs(nm), 1_000_000)
    return f"{sign}{whole}" + (f".{frac:06d}".rstrip("0") if frac else "")
