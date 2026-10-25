# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review marks of the viewer (capability review-tools, change c0189): ``fenolite.review.v0``.

A person drops a mark with a note on a board or a sheet; the file lists them for a colleague or an agent
(``fenolite view PATH --marks FILE --json``). A mark names its document by file name, its place in
nanometres in the document's frame (the frame the scene draws: Y down), and optionally the part or net it
points at. ``read_review`` checks a file; ``with_mark`` gives the bytes of a file with one mark added or
replaced (by ``id``) or removed (a mark without note and position), which the live server writes in one
atomic replace. Standard library only.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from fenolite.core.errors import FormatError

SCHEMA = "fenolite.review.v0"
ID_LIMIT = 64
NOTE_LIMIT = 4000
MARK_LIMIT = 5000


@dataclass(frozen=True)
class ReviewMark:
    """One mark: where it is, what it says and what it points at."""

    id: str = field(metadata={"description": "unique in the file; the page makes m<n>"})
    doc: str = field(metadata={"description": "the document's file name, as the project tree names it"})
    x_nm: int = field(metadata={"description": "X in nanometres, in the document's frame"})
    y_nm: int = field(metadata={"description": "Y in nanometres, Y down"})
    note: str = ""
    select: str = field(default="", metadata={"description": "a part reference or net name it points at"})
    created: str = field(default="", metadata={"description": "ISO 8601 time the page gave"})


@dataclass(frozen=True)
class ReviewFile:
    """A project's review marks (``fenolite view --marks``)."""

    schema: Literal["fenolite.review.v0"] = "fenolite.review.v0"
    marks: tuple[ReviewMark, ...] = ()


def _text(value: Any, key: str, limit: int, where: str) -> str:
    if not isinstance(value, str) or len(value) > limit:
        raise FormatError(f"{where}: `{key}` must be a text of at most {limit} characters", locator=where)
    return value


def _mark(raw: Any, where: str) -> ReviewMark:
    if not isinstance(raw, dict):
        raise FormatError(f"{where}: a mark is an object", locator=where)
    item = cast("dict[str, Any]", raw)
    unknown = set(item) - {"id", "doc", "x_nm", "y_nm", "note", "select", "created"}
    if unknown:
        raise FormatError(f"{where}: unknown key(s) {', '.join(sorted(unknown))}", locator=where)
    for key in ("x_nm", "y_nm"):
        if type(item.get(key)) is not int:
            raise FormatError(f"{where}: `{key}` must be an integer (nanometres)", locator=where)
    mark = ReviewMark(
        id=_text(item.get("id"), "id", ID_LIMIT, where),
        doc=_text(item.get("doc"), "doc", 255, where),
        x_nm=item["x_nm"],
        y_nm=item["y_nm"],
        note=_text(item.get("note", ""), "note", NOTE_LIMIT, where),
        select=_text(item.get("select", ""), "select", 255, where),
        created=_text(item.get("created", ""), "created", 64, where),
    )
    if not mark.id or not mark.doc:
        raise FormatError(f"{where}: `id` and `doc` must not be empty", locator=where)
    return mark


def read_review(data: Any, *, file: str = "") -> ReviewFile:
    """The review file ``data`` (parsed JSON); ``FormatError`` when it is not ``fenolite.review.v0``."""
    if not isinstance(data, dict) or cast("dict[str, Any]", data).get("schema") != SCHEMA:
        raise FormatError(f"{file or 'the file'} is not a {SCHEMA} file", file=file)
    raw = cast("dict[str, Any]", data).get("marks", [])
    if not isinstance(raw, list) or len(cast("list[Any]", raw)) > MARK_LIMIT:
        raise FormatError(f"{file}: `marks` must be a list of at most {MARK_LIMIT} marks", file=file)
    marks = tuple(_mark(item, f"/marks/{k}") for k, item in enumerate(cast("list[Any]", raw)))
    if len({m.id for m in marks}) != len(marks):
        raise FormatError(f"{file}: two marks have the same id", file=file)
    return ReviewFile(marks=marks)


def load(path: Path) -> ReviewFile:
    """The review file at ``path``; an empty one when there is none; ``FormatError`` when it is malformed."""
    if not path.is_file():
        return ReviewFile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise FormatError(f"{path.name} is not JSON: {exc}", file=path.name) from exc
    return read_review(data, file=path.name)


def dumps(review: ReviewFile) -> bytes:
    """The canonical bytes of ``review``: sorted keys, two-space indent, a final newline."""
    body = {"schema": review.schema, "marks": [asdict(m) for m in review.marks]}
    return (json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def with_mark(review: ReviewFile, raw: Any) -> ReviewFile:
    """``review`` with the mark ``raw`` (an object the page sent) added, or replacing the mark of its id; a
    mark whose ``note`` is ``null`` removes the mark of its id."""
    if isinstance(raw, dict) and cast("dict[str, Any]", raw).get("note", "") is None:
        gone = str(cast("dict[str, Any]", raw).get("id", ""))
        return ReviewFile(marks=tuple(m for m in review.marks if m.id != gone))
    mark = _mark(raw, "/mark")
    kept = tuple(m for m in review.marks if m.id != mark.id)
    if len(kept) >= MARK_LIMIT:
        raise FormatError(f"the review file holds {MARK_LIMIT} marks already", locator="/mark")
    return ReviewFile(marks=(*kept, mark))


def write_atomic(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` through a temporary file in the same folder and one replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".review-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def to_json(review: ReviewFile) -> list[dict[str, Any]]:
    """``result.marks`` of ``fenolite view --marks``: each mark with its place also in millimetres."""
    return [asdict(m) | {"x_mm": m.x_nm / 1e6, "y_mm": m.y_nm / 1e6} for m in review.marks]


__all__ = [
    "SCHEMA",
    "ReviewFile",
    "ReviewMark",
    "dumps",
    "load",
    "read_review",
    "to_json",
    "with_mark",
    "write_atomic",
]
