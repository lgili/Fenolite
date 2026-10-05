# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The output contract: envelope dataclasses, output-mode selection, ``--fields`` and rendering."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, TextIO

from fenolite.cli.errors import ErrorInfo
from fenolite.core.errors import ISSUE_CODE, Issue, Severity
from fenolite.core.evidence import Evidence, Level

OutputMode = Literal["json", "text"]
EvidenceLevel = Level
SCHEMA_ID = re.compile(r"^fenolite\.[a-z_][a-z0-9_-]*\.v0$")


@dataclass(frozen=True, slots=True)
class InputRef:
    """The design file a command read."""

    path: str
    sha256: str | None
    kind: str
    format_version: str | None


@dataclass(frozen=True, slots=True)
class WrittenFile:
    path: str
    sha256: str = field(metadata={"pattern": r"^[0-9a-f]{64}$"})


@dataclass(frozen=True, slots=True)
class Receipt:
    """Files written by a confirmed mutating command, and the backups kept."""

    written: tuple[WrittenFile, ...]
    backup: tuple[str, ...]
    id: str = field(default="", metadata={"pattern": r"^([0-9a-f]{16})?$", "optional": True})
    """The identity of the write: :func:`receipt_id` of ``written`` and ``backup``."""
    undo: str | None = field(default=None, metadata={"optional": True})
    """The command that puts the backups back, reading this envelope from stdin; ``None`` without one."""


@dataclass(frozen=True, slots=True)
class Envelope:
    """The single JSON document every ``fenolite`` command prints on stdout."""

    ok: bool
    command: str
    schema: str = field(metadata={"pattern": SCHEMA_ID.pattern})
    input: InputRef | None
    result: dict[str, Any]
    issues: tuple[Issue, ...]
    evidence: Evidence
    receipt: Receipt | None
    elapsed_ms: int = field(metadata={"minimum": 0})


UNDO_COMMAND = "fenolite restore - --confirm"
"""``receipt.undo`` of a write that kept a backup: pipe the envelope to it."""


def canonical_json(value: Any) -> str:
    """Compact JSON with sorted keys: the form that receipt ids and page cursors are digests of."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def receipt_id(written: Sequence[WrittenFile], backup: Sequence[str]) -> str:
    """The first 16 hex digits of the SHA-256 of the canonical JSON of ``{"written": …, "backup": …}``.
    No clock, seed or folder takes part, so equal writes have equal ids."""
    body = {"written": [{"path": w.path, "sha256": w.sha256} for w in written], "backup": list(backup)}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()[:16]


def make_receipt(written: Sequence[WrittenFile], backup: Sequence[str]) -> Receipt:
    """The receipt of a confirmed write, with its ``id`` and, when a backup was kept, its ``undo``."""
    return Receipt(
        written=tuple(written),
        backup=tuple(backup),
        id=receipt_id(written, backup),
        undo=UNDO_COMMAND if backup else None,
    )


class CursorError(ValueError):
    """A ``--cursor`` that is malformed, past the end, or issued for another list."""


@dataclass(frozen=True, slots=True)
class Page:
    """One page of a list: its items and what ``result.page`` says about it."""

    items: tuple[Any, ...]
    limit: int
    offset: int
    total: int
    next: str | None


CURSOR = re.compile(r"^(0|[1-9][0-9]{0,11})\.([0-9a-f]{8})$")


def list_digest(items: Sequence[Any]) -> str:
    """The first 8 hex digits of the SHA-256 of the canonical JSON of the whole list."""
    return hashlib.sha256(canonical_json(to_jsonable(list(items))).encode("utf-8")).hexdigest()[:8]


def page(items: Sequence[Any], limit: int, cursor: str | None = None) -> Page:
    """The ``limit`` items of ``items`` from the cursor's offset (0 without one). A cursor is
    ``<offset>.<digest of the whole list>``, so paging keeps no state: :class:`CursorError` when it is
    malformed, past the end, or when the list is not the one it was issued for."""
    if limit < 1:
        raise ValueError("the limit is at least 1")
    digest = list_digest(items)
    offset = 0
    if cursor is not None:
        match = CURSOR.fullmatch(cursor)
        if match is None:
            raise CursorError(f"malformed cursor {cursor!r}; pass the 'next' of the page before")
        offset = int(match.group(1))
        if match.group(2) != digest:
            raise CursorError("the result changed since the cursor was issued; start again without --cursor")
        if offset >= len(items) and offset > 0:
            raise CursorError(f"the cursor's offset {offset} is past the end of {len(items)} items")
    end = offset + limit
    following = f"{end}.{digest}" if end < len(items) else None
    return Page(tuple(items[offset:end]), limit, offset, len(items), following)


class FieldNotFoundError(KeyError):
    """A ``--fields`` path does not exist in the result."""


def resolve_mode(*, force_json: bool, force_text: bool, stream: TextIO) -> OutputMode:
    """JSON unless ``stream`` is a terminal; ``--json``/``--text`` override the detection."""
    if force_json:
        return "json"
    if force_text:
        return "text"
    try:
        return "text" if stream.isatty() else "json"
    except (AttributeError, ValueError):
        return "json"


def parse_fields(spec: str) -> list[str]:
    return [part.strip() for part in spec.split(",") if part.strip()]


def project_fields(result: Mapping[str, Any], paths: Sequence[str]) -> dict[str, Any]:
    """Keep only the dotted ``paths`` of ``result``; raise :class:`FieldNotFoundError` for a missing one."""
    out: dict[str, Any] = {}
    for path in paths:
        node: Any = result
        parts = path.split(".")
        for part in parts:
            if not isinstance(node, Mapping) or part not in node:
                raise FieldNotFoundError(path)
            node = node[part]  # pyright: ignore[reportUnknownVariableType]
        target = out
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = node
    return out


def to_jsonable(obj: Any) -> Any:
    """Convert dataclasses (recursively), tuples and mappings into plain JSON values."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in obj.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]  # pyright: ignore[reportUnknownVariableType]
    return obj


