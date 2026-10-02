# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed CLI errors: the ``FEN-NNNN`` registry, the stderr error object and :class:`CliError`."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from fenolite.cli.exitcodes import ExitCode

ERROR_CODE = re.compile(r"^FEN-[1-7][0-9]{3}$")


@dataclass(frozen=True, slots=True)
class ErrorSpec:
    """Registry entry for one error code."""

    code: str
    exit_code: ExitCode
    message: str
    hint: str
    retryable: bool = False


_SPECS = (
    ErrorSpec(
        "FEN-1001", ExitCode.INTERNAL, "internal error", "this is a bug; report it with the command line"
    ),
    ErrorSpec("FEN-2001", ExitCode.USAGE, "invalid command line", "run 'fenolite --help'"),
    ErrorSpec(
        "FEN-2002", ExitCode.USAGE, "unknown field in --fields", "list the result keys with --json first"
    ),
    ErrorSpec(
        "FEN-2003", ExitCode.USAGE, "--dry-run and --confirm are mutually exclusive", "use one of them"
    ),
    ErrorSpec("FEN-2004", ExitCode.USAGE, "invalid --timestamp", "use ISO 8601, e.g. 2026-01-01T00:00:00Z"),
    ErrorSpec(
        "FEN-3001", ExitCode.INPUT, "input file missing or unreadable", "check the path and permissions"
    ),
    ErrorSpec(
        "FEN-3002", ExitCode.INPUT, "input uses a newer format version than supported", "upgrade fenolite"
    ),
    ErrorSpec(
        "FEN-3003",
        ExitCode.INPUT,
        "input format version older than the oldest supported",
        "upgrade the file with the kicad-cli command for its kind",
    ),
    ErrorSpec("FEN-3004", ExitCode.INPUT, "malformed input file", "the message and where locate the problem"),
    ErrorSpec(
        "FEN-3005",
        ExitCode.INPUT,
        "geometry in the input cannot be represented",
        "the message names the geometry code and the points",
    ),
    ErrorSpec(
        "FEN-4001",
        ExitCode.CONFIRM_REQUIRED,
        "confirmation required; nothing was written",
        "review result.plan, then re-run with --confirm (or --dry-run to only preview)",
    ),
    ErrorSpec(
        "FEN-5001",
        ExitCode.FINDINGS,
        "verification produced findings of severity error",
        "read 'issues' in the envelope",
    ),
    ErrorSpec(
        "FEN-6001",
        ExitCode.TOOL,
        "external tool not found",
        "run 'fenolite capabilities' to see what is missing",
        retryable=True,
    ),
    ErrorSpec(
        "FEN-6002", ExitCode.TOOL, "external tool version not supported", "install a supported version"
    ),
    ErrorSpec(
        "FEN-7001",
        ExitCode.LOSSY,
        "operation would lose information",
        "re-run with --allow-lossy to accept the loss",
    ),
    ErrorSpec(
        "FEN-7002",
        ExitCode.LOSSY,
        "target format version older than the input; downgrade is not supported",
        "choose a target at least as new as the input",
    ),
    ErrorSpec(
        "FEN-7003",
        ExitCode.LOSSY,
        "input from KiCad 8.0 is read-only; writing needs a KiCad 9.0 or newer source",
        "convert it with 'kicad-cli pcb upgrade' (KiCad 10.0) or re-save it in KiCad 9.0",
    ),
)

REGISTRY: dict[str, ErrorSpec] = {spec.code: spec for spec in _SPECS}


@dataclass(frozen=True, slots=True)
class ErrorInfo:
    """The single error object written to stderr when the exit code is not 0."""

    code: str = field(metadata={"pattern": ERROR_CODE.pattern})
    message: str
    hint: str
    retryable: bool
    where: str


class CliError(Exception):
    """An error with a registered ``FEN-NNNN`` code; the dispatcher maps it to an exit code."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        hint: str | None = None,
        where: str = "",
        retryable: bool | None = None,
    ) -> None:
        if code not in REGISTRY:
            raise ValueError(f"unregistered error code {code!r}")
        spec = REGISTRY[code]
        self.code = code
        self.message = message or spec.message
        self.hint = spec.hint if hint is None else hint
        self.where = where
        self.retryable = spec.retryable if retryable is None else retryable
        super().__init__(f"{code}: {self.message}")

    @property
    def exit_code(self) -> ExitCode:
        return REGISTRY[self.code].exit_code

    def info(self) -> ErrorInfo:
        return ErrorInfo(
            code=self.code, message=self.message, hint=self.hint, retryable=self.retryable, where=self.where
        )


def from_exception(exc: Exception, where: str) -> CliError:
    """The CLI error for an exception raised inside a command (library errors keep their codes)."""
    from fenolite.core.errors import FenoliteError, FormatError

    code = getattr(type(exc), "cli_code", None)
    if isinstance(exc, FenoliteError) and isinstance(code, str) and code in REGISTRY:
        chosen = code
    elif isinstance(exc, FormatError):
        chosen = "FEN-3004"
    else:
        return CliError("FEN-1001", f"{type(exc).__name__}: {exc}", where=where)
    if isinstance(exc, FormatError):
        message = exc.message
        offset = "" if exc.offset is None else f"@{exc.offset}"
        location = ":".join(part for part in (exc.file, exc.locator, offset) if part)
    else:
        message, location = str(exc), ""
    hint = getattr(exc, "hint", "")
    return CliError(
        chosen, message, hint=hint if isinstance(hint, str) and hint else None, where=location or where
    )


__all__ = ["ERROR_CODE", "REGISTRY", "CliError", "ErrorInfo", "ErrorSpec", "from_exception"]
