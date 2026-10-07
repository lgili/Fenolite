# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files that a command's examples need in the working directory (change c0066).

Most commands take their example input from the test data and write somewhere new, so their examples run
in an empty folder. ``fmt`` rewrites the file it is given and ``restore`` puts back the backups of an
earlier write: their examples name files that the suites prepare here first (capability cli-contract,
"Fmt command" and "Restore command").
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from fenolite.cli.cmd_fmt import EXAMPLE_COPY
from fenolite.cli.cmd_restore import EXAMPLE_RECEIPT

BOARD = Path(__file__).resolve().parent / "data" / "kicad" / "board" / "two_layer.kicad_pcb"


def _fmt(folder: Path) -> None:
    """A copy of the authored board that is not canonical: two blanks after its first head."""
    text = BOARD.read_text(encoding="utf-8")
    assert text.startswith("(kicad_pcb\n")
    (folder / EXAMPLE_COPY).write_bytes(text.replace("(kicad_pcb\n", "(kicad_pcb  \n", 1).encode("utf-8"))


def _restore(folder: Path) -> None:
    """The state after an overwrite: a file holding ``two``, its backup holding ``one``, and the receipt
    of that write as a bare object."""
    name = "fenolite-restore-example.txt"
    (folder / name).write_bytes(b"two\n")
    (folder / (name + ".bak")).write_bytes(b"one\n")
    receipt = {
        "written": [{"path": name, "sha256": hashlib.sha256(b"two\n").hexdigest()}],
        "backup": [name + ".bak"],
    }
    (folder / EXAMPLE_RECEIPT).write_bytes((json.dumps(receipt) + "\n").encode("utf-8"))


PREPARED: dict[str, Callable[[Path], None]] = {"fmt": _fmt, "restore": _restore}
"""Command name → the function that writes its example files into a folder."""
PLANS_NOTHING = frozenset({"models"})
"""Mutating commands whose mutation example plans no write: ``models --vendor`` on the example board,
whose footprints name no 3D model (cli-contract, "Models command": both examples exit 0 and run no
subprocess; change c0116). The protocol with a real plan is tested in
``tests/unit/cli/test_models_cmd.py``."""


def prepare_example(name: str, folder: Path) -> None:
    """Write the example files of command ``name`` into ``folder``; nothing for most commands."""
    prepare = PREPARED.get(name)
    if prepare is not None:
        prepare(folder)


def folder_snapshot(folder: Path) -> dict[str, str]:
    """Every file under ``folder`` by POSIX name → SHA-256, so a test can prove nothing was written."""
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


__all__ = ["PLANS_NOTHING", "PREPARED", "folder_snapshot", "prepare_example"]
