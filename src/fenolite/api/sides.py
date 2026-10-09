# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The sides of a comparison (capability design-equivalence, "Equivalent command" and "Public equivalence
API"; change c0158).

A side is a built design (a ``.fenolite/`` folder), a KiCad project resolved to its board, any file a
backend reads, or a ``Design`` given directly. The triangle's side ``b`` is the board that ``kicad-cli pcb
import`` converts an Altium PCB document to. The faults of a side are typed: a usage fault is a
``ValueError`` (``SideUsageError``), and every error carries the ``FEN-NNNN`` code the command reports, the
place it names and its hint.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, KicadCliVersionError, cli_for, find_kicad_cli
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.checks.equivalence import codes as equivalence_codes
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

BUILT_FILES = ("meta.json", "build.json")
"""A folder that holds one of these directly is a built design (a ``.fenolite/`` folder)."""
BUILT_BACKEND = "fenolite"
BUILT_EVIDENCE = Evidence(Level.INFERRED)
MODEL_BACKEND = "model"
MODEL_EVIDENCE = Evidence(Level.INFERRED)
"""The evidence of a design given directly, as of a built design: nothing says what wrote it."""
DEFAULT_TIMEOUT = 300.0
IMPORT_MAJOR = 10
NO_TOOL_HINT = "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli"
READS = (
    "a KiCad board, project file or folder, an Altium document or project, or a .fenolite/ folder of a "
    "built design"
)


class SideError(FenoliteError):
    """A side that cannot be read or compared: ``cli_code`` is the command's code, ``where`` the place it
    names and ``hint`` what to do (``None``: the code's own hint)."""

    cli_code = "FEN-2001"

    def __init__(self, message: str, *, where: str = "", hint: str | None = None) -> None:
        self.message = message
        self.where = where
        self.hint = hint
        super().__init__(message)


class SideUsageError(SideError, ValueError):
    """A usage fault (``FEN-2001``): a path no backend reads, a library, a bad option."""


class SideMissingError(SideError):
    """A path that does not exist (``FEN-3001``)."""

    cli_code = "FEN-3001"


class ToolMissingError(SideError):
    """No ``kicad-cli`` where one is needed (``FEN-6001``)."""

    cli_code = "FEN-6001"


class ToolMajorError(SideError):
    """A ``kicad-cli`` of another major than the triangle needs (``FEN-6002``)."""

    cli_code = "FEN-6002"


@dataclass(frozen=True, slots=True)
class ReadSide:
    """One side as read: its name (the file or folder name, no folder), the SHA-256 of a file, the backend,
    the design, the reader's warnings and infos, the evidence, the input kind, and for the triangle's side
    ``b`` the version and messages of ``kicad-cli``."""

    name: str
    sha256: str | None
    backend: str
    design: Design
    issues: tuple[Issue, ...]
    evidence: Evidence
    kind: str
    tool_version: str | None = None
    messages: tuple[str, ...] = ()
    netlist_source: str | None = None
    """``schematic`` for a schematic side; ``None``: ``board`` when the design holds footprints, else
    ``circuit``."""
    power_symbols: int | None = None
    """The power symbols of a schematic side, which its circuit leaves out."""


def existing(path: Path) -> Path:
    """``path`` when it exists, else ``SideMissingError``."""
    if not path.exists():
        raise SideMissingError(f"{path.name} does not exist", where=path.name)
    return path


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def notices(issues: list[Issue] | tuple[Issue, ...]) -> tuple[Issue, ...]:
    """The warnings and infos of a read; a reader raises its errors."""
    return tuple(issue for issue in issues if issue.severity != "error")


def read_path(path: Path) -> ReadSide:
    """One side: a built design, a KiCad project resolved to its board, or any file a backend reads."""
    if path.is_dir() and any((path / name).is_file() for name in BUILT_FILES):
        return ReadSide(path.name, None, BUILT_BACKEND, load_dir(path), (), BUILT_EVIDENCE, "fenolite_model")
    if path.is_dir() or path.suffix == ".kicad_pro":
        path = resolve_board(path)
    backend = registry.for_path(path)
    if backend is None:
        raise SideUsageError(
            f"equivalent does not read {path.name}", where=path.name, hint="it reads " + READS
        )
    found: list[Issue] = []
    read = backend.read(path, issues=found)
    if not isinstance(read.content, Design):
        raise SideUsageError(
            f"{path.name} is a library, not a design", where=path.name, hint="compare libraries with diff"
        )
    kind = path.suffix.lower().lstrip(".")
    return ReadSide(path.name, _digest(path), backend.name, read.content, notices(found), read.evidence, kind)


def model_side(design: Design) -> ReadSide:
    """A design given directly: backend ``model``, no digest, the evidence ``INFERRED``."""
    return ReadSide(design.header.name, None, MODEL_BACKEND, design, (), MODEL_EVIDENCE, MODEL_BACKEND)


def read_side(
    given: str | Path | Design, *, kicad_cli: str | None = None, timeout: float = DEFAULT_TIMEOUT
) -> ReadSide:
    """One side of a comparison: a design given directly, or the path of any side ``read_path`` reads.
    ``kicad_cli`` and ``timeout`` serve a side that needs the tool."""
    del kicad_cli, timeout  # no side of this kind runs a tool yet
    if isinstance(given, Design):
        return model_side(given)
    return read_path(existing(Path(given)))


def import_tool(explicit: str | None, timeout: float) -> KicadCli:
    """The ``kicad-cli`` that converts the triangle's side ``a``: ``ToolMissingError`` without one,
    ``ToolMajorError`` for another major than 10. No import runs before both hold."""
    path = find_kicad_cli(explicit)
    if path is None:
        raise ToolMissingError("kicad-cli not found", hint=NO_TOOL_HINT)
    cli = cli_for(path, timeout=timeout)
    try:
        major = cli.major()
    except (KicadCliError, ValueError, OSError) as exc:
        raise ToolMissingError(f"{path.name} did not report a kicad-cli version", hint=NO_TOOL_HINT) from exc
    if major != IMPORT_MAJOR:
        raise ToolMajorError(
            f"--against kicad-import needs kicad-cli 10.0 (pcb import); running {cli.version()}",
            hint="use kicad-cli 10.0, for example the kicad-10 job's container",
        )
    return cli


def imported(cli: KicadCli, source: Path, name: str) -> ReadSide | Issue:
    """Side ``b`` of the triangle, or the ``equiv.oracle-failed`` issue of a run that gives no board."""
    try:
        found = altium_import.import_design(cli, source)
    except KicadCliVersionError:
        raise
    except FenoliteError as error:
        return equivalence_codes.issue("equiv.oracle-failed", str(error), where=name)
    read = found.read
    return ReadSide(
        name, None, altium_import.PROFILE, read.design, notices(read.issues), read.evidence, "kicad_pcb",
        found.tool_version, found.messages,
    )  # fmt: skip


__all__ = [
    "BUILT_BACKEND",
    "BUILT_EVIDENCE",
    "BUILT_FILES",
    "DEFAULT_TIMEOUT",
    "IMPORT_MAJOR",
    "MODEL_BACKEND",
    "MODEL_EVIDENCE",
    "NO_TOOL_HINT",
    "READS",
    "ReadSide",
    "SideError",
    "SideMissingError",
    "SideUsageError",
    "ToolMajorError",
    "ToolMissingError",
    "existing",
    "import_tool",
    "imported",
    "model_side",
    "notices",
    "read_path",
    "read_side",
]
