# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every Python source file starts with the SPDX licence line and the copyright line."""

from __future__ import annotations

import tomllib
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("src", "tests", "tools")
EXEMPT = ("schemas", "tools/residue")
HEADER = (
    "# SPDX-License-Identifier: Apache-2.0",
    "# Copyright (c) 2026 Fenolite contributors",
)
CC0_HEADER = ("# SPDX-License-Identifier: CC0-1.0", HEADER[1])


def _cc0_data_paths(root: Path) -> frozenset[str]:
    """Only declared authored data may use CC0; a manifest cannot relicense core code."""
    found: set[str] = set()
    manifests = (
        ("tests/data/MANIFEST.toml", "", "tests/data/"),
        ("src/fenolite/blocks/MANIFEST.toml", "src/fenolite/blocks/", "src/fenolite/blocks/usage/"),
    )
    for name, base, scope in manifests:
        path = root / name
        if not path.is_file():
            continue
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        for row in data.get("file", []):
            if row.get("origin") != "authored" or row.get("spdx", data.get("licence")) != "CC0-1.0":
                continue
            rel = PurePosixPath(row["path"])
            assert not rel.is_absolute() and ".." not in rel.parts, "invalid authored data path"
            target = base + rel.as_posix()
            if target.startswith(scope) and rel.suffix == ".py":
                found.add(target)
    return frozenset(found)


def _header_problem(path: Path, rel: str, cc0_data: frozenset[str]) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    expected = CC0_HEADER if rel in cc0_data else HEADER
    if tuple(lines[:2]) != expected:
        return True
    return rel in cc0_data and not any(line.startswith("# Authored for Fenolite") for line in lines[2:5])


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
    cc0_data = _cc0_data_paths(ROOT)
    for path in _python_files():
        rel = path.relative_to(ROOT).as_posix()
        if _header_problem(path, rel, cc0_data):
            offenders.append(rel)
    assert not offenders, "missing SPDX/copyright header in:\n" + "\n".join(offenders)


def test_scan_is_not_empty() -> None:
    assert _python_files(), "no Python files found; the header test would pass vacuously"


def test_manifest_dedication_is_bounded_to_authored_data(tmp_path: Path) -> None:
    manifest = tmp_path / "tests/data/MANIFEST.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '[[file]]\npath = "tests/data/own/design.py"\norigin = "authored"\nspdx = "CC0-1.0"\n'
        '[[file]]\npath = "src/fenolite/core/not_data.py"\norigin = "authored"\nspdx = "CC0-1.0"\n'
        '[[file]]\npath = "tests/data/foreign/design.py"\norigin = "corpus"\nspdx = "CC0-1.0"\n',
        encoding="utf-8",
    )
    assert _cc0_data_paths(tmp_path) == {"tests/data/own/design.py"}


def test_core_licence_and_copyright_cannot_use_the_data_exception(tmp_path: Path) -> None:
    path = tmp_path / "authored.py"
    path.write_text("\n".join((*CC0_HEADER, "# Authored for Fenolite as test data.")) + "\n")
    declared = frozenset({"tests/data/own/design.py"})
    assert not _header_problem(path, "tests/data/own/design.py", declared)
    assert _header_problem(path, "src/fenolite/core/not_data.py", declared)
    path.write_text("\n".join((CC0_HEADER[0], "# Authored for Fenolite as test data.")) + "\n")
    assert _header_problem(path, "tests/data/own/design.py", declared)
    path.write_text("\n".join(CC0_HEADER) + "\n")
    assert _header_problem(path, "tests/data/own/design.py", declared)