def render_json(envelope: Envelope) -> str:
    return json.dumps(to_jsonable(envelope), ensure_ascii=False)


def _text_lines(value: Any, indent: int) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():  # pyright: ignore[reportUnknownVariableType]
            if isinstance(item, (Mapping, list)) and item:
                lines.append(f"{pad}{key}:")
                lines.extend(_text_lines(item, indent + 1))
            else:
                lines.append(f"{pad}{key}: {_scalar(item)}")
    elif isinstance(value, list):
        for item in value:  # pyright: ignore[reportUnknownVariableType]
            if isinstance(item, (Mapping, list)) and item:
                lines.append(f"{pad}-")
                lines.extend(_text_lines(item, indent + 1))
            else:
                lines.append(f"{pad}- {_scalar(item)}")
    else:
        lines.append(f"{pad}{_scalar(value)}")
    return lines


def _scalar(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (Mapping, list)):
        return "(empty)"
    return str(value)


def render_text(envelope: Envelope) -> str:
    """Human rendering of the same envelope (never a different data set)."""
    data = to_jsonable(envelope)
    status = "ok" if envelope.ok else "FAILED"
    lines = [f"fenolite {envelope.command}: {status}"]
    if data["input"]:
        lines.append(f"input: {data['input']['path']} ({data['input']['kind']})")
    if data["result"]:
        lines.append("result:")
        lines.extend(_text_lines(data["result"], 1))
    for issue in envelope.issues:
        where = f" [{issue.where}]" if issue.where else ""
        hint = f" (hint: {issue.hint})" if issue.hint else ""
        lines.append(f"{issue.severity}: {issue.code}: {issue.message}{where}{hint}")
    oracle = f"({envelope.evidence.oracle})" if envelope.evidence.oracle else ""
    lines.append(f"evidence: {envelope.evidence.level}{oracle}")
    if envelope.receipt:
        for written in envelope.receipt.written:
            lines.append(f"wrote: {written.path} sha256={written.sha256[:12]}")
        for backup in envelope.receipt.backup:
            lines.append(f"backup: {backup}")
        if envelope.receipt.undo:
            lines.append(f"undo: {envelope.receipt.undo} (receipt {envelope.receipt.id})")
    return "\n".join(lines)


def write_error(info: ErrorInfo, mode: OutputMode, stream: TextIO) -> None:
    """Write the single stderr error object (JSON) or line (text)."""
    if mode == "json":
        stream.write(json.dumps(to_jsonable(info), ensure_ascii=False) + "\n")
    else:
        hint = f" ({info.hint})" if info.hint else ""
        stream.write(f"error {info.code}: {info.message}{hint}\n")


__all__ = [
    "ISSUE_CODE",
    "Envelope",
    "Evidence",
    "EvidenceLevel",
    "CursorError",
    "FieldNotFoundError",
    "InputRef",
    "Issue",
    "OutputMode",
    "Page",
    "Receipt",
    "Severity",
    "UNDO_COMMAND",
    "WrittenFile",
    "canonical_json",
    "list_digest",
    "make_receipt",
    "page",
    "parse_fields",
    "project_fields",
    "receipt_id",
    "render_json",
    "render_text",
    "resolve_mode",
    "to_jsonable",
    "write_error",
]
