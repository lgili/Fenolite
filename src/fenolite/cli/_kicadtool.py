# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pre-flight shared by the commands that run ``kicad-cli`` on a board (``check``, ``export``,
``render``): a supported binary that reads this board's format, or a typed error (``docs/cli-contract.md``,
"check")."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad import versions
from fenolite.backends.kicad.cli import DOCKER_PREFIX, KicadCli, KicadCliError, cli_for, find_kicad_cli
from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError

DEFAULT_TIMEOUT = 300.0
NO_TOOL_HINT = "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli"


def board_format(board: Path) -> int | None:
    """The format version in the board's header, or ``None`` when Fenolite cannot read it."""
    try:
        return versions.inspect(parse_bytes(board.read_bytes(), file=board.name), file=board.name).version
    except (FormatError, OSError):
        return None


def preflight(explicit: str | None, timeout: float, board: Path, *, hint: str = NO_TOOL_HINT) -> KicadCli:
    """The ``kicad-cli`` to run on ``board``: ``FEN-6001`` when none is found or it reports no version,
    ``FEN-6002`` for an unsupported major or a board newer than the tool reads."""
    path = find_kicad_cli(explicit)
    if path is None:
        raise CliError("FEN-6001", "kicad-cli not found", hint=hint)
    cli = cli_for(path, timeout=timeout)
    try:
        major = cli.major()
    except (KicadCliError, ValueError, OSError) as exc:
        if str(path).startswith(DOCKER_PREFIX):
            hint = f"docker pull {str(path)[len(DOCKER_PREFIX) :]}"
        raise CliError("FEN-6001", f"{path.name} did not report a kicad-cli version", hint=hint) from exc
    if major not in versions.TARGET_MAJORS:
        raise CliError("FEN-6002", f"kicad-cli {cli.version()} is not supported",
                       hint=f"use kicad-cli {' or '.join(map(str, versions.TARGET_MAJORS))}")  # fmt: skip
    try:
        info = versions.inspect(parse_bytes(board.read_bytes(), file=board.name), file=board.name)
    except (FormatError, OSError):
        info = None  # the header check is skipped; KiCad decides
    limit = versions.FORMAT_VERSIONS[versions.FileKind.BOARD][major]
    if info is not None and (info.status is versions.VersionStatus.FUTURE or info.version > limit):
        raise CliError("FEN-6002", f"{board.name} (format {info.version}) is newer than kicad-cli "
                       f"{cli.version()} reads", hint="run a newer kicad-cli")  # fmt: skip
    return cli


__all__ = ["DEFAULT_TIMEOUT", "NO_TOOL_HINT", "board_format", "preflight"]
