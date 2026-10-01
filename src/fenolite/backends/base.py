# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The backend protocol: what every file-format backend offers, independent of any one backend.

``checks``, ``placement`` and the CLI reach backends only through this module and
``fenolite.backends.registry``. It imports only ``core`` and ``model``; a backend never imports
another backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

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


__all__ = ["Backend", "BackendOperation", "CapabilityReport", "Downgrade", "ReadResult"]
