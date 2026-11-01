# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The inputs of an import (change c0275, design decision 2): a KiCad project, board or schematic read
into the model with its project file, every file read recorded by base name and SHA-256.

A board below the read floor is passed to ``upgrade``, the caller's upgrade on a private copy
(``importer.upgrade``); without one it raises ``UnsupportedFormatError`` (``FEN-3003``). Nothing is
written and no process is started here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.kicad import parity_inputs
from fenolite.backends.kicad.dru import read_rules
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.pro import apply_project, project_minimums, read_project
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import (
    FileKind,
    UnsupportedFormatError,
    VersionStatus,
    inspect,
    require_readable,
)
from fenolite.core.errors import FenoliteError, Issue
from fenolite.model.design import Design
from fenolite.model.rules import Rule

KICAD_SUFFIXES = (".kicad_pro", ".kicad_pcb", ".kicad_sch")
ALTIUM_SUFFIXES = (".prjpcb", ".pcbdoc")
KNOWN_KINDS: Mapping[str, str] = {
    ".brd": "an Eagle or Allegro board",
    ".sch": "an Eagle or legacy KiCad schematic",
    ".json": "an EasyEDA document",
    ".mod": "a legacy KiCad footprint library",
    ".lib": "a legacy KiCad symbol library",
    ".kicad_mod": "a KiCad footprint",
    ".kicad_sym": "a KiCad symbol library",
}
"""Input kinds the import names when it refuses them (``FEN-2001``)."""


class InputKindError(FenoliteError):
    """An input the import does not read (``FEN-2001``): the message names its kind."""

    cli_code = "FEN-2001"

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint


@dataclass(frozen=True, slots=True)
class InputFile:
    """One file read: its base name, SHA-256 of its original bytes, format and format version."""

    file: str
    sha256: str
    format: str
    version: int | None = None

    def as_json(self) -> dict[str, object]:
        return {"file": self.file, "sha256": self.sha256, "format": self.format, "version": self.version}


@dataclass(frozen=True, slots=True)
class Upgrade:
    """One upgrade of a file on a private copy (decision 13)."""

    file: str
    tool: str
    tool_version: str
    from_version: int
    to_version: int | None
    sha256_before: str
    sha256_after: str

    def as_json(self) -> dict[str, object]:
        return {
            "file": self.file,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "sha256_before": self.sha256_before,
            "sha256_after": self.sha256_after,
        }


Upgrader = Callable[[Path, FileKind], tuple[bytes, Upgrade]]
"""The caller's upgrade of a file below the read floor: its upgraded bytes and the record."""


@dataclass(frozen=True, slots=True)
class Source:
    """What an import reads: the design name, the backend, the model (board and project classes), the
    KiCad board text (upgraded when it was), the board's major, the inputs, the upgrades, the project
    minimums by rule kind, the rules of the custom rules file, the count of schematic sheets, the reader's
    issues and every path read."""

    name: str
    backend: str
    design: Design
    board_text: str
    major: int
    inputs: tuple[InputFile, ...]
    upgrades: tuple[Upgrade, ...] = ()
    minimums: Mapping[str, int] = field(default_factory=lambda: {})
    custom_rules: tuple[Rule, ...] = ()
    sheets: int = 0
    issues: tuple[Issue, ...] = ()
    paths: tuple[Path, ...] = ()
    folder: Path = Path()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_kind(path: Path) -> str:
    """``kicad`` or ``altium`` for an input the import reads; ``InputKindError`` naming the kind else."""
    suffix = path.suffix.lower()
    if suffix in KICAD_SUFFIXES:
        return "kicad"
    if suffix in ALTIUM_SUFFIXES:
        return "altium"
    kind = KNOWN_KINDS.get(suffix, f"a {suffix or 'suffix-less'} file")
    raise InputKindError(
        f"import does not read {path.name}: it is {kind}",
        hint="pass a .kicad_pro, .kicad_pcb, .kicad_sch, .PrjPcb or .PcbDoc",
    )


def _board_path(path: Path) -> Path:
    board = path.with_suffix(".kicad_pcb")
    if not board.is_file():
        raise InputKindError(
            f"{path.name} has no board {board.name} beside it; import reads a board",
            hint="pass the project of a board",
        )
    return board


def read_kicad(path: Path, *, upgrade: Upgrader | None = None) -> Source:
    """The KiCad project of ``path`` (a ``.kicad_pro``, ``.kicad_pcb`` or ``.kicad_sch``): its board with
    the classes of its project file, the minimums and custom rules, and the count of schematic sheets."""
    board_path = path if path.suffix == ".kicad_pcb" else _board_path(path)
    folder = board_path.parent
    stem = board_path.stem
    data = board_path.read_bytes()
    inputs: list[InputFile] = []
    upgrades: list[Upgrade] = []
    paths: list[Path] = [board_path]
    text = data.decode("utf-8")
    info = inspect(parse(text), file=board_path.name)
    inputs.append(InputFile(board_path.name, _sha(data), "kicad_pcb", info.version))
    if info.status == VersionStatus.TOO_OLD:
        if upgrade is None:
            require_readable(info, file=board_path.name)
            raise UnsupportedFormatError(f"{board_path.name} is too old", file=board_path.name)
        upgraded, row = upgrade(board_path, FileKind.BOARD)
        upgrades.append(row)
        text = upgraded.decode("utf-8")
        info = inspect(parse(text), file=board_path.name)
    issues: list[Issue] = []
    design = read_board(text, file=board_path.name)
    major = info.major if info.major is not None else 10
    minimums: dict[str, int] = {}
    project = folder / f"{stem}.kicad_pro"
    if project.is_file():
        raw = project.read_bytes()
        paths.append(project)
        found = read_project(raw.decode("utf-8"), file=project.name, issues=issues)
        inputs.append(InputFile(project.name, _sha(raw), "kicad_pro", found.meta_version))
        design = apply_project(design, found, issues=issues)
        minimums = project_minimums(found.data, issues=issues)
    rules: tuple[Rule, ...] = ()
    dru = folder / f"{stem}.kicad_dru"
    if dru.is_file():
        raw = dru.read_bytes()
        paths.append(dru)
        inputs.append(InputFile(dru.name, _sha(raw), "kicad_dru", None))
        ruleset = read_rules(raw.decode("utf-8"), file=dru.name, issues=issues)
        rules = ruleset.rules
    sheets = 0
    root = folder / f"{stem}.kicad_sch"
    if root.is_file():
        read = parity_inputs.read_sheets(root)
        sheets = len(read)
        for name in read:
            sheet = folder / name
            raw = sheet.read_bytes()
            paths.append(sheet)
            inputs.append(InputFile(Path(name).as_posix(), _sha(raw), "kicad_sch", None))
    return Source(
        name=stem,
        backend="kicad",
        design=design,
        board_text=text,
        major=major,
        inputs=tuple(inputs),
        upgrades=tuple(upgrades),
        minimums=minimums,
        custom_rules=rules,
        sheets=sheets,
        issues=tuple(i for i in issues if i.severity != "error"),
        paths=tuple(paths),
        folder=folder,
    )


__all__ = [
    "ALTIUM_SUFFIXES",
    "KICAD_SUFFIXES",
    "InputFile",
    "InputKindError",
    "Source",
    "Upgrade",
    "Upgrader",
    "input_kind",
    "read_kicad",
]
