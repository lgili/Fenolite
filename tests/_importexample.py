# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored import example ``examples/import_python/`` (change c0275): the code ``fenolite import``
writes from ``tests/data/import_python/two_sheet``, a board authored for Fenolite, with the line
``MARKER`` after the provenance header of each ``.py`` file.

``uv run python tests/_importexample.py`` writes it again; ``tests/unit/test_examples.py -k import_python``
keeps it equal to a fresh import, the Fenolite version aside.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _importcode import PROJECT, imported  # noqa: E402

from fenolite import __version__  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "import_python"
FLAGS = (
    "--licence", "CC0-1.0", "--copyright", "2026 Fenolite contributors",
    "--source", "https://github.com/lgili/Fenolite", "--revision", "main",
)  # fmt: skip
MARKER = "# Authored for Fenolite: imported from tests/data/import_python/two_sheet, authored for Fenolite."
HEADER_LINES = 4
KEPT = ("README.md",)
"""Files of the example that the import does not write."""


def fresh(folder: Path) -> dict[str, bytes]:
    """The files of the example as a fresh import into ``folder`` gives them, marked."""
    reply = imported(folder, PROJECT, *FLAGS, "--confirm")
    if reply.exit_code != 0:
        raise RuntimeError(f"the import failed: {reply.error}")
    out = folder / "out"
    files: dict[str, bytes] = {}
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        if path.suffix == ".py":
            lines = data.decode("utf-8").split("\n")
            data = "\n".join([*lines[:HEADER_LINES], MARKER, *lines[HEADER_LINES:]]).encode("utf-8")
        files[path.relative_to(out).as_posix()] = data
    return files


def unversioned(data: bytes) -> bytes:
    """``data`` with the running Fenolite version written as ``VERSION``."""
    return data.replace(__version__.encode("utf-8"), b"VERSION")


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        files = fresh(Path(folder))
    for path in EXAMPLE.rglob("*"):
        if path.is_file() and path.name not in KEPT:
            path.unlink()
    for name, data in files.items():
        target = EXAMPLE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for folder in sorted((p for p in EXAMPLE.rglob("*") if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            shutil.rmtree(folder)


if __name__ == "__main__":
    main()
