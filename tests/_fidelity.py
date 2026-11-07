# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Strict read → emit → build → verify-source helpers (c0278).

All generated files belong to the caller's pytest temporary directory. No acceptance, geometry
tolerance, level subset, tool upgrade or lossy-import flag is added by this helper. A failed comparison
is returned intact; an import/build refusal names its stage instead of looking like a fidelity pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fenolite.api import Reply, run
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import inspect

ALL_LEVELS = (1, 2, 3, 4, 5, 6, 7, "S", 8)
STAMP = "2026-11-01T00:00:00Z"


class RoundtripRefusal(AssertionError):
    """A refused import/build retains its reply for a value-free census, never a passing level."""

    def __init__(self, stage: str, reply: Reply) -> None:
        self.stage, self.reply = stage, reply
        details = {"error": reply.error, "issues": (reply.envelope or {}).get("issues", [])}
        super().__init__(
            f"fidelity {stage} refused: exit {reply.exit_code}; " + json.dumps(details, sort_keys=True)
        )


def snapshot(folder: Path) -> dict[str, str]:
    """Relative file names and byte digests, including any existing cache or local settings."""
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def _stage(name: str, reply: Reply) -> None:
    if reply.exit_code != 0:
        raise RoundtripRefusal(name, reply)


def roundtrip(project: Path, tmp_path: Path) -> Reply:
    """Import ``project`` to ``tmp_path/code``, build it, then return its complete fidelity reply.

    ``project`` is a KiCad project folder or project file. It is read from its native bytes, never its
    cached model. The explicit build tests the shipped script before ``verify-source`` independently
    rebuilds it. Both builds select the original's KiCad major. Nothing changes the original bytes.
    """
    project, tmp_path = project.resolve(), tmp_path.resolve()
    root = project if project.is_dir() else project.parent
    before = snapshot(root)
    board = resolve_board(project)
    info = inspect(parse(board.read_text(encoding="utf-8")), file=board.name)
    assert info.major in (9, 10), "the hermetic fidelity harness needs a readable KiCad 9/10 original"
    source = project if project.is_file() else board.with_suffix(".kicad_pro")
    if not source.is_file():
        source = board
    tmp_path.mkdir(parents=True, exist_ok=True)
    assert not (tmp_path / "code").exists(), "each round trip needs a fresh temporary code folder"
    try:
        imported = run(
            "import", str(source), "--to", "python", "--out", "code", "--confirm",
            cwd=tmp_path, timestamp=STAMP,
        )  # fmt: skip
        _stage("import", imported)
        script = tmp_path / "code" / "design.py"
        assert script.is_file(), "import did not emit design.py"
        built = run(
            "build", str(script), "--out", "built", "--confirm", "--kicad-version", str(info.major),
            cwd=tmp_path, timestamp=STAMP,
        )  # fmt: skip
        _stage("build", built)
        return run(
            "verify-source", str(script), "--against", str(project),
            cwd=tmp_path, timestamp=STAMP,
        )  # fmt: skip
    finally:
        assert snapshot(root) == before, "a fidelity round trip changed its original project"


def difference_counts(reply: Reply) -> dict[str, int]:
    """Counts keyed only by ``<level>:<kind>``; never upstream text, values, refs or coordinates."""
    counts: dict[str, int] = {}
    for row in reply.result.get("differences", []):
        key = f"{row['level']}:{row['kind']}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


__all__ = ["ALL_LEVELS", "STAMP", "RoundtripRefusal", "difference_counts", "roundtrip", "snapshot"]
