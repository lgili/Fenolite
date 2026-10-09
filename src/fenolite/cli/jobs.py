# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The record of an unfinished route: the copper of each router process that finished, kept so that the
same call made again does not route those nets again (capability cli-contract, "Resumable route jobs").

A record lives under ``jobs/<key>/`` of the state folder, one file per finished run. The key is a digest
of what the copper depends on: the Fenolite version, the router and its version, the board, its project
file and the route arguments. With the state folder off no record is kept.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fenolite.cli.output import canonical_json
from fenolite.core.errors import FormatError
from fenolite.core.io import atomic_write
from fenolite.model.board import Arc, Track, Via
from fenolite.model.canonical import decode, to_data
from fenolite.routing.protocol import FinishedRun

JOB_KEEP = 8
"""The state folder keeps at most this many route records."""
JOB_DAYS = 7
"""A route record older than this is dropped."""
_SUFFIX = ".json"


def route_job_key(
    *,
    fenolite_version: str,
    router: str,
    router_version: str,
    board_sha256: str,
    project_sha256: str | None,
    arguments: Mapping[str, Any],
    rules_sha256: str | None = None,
) -> str:
    """The first 16 hex digits of the SHA-256 of the canonical JSON of the Fenolite version, the router's
    name and version, the SHA-256 of the board, of its project file and of its rules file (``None``
    without one), and the route arguments without the run flags and without ``--out``. The rules file
    joins the key only when there is one: the router is given its rules (change c0107), so other rules
    are another job."""
    body: dict[str, Any] = {
        "fenolite": fenolite_version,
        "router": router,
        "router_version": router_version,
        "board": board_sha256,
        "project": project_sha256,
        "arguments": {key: value for key, value in arguments.items() if key != "out"},
    }
    if rules_sha256 is not None:
        body["rules"] = rules_sha256
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()[:16]


def _encode(run: FinishedRun) -> bytes:
    data = {
        "nets": list(run.nets),
        "tracks": to_data(run.tracks),
        "arcs": to_data(run.arcs),
        "vias": to_data(run.vias),
        "tier": run.tier,
        "milliseconds": max(0, round(run.seconds * 1000)),
    }
    return (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")


def _decode(data: bytes, file: str) -> FinishedRun:
    found = json.loads(data.decode("utf-8"))
    return FinishedRun(
        nets=tuple(str(name) for name in found["nets"]),
        tracks=decode(tuple[Track, ...], found["tracks"], "/tracks", file),
        arcs=decode(tuple[Arc, ...], found["arcs"], "/arcs", file),
        vias=decode(tuple[Via, ...], found["vias"], "/vias", file),
        tier=int(found["tier"]),
        seconds=int(found["milliseconds"]) / 1000,
    )


def prune(root: Path, *, keep: str = "", now: float | None = None) -> None:
    """Drop the records older than ``JOB_DAYS`` and the oldest beyond ``JOB_KEEP``; never ``keep``."""
    moment = time.time() if now is None else now
    stored: list[tuple[float, str, Path]] = []
    try:
        folders = list((root / "jobs").iterdir())
    except OSError:
        return
    for folder in folders:
        with contextlib.suppress(OSError):
            if folder.is_dir():
                stored.append((folder.stat().st_mtime, folder.name, folder))
    stored.sort()
    for index, (stamp, name, folder) in enumerate(stored):
        old = moment - stamp > JOB_DAYS * 86400
        beyond = len(stored) - index > JOB_KEEP
        if name != keep and (old or beyond):
            shutil.rmtree(folder, ignore_errors=True)


class JobRecord:
    """The finished runs of one route job. Every method is safe with the state folder off (``root`` is
    ``None``): nothing is read and nothing is kept."""

    def __init__(self, root: Path | None, key: str) -> None:
        self.key = key
        self.folder = None if root is None else root / "jobs" / key
        self._root = root
        self._count = 0

    def runs(self) -> tuple[FinishedRun, ...]:
        """The recorded runs in the order they finished. A record that cannot be read is removed and gives
        no run."""
        if self.folder is None or self._root is None or not self.folder.is_dir():
            return ()
        prune(self._root, keep=self.key)
        try:
            files = sorted(path for path in self.folder.iterdir() if path.suffix == _SUFFIX)
            found = tuple(_decode(path.read_bytes(), path.name) for path in files)
        except (OSError, ValueError, KeyError, TypeError, FormatError):
            self.remove()
            return ()
        self._count = len(found)
        return found

    def add(self, run: FinishedRun) -> None:
        """Keep one finished run, in a file of its own written atomically. A state folder that cannot be
        written keeps nothing and fails nothing."""
        if self.folder is None or self._root is None:
            return
        try:
            atomic_write(self.folder / f"{self._count:04d}{_SUFFIX}", _encode(run), backup=False)
        except OSError:
            return
        if self._count == 0:
            prune(self._root, keep=self.key)
        self._count += 1

    def remove(self) -> None:
        if self.folder is not None:
            shutil.rmtree(self.folder, ignore_errors=True)
        self._count = 0


__all__ = ["JOB_DAYS", "JOB_KEEP", "JobRecord", "route_job_key"]
