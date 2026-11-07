# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library release`` (capability fenolite-library, "Library releases"; change c0279)."""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli import main as cli_main
from fenolite.library.items import folder_files, tree_digest
from fenolite.library.release import archive_members

DEMO = Path(__file__).resolve().parents[2] / "data" / "library_repo" / "demo"


def _cli(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def _files(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


def test_release_is_reproducible(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Release is reproducible"."""
    for out in ("one", "two"):
        code, envelope = _cli(
            monkeypatch,
            tmp_path,
            "library",
            "release",
            str(DEMO),
            "--version",
            "1.0.0",
            "--out",
            out,
            "--confirm",
        )
        assert code == 0, envelope
    one, two = _files(tmp_path / "one"), _files(tmp_path / "two")
    assert one == two
    assert sorted(one) == [
        "SHA256SUMS",
        "blocks-apache.tar.gz",
        "board-demo-src-blink-1.0.0.tar.gz",
        "devices-cc0.tar.gz",
        "footprints-cc-by-sa.tar.gz",
        "footprints-cc0.tar.gz",
        "index.json",
        "symbols-cc0.tar.gz",
    ]
    index = json.loads(one["index.json"])
    assert index["schema"] == "fenolite.library-index.v0" and index["version"] == "1.0.0"
    for row in index["items"]:
        assert row["tree"] == tree_digest(folder_files(DEMO / row["path"])), row["id"]
        members = archive_members(one[row["archive"]], name=row["archive"])
        mine = {
            k.removeprefix(row["path"] + "/"): v
            for k, v in members.items()
            if k.startswith(row["path"] + "/")
        }
        assert tree_digest(mine) == row["tree"]
    for archive in index["archives"]:
        assert hashlib.sha256(one[archive["name"]]).hexdigest() == archive["sha256"]
    sums = one["SHA256SUMS"].decode().splitlines()
    assert f"{hashlib.sha256(one['index.json']).hexdigest()}  index.json" in sums
    board = next(r for r in index["items"] if r["kind"] == "board")
    assert (
        board["proof"] == "pass-with-accepted" and board["reciprocal"] is True and board["executes"] is True
    )


def test_release_dry_run_and_audit_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, demo: Path
) -> None:
    code, envelope = _cli(
        monkeypatch,
        tmp_path,
        "library",
        "release",
        str(demo),
        "--version",
        "1.0.0",
        "--out",
        "dist",
        "--dry-run",
    )
    assert code == 0 and not (tmp_path / "dist").exists()
    assert len(envelope["result"]["plan"]) == 8
    (demo / "devices/cc0/Demo/EXB/notes.txt").write_text("x", encoding="utf-8")
    code, envelope = _cli(
        monkeypatch,
        tmp_path,
        "library",
        "release",
        str(demo),
        "--version",
        "1.0.0",
        "--out",
        "dist",
        "--confirm",
    )
    assert code == 5 and not (tmp_path / "dist").exists()


def test_archive_members_refuse_links(tmp_path: Path) -> None:
    import tarfile

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w:gz") as tar:
        info = tarfile.TarInfo("top/link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)
    with pytest.raises(ValueError, match="not a regular file"):
        archive_members(raw.getvalue(), name="x.tar.gz")
