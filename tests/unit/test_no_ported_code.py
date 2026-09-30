# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nothing is ported from non-public projects (ADR-0003): no ported-from trailers or markers."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = "Ported" + "-From:"  # assembled so this file does not match itself
SCANNED_DIRS = ("src", "tests", "tools", "examples")


def commits_with_marker() -> list[str]:
    proc = subprocess.run(
        ["git", "log", "--all", "--format=%H%x00%B%x01"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:  # not a git checkout, or no commits yet
        return []
    hits = []
    for record in proc.stdout.split("\x01"):
        sha, _, body = record.strip().partition("\x00")
        if sha and re.search(rf"^{re.escape(MARKER)}", body, re.MULTILINE | re.IGNORECASE):
            hits.append(sha[:12])
    return hits


def files_with_marker() -> list[str]:
    hits = []
    for top in SCANNED_DIRS:
        for path in sorted((ROOT / top).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".md", ".toml", ".txt", ".yaml", ".yml"}:
                if MARKER.lower() in path.read_text(encoding="utf-8", errors="replace").lower():
                    hits.append(path.relative_to(ROOT).as_posix())
    return hits


def test_no_commit_declares_ported_code() -> None:
    hits = commits_with_marker()
    assert not hits, f"commits with a {MARKER} trailer: {', '.join(hits)}"


def test_no_source_file_declares_ported_code() -> None:
    hits = files_with_marker()
    assert not hits, f"files with a {MARKER} marker:\n" + "\n".join(hits)
