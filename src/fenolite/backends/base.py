# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The backend protocol: what every file-format backend offers, independent of any one backend.

``checks``, ``placement`` and the CLI reach backends only through this module and
``fenolite.backends.registry``. It imports only ``core`` and ``model``; a backend never imports
another backend.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol, runtime_checkable

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design
from fenolite.model.library import Library

BackendOperation = Literal["detect", "read", "write", "lower", "validate"]
Downgrade = Literal["unsupported", "supported"]


@dataclass(frozen=True, slots=True)
class ReadResult:
    """What ``Backend.read`` returns: a ``Design`` for a board, a ``Library`` for library files."""

    content: Design | Library
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = Evidence()

    @property
    def design(self) -> Design:
        """The content when it is a ``Design``; ``TypeError`` for a library."""
        if not isinstance(self.content, Design):
            raise TypeError(f"read result holds a {type(self.content).__name__}, not a Design")
        return self.content


@dataclass(frozen=True, slots=True)
class WriteResult:
    """What a backend writer returns: the file text and the warnings and infos of the write.

    Errors are raised, never returned, so a caller cannot write a file that lost content silently.
    """

    text: str
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class DrcItem:
    """A board item a DRC violation names: its uuid, the tool's description, and a report position."""

    uuid: str
    description: str
    position: Point

    def __post_init__(self) -> None:
        if type(self.position.x) is not int or type(self.position.y) is not int:
            raise TypeError(f"DRC positions are integer nanometres, got {self.position!r}")


@dataclass(frozen=True, slots=True)
class DrcViolation:
    """One violation of a DRC report; ``type`` and ``severity`` are the tool's own strings."""

    type: str
    description: str
    severity: str
    items: tuple[DrcItem, ...] = ()
    excluded: bool = False
    comment: str = ""


@dataclass(frozen=True, slots=True)
class DrcReport:
    """A DRC report in report order, independent of the tool that wrote it."""

    source: str
    date: str
    kicad_version: str
    coordinate_units: str
    violations: tuple[DrcViolation, ...] = ()
    unconnected_items: tuple[DrcViolation, ...] = ()
    schematic_parity: tuple[DrcViolation, ...] = ()
    ignored_checks: tuple[str, ...] = ()
    included_severities: tuple[str, ...] = ()

    def of_type(self, type: str) -> tuple[DrcViolation, ...]:  # noqa: A002 (the report's own key)
        """The violations, unconnected items and parity items of ``type``, in report order."""
        groups = (self.violations, self.unconnected_items, self.schematic_parity)
        return tuple(v for group in groups for v in group if v.type == type)


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    """What a backend can do here. ``operations`` lists only what is implemented."""

    name: str
    read_kinds: tuple[str, ...]
    write_kinds: tuple[str, ...] = ()
    targets: tuple[int, ...] = ()
    default_target: int | None = None
    downgrade: Downgrade = "unsupported"
    operations: tuple[BackendOperation, ...] = ("detect", "read")
    evidence: Evidence = Evidence()

    def to_json(self) -> dict[str, Any]:
        """A JSON-compatible mapping with exactly the report's fields."""
        return {
            "name": self.name,
            "read_kinds": list(self.read_kinds),
            "write_kinds": list(self.write_kinds),
            "targets": list(self.targets),
            "default_target": self.default_target,
            "downgrade": self.downgrade,
            "operations": list(self.operations),
            "evidence": {
                "level": self.evidence.level.value,
                "oracle": self.evidence.oracle,
                "hypotheses": list(self.evidence.hypotheses),
            },
        }


SkipReason = Literal[
    "outside-root", "variable", "relative", "missing", "nested-table", "too-large", "reserved-name"
]


@dataclass(frozen=True, slots=True)
class SkippedFile:
    """A file or folder that a project names but that is not copied for an oracle run, and why."""

    name: str
    reason: SkipReason


