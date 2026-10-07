# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Staged plans: the id of a plan and the store that keeps its bytes between a review and
``--confirm --plan ID`` (capability cli-contract, "Staged plans").

The id is a digest of what a review relied on: the command, its arguments without the run flags, the
working folder, the digest of every declared input and, per planned write, its path, kind, size and digest
and the digest of the file it would replace. No clock and no seed takes part. The store lives under
``plans/`` of the state folder (``fenolite.core.state``), one folder per id, and is bounded.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fenolite.cli.output import canonical_json, to_jsonable
from fenolite.core.io import sha256_bytes, sha256_of

RUN_FLAGS = (
    "--dry-run",
    "--confirm",
    "--plan",
    "--json",
    "--text",
    "--fields",
    "--limit",
    "--cursor",
    "--format",
    "--progress",
    "--seed",
    "--timestamp",
    "--no-backup",
    "--timeout",
    "--kicad-cli",
)
"""The flags that change how a run happens, not what it plans: they take no part in a plan id."""
PLAN_KEEP = 16
"""The store keeps at most this many plans."""
PLAN_BYTES = 512 * 1024 * 1024
"""The store keeps at most this many bytes of planned files."""
PLAN_DAYS = 7
"""A plan older than this is dropped."""
PLAN_ID = re.compile(r"^[0-9a-f]{16}$")
META = "plan.json"
FILES = "files"
_RUN_KEYS = frozenset(flag[2:].replace("-", "_") for flag in RUN_FLAGS) | {"command"}


class StageError(Exception):
    """A plan could not be staged; the message is the reason, without a path."""


class DamagedPlan(Exception):
    """A staged plan cannot be read, or one of its files does not have its planned digest."""


def arguments(namespace: Mapping[str, object]) -> dict[str, Any]:
    """The arguments of a parsed command line without the run flags, as JSON values with sorted keys."""
    kept = {key: value for key, value in namespace.items() if key not in _RUN_KEYS}
    return cast(dict[str, Any], json.loads(json.dumps(kept, sort_keys=True, default=str)))


def digest_of(path: Path) -> str | None:
    """The SHA-256 of the file at ``path``, or ``None`` when no file is there or it cannot be read."""
    try:
        return sha256_of(path) if path.is_file() else None
    except OSError:
        return None


def plan_id(
    command: str,
    args: Mapping[str, Any],
    cwd: str,
    depends: Sequence[tuple[str, str | None]],
    writes: Sequence[Mapping[str, Any]],
) -> str:
    """The first 16 hex digits of the SHA-256 of the canonical JSON of the command name, its arguments
    without the run flags, the working folder, ``(path, sha256)`` of every declared input and, for each
    planned write, its ``path``, ``kind``, ``bytes``, ``sha256`` and ``replaces`` (the SHA-256 of the file
    it would replace, ``None`` without one)."""
    body = {
        "command": command,
        "arguments": dict(args),
        "cwd": cwd,
        "depends": [[path, digest] for path, digest in depends],
        "writes": [
            {key: row[key] for key in ("path", "kind", "bytes", "sha256", "replaces")} for row in writes
        ],
    }
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class StagedPlan:
    """A plan read back from the store. ``writes`` holds the rows of the id plus ``file``, the name of the
    staged bytes; ``reply`` what the review saw (``result``, ``issues``, ``evidence``, ``input``,
    ``write_on_error``) as JSON values."""

    id: str
    command: str
    arguments: dict[str, Any]
    cwd: str
    depends: tuple[tuple[str, str | None], ...]
    writes: tuple[dict[str, Any], ...]
    reply: dict[str, Any]
    folder: Path

    def data(self, row: Mapping[str, Any]) -> bytes:
        """The staged bytes of one write; :class:`DamagedPlan` when they are missing or changed."""
        try:
            data = (self.folder / FILES / str(row["file"])).read_bytes()
        except OSError as exc:
            raise DamagedPlan(f"the staged bytes of {row['path']} cannot be read") from exc
        if len(data) != row["bytes"] or sha256_bytes(data) != row["sha256"]:
            raise DamagedPlan(f"the staged bytes of {row['path']} are not the planned ones")
        return data


def _plans(root: Path) -> Path:
    return root / "plans"


def _size(folder: Path) -> int:
    total = 0
    for path in folder.rglob("*"):
        with contextlib.suppress(OSError):
            if path.is_file():
                total += path.stat().st_size
    return total


