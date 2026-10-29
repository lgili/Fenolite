# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Old KiCad inputs upgraded on private copies (change c0275, design decision 13).

``kicad-cli pcb upgrade`` (or ``sch upgrade``) runs on copies of the project's files in a private temporary
folder (``KicadCli`` copies them, runs the tool there and deletes them); the source is never touched. Each
upgrade is one ``Upgrade`` record: the tool and its version, the format versions and the SHA-256 before and
after. Without ``kicad-cli`` the import exits 6 (``FEN-6001``); a ``kicad-cli`` without ``pcb upgrade``
(9.0) raises ``KicadCliVersionError`` (``FEN-6002``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fenolite.backends.kicad.cli import cli_for
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import FileKind, inspect
from fenolite.core.errors import FenoliteError
from fenolite.importer.source import Upgrade, Upgrader

PROJECT_SUFFIXES = (".kicad_pro", ".kicad_sch", ".kicad_prl", ".kicad_dru")
TABLES = ("fp-lib-table", "sym-lib-table")
NO_TOOL_HINT = (
    "install KiCad 10 (kicad-cli) or set FENOLITE_KICAD_CLI; or pass --no-upgrade to refuse the old file"
)


class UpgradeToolMissingError(FenoliteError):
    """An input below the read floor and no ``kicad-cli`` to upgrade it (``FEN-6001``)."""

    cli_code = "FEN-6001"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.hint = NO_TOOL_HINT


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _companions(path: Path) -> dict[str, Path]:
    """The project files beside ``path`` that the tool may read: project, sheets, rules and tables."""
    found: dict[str, Path] = {}
    for sibling in sorted(path.parent.iterdir()):
        if sibling == path or not sibling.is_file():
            continue
        if sibling.suffix in PROJECT_SUFFIXES or sibling.name in TABLES:
            found[sibling.name] = sibling
    return found


def upgrader(tool: Path | None, *, timeout: float = 120) -> Upgrader:
    """The upgrade of ``source.read_kicad`` with the ``kicad-cli`` at ``tool`` (``None``: none found)."""

    def run(path: Path, kind: FileKind) -> tuple[bytes, Upgrade]:
        before = path.read_bytes()
        old = inspect(parse(before.decode("utf-8")), file=path.name)
        if tool is None:
            raise UpgradeToolMissingError(
                f"{path.name} has format version {old.version}, below the read floor, and no kicad-cli is "
                "found to upgrade a copy of it"
            )
        cli = cli_for(tool, timeout=timeout)
        files = _companions(path)
        if kind == FileKind.BOARD:
            after = cli.upgrade_board(path, files=files)
        else:
            after = cli.upgrade_schematic(path, files=files)
        new = inspect(parse(after.decode("utf-8")), file=path.name)
        return after, Upgrade(
            file=path.name,
            tool="kicad-cli",
            tool_version=cli.version(),
            from_version=old.version,
            to_version=new.version,
            sha256_before=_sha(before),
            sha256_after=_sha(after),
        )

    return run


__all__ = ["NO_TOOL_HINT", "UpgradeToolMissingError", "upgrader"]
