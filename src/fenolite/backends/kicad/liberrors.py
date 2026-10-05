# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Issue codes of KiCad library reading and resolution, and the exception that carries the errors.

A leaf module (it imports only ``core``), so ``sym`` and ``libs`` can both raise ``LibraryError``
without importing each other. The closed set is the table of ``docs/formats/kicad/libraries.md``.
"""

# evidence: none, issue codes and the error class of library reading

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from fenolite.core.errors import FenoliteError, Issue, Severity

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.lib.invalid-id": "error",
        "kicad.lib.unknown-nickname": "error",
        "kicad.lib.disabled": "error",
        "kicad.lib.unsupported-type": "error",
        "kicad.lib.unresolved-variable": "error",
        "kicad.lib.missing-library": "error",
        "kicad.lib.missing-entry": "error",
        "kicad.lib.missing-parent": "error",
        "kicad.lib.extends-cycle": "error",
        "kicad.lib.duplicate-nickname": "warning",
        "kicad.lib.table-cycle": "warning",
        "kicad.lib.missing-table": "warning",
        "kicad.lib.name-mismatch": "warning",
        "kicad.lib.missing-3d-model": "warning",
        "kicad.lib.kept-opaque": "info",
        "kicad.lib.nested-table-target": "info",
    }
)


def lib_issue(code: str, message: str, *, where: str = "", hint: str = "") -> Issue:
    """An issue of the closed set, with the severity the table gives its code."""
    severity = ISSUE_CODES.get(code)
    if severity is None:
        raise ValueError(f"{code!r} is not a KiCad library issue code")
    return Issue(code, severity, message, where=where, hint=hint)


class LibraryError(FenoliteError):
    """A library item cannot be read or resolved; ``issue`` is an error of the closed set."""

    cli_code = "FEN-3001"

    def __init__(self, issue: Issue) -> None:
        if ISSUE_CODES.get(issue.code) != "error" or issue.severity != "error":
            raise ValueError(f"LibraryError needs an error code of the closed set, got {issue.code!r}")
        self.issue = issue
        super().__init__(issue.message)

    @property
    def hint(self) -> str:
        return self.issue.hint


def lib_error(code: str, message: str, *, where: str = "", hint: str = "") -> LibraryError:
    return LibraryError(lib_issue(code, message, where=where, hint=hint))


__all__ = ["ISSUE_CODES", "LibraryError", "lib_error", "lib_issue"]
