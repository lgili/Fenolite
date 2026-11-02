# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Structured edit conflicts and the source context of a viewer take (c0250, decision 14).

Only the server builds this context from the reply it loaded and the document it serves. A browser
selects a finding and a side, never a script, an output folder, a root or command words.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

Json = dict[str, Any]
HASH = re.compile(r"[0-9a-f]{64}")


def _object(value: Any) -> Json:
    return cast(Json, value) if isinstance(value, dict) else {}


def records(reply: Json) -> dict[str, Json]:
    """Conflict records of a build or sync, keyed by the exact property key."""
    result = _object(reply.get("result"))
    edits = _object(_object(result.get("preserved")).get("edits"))
    rows = edits.get("conflicts", result.get("conflicts", []))
    if not isinstance(rows, list):
        return {}
    found: dict[str, Json] = {}
    for value in cast(list[Any], rows):
        row = _object(value)
        key = row.get("key")
        if (
            isinstance(key, str)
            and "#" in key
            and isinstance(row.get("cad"), dict)
            and all(name in row for name in ("base", "code", "reason"))
        ):
            found[key] = {name: row[name] for name in ("key", "reason", "base", "code", "cad")}
    return found


def sides(record: Json) -> tuple[str, ...]:
    return ("board", "schematic") if record.get("reason") == "sides-disagree" else ("code", "cad")


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    except OSError:
        return None


def bind(reply: Json, *, board: Path, cwd: Path, board_sha256: str) -> Json | None:
    """Capture a build/sync source and this board, including available base/build records.

    An unbound reply keeps its copied commands; its context explains why taking it is unavailable.
    No source code is executed here.
    """
    if not records(reply):
        return None
    source, result = _object(reply.get("input")), _object(reply.get("result"))
    digest, name, out_name = source.get("sha256"), source.get("path"), result.get("out")
    if (
        source.get("kind") != "fenolite-dsl"
        or not isinstance(name, str)
        or not isinstance(out_name, str)
        or not isinstance(digest, str)
        or HASH.fullmatch(digest) is None
    ):
        return {"why": "the reply has no hashed design source and output: run the build again"}
    script = (cwd / name).resolve()
    choices = [(cwd / out_name).resolve(), (script.parent / out_name).resolve()]
    out = next((path for path in choices if path == board.resolve().parent), choices[0])
    root = script.parent
    if script.suffix.lower() != ".py" or not out.is_relative_to(root) or board.resolve().parent != out:
        return {"why": "the reply's source/output do not identify this board in its authoring project"}
    if _digest(script) != digest:
        return {"why": "the design source changed since this reply: run the build again"}
    if _digest(board) != board_sha256:
        return {"why": "the selected board changed while its scene was read: reload it"}
    inputs: list[Json] = [
        {"path": str(script), "sha256": digest},
        {"path": str(board.resolve()), "sha256": board_sha256},
    ]
    for path in (script.with_suffix(".lock"), root / "edits.toml"):
        if not path.resolve().is_relative_to(root):
            return {"why": "a source-side input resolves outside the authoring root"}
        inputs.append({"path": str(path), "sha256": _digest(path)})
    major = result.get("target")
    for path, schema in (
        (out / "fenolite-base.json", "fenolite.base.v0"),
        (out / ".fenolite/build.json", "fenolite.build-record.v0"),
    ):
        if not path.resolve().is_relative_to(root):
            return {"why": "a base/build record resolves outside the authoring root"}
        stamp = _digest(path)
        inputs.append({"path": str(path), "sha256": stamp})
        if stamp is None:
            continue
        try:
            record = _object(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            return {"why": "the selected output's base/build record is unreadable"}
        if record.get("schema") != schema:
            return {"why": "the selected output's base/build record has a different schema"}
        if path.name == "build.json":
            if record.get("design") != board.stem:
                return {"why": "the build record belongs to another board"}
            if major is None:
                major = record.get("target")
        elif record.get("target") != "kicad":
            return {"why": "the base record is not a KiCad build"}
    if type(major) is not int or major not in (9, 10):
        return {"why": "the reply and build record do not identify the KiCad target"}
    return {
        "script": str(script),
        "sha256": digest,
        "out": str(out),
        "root": str(root),
        "board": str(board.resolve()),
        "target": major,
        "inputs": inputs,
    }


def current(binding: Json | None, board: Path) -> str | None:
    """Why this captured context cannot run, or ``None`` when its inputs and scope still match."""
    if not binding:
        return "there is no bound source context: load a current build or sync reply"
    if binding.get("why"):
        return str(binding["why"])
    try:
        root, out, script = (Path(str(binding[key])) for key in ("root", "out", "script"))
        if (
            root.resolve() != root
            or script.resolve().parent != root
            or not out.resolve().is_relative_to(root)
            or board.resolve() != Path(str(binding["board"]))
            or board.resolve().parent != out
        ):
            return "the source/output paths changed or left their bound authoring root"
        inputs = binding["inputs"]
        if not isinstance(inputs, list):
            return "the source context has no input bindings"
        for value in cast(list[Any], inputs):
            item = _object(value)
            path = Path(str(item["path"]))
            if not path.resolve().is_relative_to(root) or _digest(path) != item.get("sha256"):
                return "a conflict input changed: run the build again and review the new conflict"
    except (KeyError, OSError, ValueError):
        return "the source context is incomplete or its paths are unavailable"
    return None


def receipt_for_root(envelope: Json, *, cwd: Path, root: Path) -> Json:
    """A restore envelope in the bound root, retaining the original receipt and its directory.

    A take may write beside its script while its child runs in the board folder. Restore accepts only
    relative paths in one root. The original id still identifies the original write; only its path
    notation changes, and the original receipt remains available verbatim.
    """
    if root.resolve() != root:
        raise ValueError("the bound authoring root changed")

    def relative(value: str) -> str:
        return (cwd / value).resolve().relative_to(root).as_posix()

    original = _object(envelope["receipt"])
    written = cast(list[Json], original["written"])
    backups = cast(list[str], original["backup"])
    receipt = original | {
        "written": [row | {"path": relative(str(row["path"]))} for row in written],
        "backup": [relative(path) for path in backups],
    }
    return envelope | {
        "receipt": receipt,
        "original_receipt": original,
        "receipt_cwd": str(cwd),
        "receipt_root": str(root),
    }


__all__ = ["bind", "current", "receipt_for_root", "records", "sides"]
