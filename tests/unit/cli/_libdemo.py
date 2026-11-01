# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Releases and projects for the ``fenolite get`` tests (change c0279), built from the authored demo library
``tests/data/library_repo/demo``. Nothing here opens a network connection."""

from __future__ import annotations

import json
import shutil
import socket
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fenolite.library.audit import audit
from fenolite.library.cache import library_dir
from fenolite.library.licences import for_root
from fenolite.library.release import build_release

ROOT = Path(__file__).resolve().parents[3]
DEMO = ROOT / "tests" / "data" / "library_repo" / "demo"
SCRIPT = '''"""A project that gets library items (test project)."""

from fenolite.dsl import Design

design = Design("demo_project")
'''


def demo_copy(target: Path, edit: Callable[[Path], None] | None = None) -> Path:
    """A copy of the demo library at ``target``, edited by ``edit``."""
    shutil.copytree(DEMO, target)
    if edit is not None:
        edit(target)
    return target


def write_release(library: Path, out: Path, version: str = "1.0.0") -> dict[str, Any]:
    """The release assets of ``library`` written into ``out``; returns the index."""
    report = audit(library)
    errors = [i for i in report.issues if i.severity == "error"]
    assert not errors, errors
    release = build_release(library, report.items, version, for_root(library), commit="0" * 40)
    out.mkdir(parents=True, exist_ok=True)
    for name, data in release.assets.items():
        (out / name).write_bytes(data)
    return dict(release.index)


def edit_json(path: Path, **changes: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def project(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")
    return folder


def files_of(folder: Path) -> dict[str, bytes]:
    if not folder.exists():
        return {}
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


def cache_files() -> dict[str, bytes]:
    return files_of(library_dir())


def no_network(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every way of this process to the network raises; the list holds what was tried."""
    tried: list[str] = []

    def refuse(*args: object, **kwargs: object) -> None:
        tried.append(repr(args[:2]))
        raise AssertionError(f"a network connection was opened: {args[:2]!r}")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    return tried


__all__ = [
    "DEMO",
    "ROOT",
    "cache_files",
    "demo_copy",
    "edit_json",
    "files_of",
    "no_network",
    "project",
    "write_release",
]
