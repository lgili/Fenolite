# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exceptions and findings shared by every package."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warning", "info"]
SEVERITIES: tuple[Severity, ...] = ("error", "warning", "info")
ISSUE_CODE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z0-9-]+)+$")


@dataclass(frozen=True, slots=True)
class Issue:
    """A finding reported by a command. Findings of severity ``error`` make the exit code 5."""

    code: str = field(metadata={"pattern": ISSUE_CODE.pattern})
    severity: Severity
    message: str
    where: str = ""
    hint: str = ""
    retryable: bool = False

    def __post_init__(self) -> None:
        if not ISSUE_CODE.match(self.code):
            raise ValueError(
                f"invalid issue code {self.code!r}: use dotted lowercase, e.g. 'model.duplicate-ref'"
            )
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity {self.severity!r}")


class FenoliteError(Exception):
    """Base class of Fenolite exceptions."""


class FormatError(FenoliteError):
    """Malformed input: ``file``, ``locator`` (e.g. a JSON pointer) and byte ``offset`` locate it."""

    def __init__(self, message: str, *, file: str = "", locator: str = "", offset: int | None = None) -> None:
        self.file = file
        self.locator = locator
        self.offset = offset
        self.message = message
        where = ":".join(part for part in (file, locator, "" if offset is None else f"@{offset}") if part)
        super().__init__(f"{where}: {message}" if where else message)


class ConsistencyError(FenoliteError):
    """An operation would break an invariant of the model."""


__all__ = [
    "ISSUE_CODE",
    "SEVERITIES",
    "ConsistencyError",
    "FenoliteError",
    "FormatError",
    "Issue",
    "Severity",
]
