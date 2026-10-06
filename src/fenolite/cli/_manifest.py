# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the producing commands share for ``--manifest``: the manifest of their output folder, merged with
the files they write (capability cli-contract, "Manifest option of producing commands";
manufacturing-exports, "Manifest merging"; user guide ``docs/exports.md``)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from fenolite import __version__
from fenolite.cli.api import Context, PlannedWrite
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.exports import manifest
from fenolite.exports.codes import issue

FENOLITE_TOOL = manifest.ToolRef("fenolite", __version__)
FENOLITE = f"{FENOLITE_TOOL.name} {FENOLITE_TOOL.version}"
"""The ``tool`` of an entry that Fenolite rendered itself."""
UNREADABLE_HINT = "move the file away, or write a new one with 'fenolite manifest'; nothing was written"


def joined(folder: str, name: str) -> str:
    """``name`` below ``folder``, as the path of a planned write (POSIX)."""
    return (PurePosixPath(Path(folder).as_posix()) / name).as_posix()


def read_folder(folder: Path, *, where: str) -> tuple[manifest.Manifest | None, Issue | None]:
    """The manifest of ``folder``: ``(None, None)`` without one, and ``manifest.unreadable`` for a file
    that ``manifest.load`` refuses. ``where`` is the path the issue names."""
    path = folder / manifest.FILE_NAME
    if not path.is_file():
        return None, None
    try:
        return manifest.load(path.read_bytes().decode("utf-8"), file=manifest.FILE_NAME), None
    except (FormatError, OSError, UnicodeDecodeError) as exc:
        reason = exc.message if isinstance(exc, FormatError) else type(exc).__name__
        located = exc.locator if isinstance(exc, FormatError) else ""
        text = f"{where} is not a manifest Fenolite reads: {reason}" + (f" at {located}" if located else "")
        return None, issue("manifest.unreadable", text, where=where, hint=UNREADABLE_HINT)


def merged_write(
    folder: str,
    ctx: Context,
    entries: Sequence[manifest.ArtifactEntry],
    *,
    board: manifest.BoardRef,
    tool: manifest.ToolRef,
) -> tuple[PlannedWrite | None, Issue | None]:
    """The planned manifest of ``folder`` (a path as the user wrote it) after ``entries`` are written into
    it, or the issue that refuses it: a command then plans no file at all."""
    target = joined(folder, manifest.FILE_NAME)
    existing, problem = read_folder(ctx.cwd / folder, where=target)
    if problem is not None:
        return None, problem
    merged = manifest.merge(existing, entries, board=board, tool=tool, timestamp=ctx.timestamp)
    text = manifest.dumps(manifest.to_data(merged)).encode("utf-8")
    return PlannedWrite(target, text, "manifest"), None


def with_manifest(
    writes: Sequence[PlannedWrite],
    folder: str,
    ctx: Context,
    entries: Sequence[manifest.ArtifactEntry],
    *,
    board: manifest.BoardRef,
    tool: manifest.ToolRef,
) -> tuple[tuple[PlannedWrite, ...], tuple[Issue, ...]]:
    """``writes`` followed by the merged manifest of ``folder``; or no write at all and the issue, when
    the folder holds a manifest that cannot be read."""
    planned, refused = merged_write(folder, ctx, entries, board=board, tool=tool)
    if refused is not None or planned is None:
        return (), () if refused is None else (refused,)
    return (*writes, planned), ()


def table_manifest(
    writes: Sequence[PlannedWrite],
    ctx: Context,
    *,
    evidence: str,
    board: manifest.BoardRef,
) -> tuple[tuple[PlannedWrite, ...], tuple[Issue, ...]]:
    """The one table that ``bom`` or ``pnp`` plans with ``--out FILE``, and the manifest of the folder of
    ``FILE`` with its entry: made from the board, by Fenolite, at the level the command gives its rows."""
    entries = [
        manifest.file_entry(
            PurePosixPath(Path(w.path).as_posix()).name,
            w.kind,
            w.data,
            evidence=evidence,
            from_={"board": board.sha256},
            tool=FENOLITE,
        )
        for w in writes
    ]
    folder = Path(writes[0].path).parent.as_posix() if writes else "."
    return with_manifest(writes, folder, ctx, entries, board=board, tool=FENOLITE_TOOL)


def needs_out(command: str, args_manifest: bool, out: str | None) -> None:
    """``--manifest`` names the folder of ``--out FILE``: without a file there is no folder."""
    if args_manifest and out is None:
        raise CliError(
            "FEN-2001",
            f"--manifest needs --out FILE: the manifest is written into the folder of the {command} file",
            hint="pass --out FILE, or drop --manifest",
            where="--manifest",
        )


__all__ = [
    "FENOLITE",
    "FENOLITE_TOOL",
    "joined",
    "merged_write",
    "needs_out",
    "read_folder",
    "table_manifest",
    "with_manifest",
]
