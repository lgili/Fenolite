# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every Python source file starts with the SPDX licence line and the copyright line."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("src", "tests", "tools")
EXEMPT = ("schemas", "tools/residue")
HEADER = (
    "# SPDX-License-Identifier: Apache-2.0",
    "# Copyright (c) 2026 Fenolite contributors",
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if any(rel == e or rel.startswith(e + "/") for e in EXEMPT):
                continue
            files.append(path)
    return files


def test_every_python_file_has_the_header() -> None:
    offenders = []
    for path in _python_files():
        first = path.read_text(encoding="utf-8").splitlines()[:2]
        if tuple(first) != HEADER:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, "missing SPDX/copyright header in:\n" + "\n".join(offenders)


def test_scan_is_not_empty() -> None:
    assert _python_files(), "no Python files found; the header test would pass vacuously"