@dataclass(frozen=True, slots=True)
class ProjectSet:
    """The closed set of project files an oracle sees: POSIX names relative to ``root`` → source paths.

    ``board`` is one of the names; ``has_project`` and ``has_rules`` say whether the board's project and
    rules files are among them.
    """

    root: Path
    board: str
    files: Mapping[str, Path]
    skipped: tuple[SkippedFile, ...] = ()
    has_project: bool = False
    has_rules: bool = False

    def __post_init__(self) -> None:
        for name in self.files:
            rel = PurePosixPath(name)
            if not name or rel.is_absolute() or ".." in rel.parts or "\\" in name or rel.as_posix() != name:
                raise ValueError(f"project file name {name!r} is not a relative POSIX name")
        if self.board not in self.files:
            raise ValueError(f"the board {self.board!r} is not one of the project files")


@dataclass(frozen=True, slots=True)
class RoundTrip:
    """A same-version rebuild verdict: ``passed`` is the conjunction of the three equalities.

    ``difference`` locates the first failing part (a tree locator, ``model`` or ``opaque``), ``""`` when
    it passed.
    """

    level: Literal["RT1"]
    passed: bool
    tree_equal: bool
    model_equal: bool
    opaque_equal: bool
    opaque_count: int
    difference: str = ""

    def __post_init__(self) -> None:
        if self.passed != (self.tree_equal and self.model_equal and self.opaque_equal):
            raise ValueError("RoundTrip.passed must equal tree_equal and model_equal and opaque_equal")


@dataclass(frozen=True, slots=True)
class Validation:
    """What ``Validator.validate`` returns: the read and its round-trip verdict."""

    read: ReadResult
    roundtrip: RoundTrip


@runtime_checkable
class Validator(Protocol):
    """A backend that validates a file: reads it and checks its round trip.

    ``validate`` raises the reader's ``FormatError`` (subclasses included) for a file it cannot read, and
    ``ValueError`` naming the kind for a kind it cannot validate.
    """

    name: str

    def validate(self, path: Path, *, issues: list[Issue] | None = None) -> Validation: ...


CanaryState = Literal["fired", "absent", "inconclusive", "not-applicable"]


@dataclass(frozen=True, slots=True)
class DrcOutcome:
    """An oracle's DRC run: the report (``None`` when none was written, canary items removed), the canary
    state, the files the tool wrote in its copy, and the evidence of the run."""

    report: DrcReport | None
    tool_version: str
    canary: CanaryState
    canary_reason: str = ""
    canary_removed: int = 0
    tool_writes: tuple[str, ...] = ()
    outcome: Literal["exit", "timeout"] = "exit"
    returncode: int | None = 0
    message: str = ""
    evidence: Evidence = Evidence()


class Oracle(Protocol):
    """An external tool that gives DRC verdicts on a project copy set; it never writes under its root and
    reports a timeout as ``outcome == "timeout"``."""

    name: str

    def version(self) -> str: ...

    def drc(self, project: ProjectSet) -> DrcOutcome: ...


class Backend(Protocol):
    """A file-format backend.

    ``detect`` decides from the path alone, without reading the file. ``read`` appends warnings and
    infos to ``issues`` when a list is given and raises errors as exceptions that carry a registered
    ``cli_code`` or are ``FormatError``s.
    """

    name: str

    def detect(self, path: Path) -> bool: ...

    def read(self, path: Path, *, issues: list[Issue] | None = None) -> ReadResult: ...

    def capabilities(self) -> CapabilityReport: ...


__all__ = [
    "Backend",
    "BackendOperation",
    "CanaryState",
    "CapabilityReport",
    "Downgrade",
    "DrcItem",
    "DrcOutcome",
    "DrcReport",
    "DrcViolation",
    "Oracle",
    "ProjectSet",
    "ReadResult",
    "RoundTrip",
    "SkipReason",
    "SkippedFile",
    "Validation",
    "Validator",
    "WriteResult",
]