def _stored(root: Path) -> list[tuple[float, str, Path]]:
    """The staged plans as ``(time, id, folder)``, the oldest first."""
    found: list[tuple[float, str, Path]] = []
    try:
        entries = list(_plans(root).iterdir())
    except OSError:
        return []
    for folder in entries:
        if PLAN_ID.fullmatch(folder.name) and folder.is_dir():
            with contextlib.suppress(OSError):
                found.append((folder.stat().st_mtime, folder.name, folder))
    return sorted(found)


def prune(root: Path, *, keep: str = "", now: float | None = None) -> list[str]:
    """Drop the plans older than ``PLAN_DAYS``, then the oldest until at most ``PLAN_KEEP`` plans and
    ``PLAN_BYTES`` bytes remain; the plan ``keep`` is never dropped. Returns the ids dropped."""
    moment = time.time() if now is None else now
    dropped: list[str] = []
    stored = _stored(root)
    for stamp, name, folder in list(stored):
        if name != keep and moment - stamp > PLAN_DAYS * 86400:
            shutil.rmtree(folder, ignore_errors=True)
            dropped.append(name)
            stored.remove((stamp, name, folder))
    sizes = {name: _size(folder) for _, name, folder in stored}
    for stamp, name, folder in list(stored):
        if len(stored) <= PLAN_KEEP and sum(sizes.values()) <= PLAN_BYTES:
            break
        if name == keep:
            continue
        shutil.rmtree(folder, ignore_errors=True)
        dropped.append(name)
        stored.remove((stamp, name, folder))
        del sizes[name]
    return dropped


def stage(
    root: Path | None,
    plan: str,
    *,
    command: str,
    args: Mapping[str, Any],
    cwd: str,
    depends: Sequence[tuple[str, str | None]],
    writes: Sequence[Mapping[str, Any]],
    payloads: Sequence[bytes],
    reply: Mapping[str, Any],
) -> None:
    """Keep the plan ``plan`` and its bytes under ``plans/<id>/`` of ``root``: written in a temporary folder
    that is renamed into place, then the store is pruned. :class:`StageError` says why it was not kept."""
    if root is None:
        raise StageError("the state folder is off (FENOLITE_STATE_DIR=off)")
    if sum(len(data) for data in payloads) > PLAN_BYTES:
        raise StageError(f"the plan is larger than the store ({PLAN_BYTES} bytes)")
    rows = [dict(row) | {"file": f"{index:04d}"} for index, row in enumerate(writes)]
    meta = {
        "id": plan,
        "command": command,
        "arguments": dict(args),
        "cwd": cwd,
        "depends": [[path, digest] for path, digest in depends],
        "writes": rows,
        "reply": to_jsonable(dict(reply)),
    }
    try:
        folder = _plans(root)
        folder.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=".stage-", dir=folder))
        try:
            (work / FILES).mkdir()
            for row, data in zip(rows, payloads, strict=True):
                (work / FILES / row["file"]).write_bytes(data)
            (work / META).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            final = folder / plan
            if final.exists():
                shutil.rmtree(final)
            os.replace(work, final)
        except BaseException:
            shutil.rmtree(work, ignore_errors=True)
            raise
    except OSError as exc:
        raise StageError(f"the state folder is not writable ({(exc.strerror or 'error').lower()})") from exc
    prune(root, keep=plan)


def load(root: Path | None, plan: str) -> StagedPlan | None:
    """The staged plan ``plan``, ``None`` when the store holds none of that id, and :class:`DamagedPlan`
    when its record cannot be read."""
    if root is None or not PLAN_ID.fullmatch(plan):
        return None
    folder = _plans(root) / plan
    if not folder.is_dir():
        return None
    try:
        meta = json.loads((folder / META).read_text(encoding="utf-8"))
        return StagedPlan(
            id=str(meta["id"]),
            command=str(meta["command"]),
            arguments=dict(meta["arguments"]),
            cwd=str(meta["cwd"]),
            depends=tuple((str(path), digest) for path, digest in meta["depends"]),
            writes=tuple(dict(row) for row in meta["writes"]),
            reply=dict(meta["reply"]),
            folder=folder,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise DamagedPlan("the staged plan cannot be read") from exc


def remove(root: Path | None, plan: str) -> None:
    """Remove the staged plan ``plan``; nothing when the store holds none of that id."""
    if root is not None and PLAN_ID.fullmatch(plan):
        shutil.rmtree(_plans(root) / plan, ignore_errors=True)


__all__ = [
    "PLAN_BYTES",
    "PLAN_DAYS",
    "PLAN_ID",
    "PLAN_KEEP",
    "RUN_FLAGS",
    "DamagedPlan",
    "StageError",
    "StagedPlan",
    "arguments",
    "digest_of",
    "load",
    "plan_id",
    "prune",
    "remove",
    "stage",
]
