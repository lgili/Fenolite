# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``atomic_write_all`` writes every file or changes nothing (capability core-primitives, "Atomic writes
of several files"; change c0120)."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from fenolite.core import io as fio
from fenolite.core.errors import FenoliteError

STEPS: tuple[tuple[Any, str], ...] = (
    (os, "replace"),
    (os, "link"),
    (os, "chmod"),
    (os, "fsync"),
    (os, "mkdir"),
    (shutil, "copymode"),
    (shutil, "copy2"),
    (tempfile, "mkstemp"),
)
"""The calls of the function that touch the file system and can fail."""


def snapshot(folder: Path) -> dict[str, str]:
    """Every file and folder under ``folder`` by POSIX name → SHA-256 (``dir`` for a folder)."""
    return {
        path.relative_to(folder).as_posix(): (
            "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for path in sorted(folder.rglob("*"))
    }


@contextmanager
def failing(monkeypatch: pytest.MonkeyPatch, at: int, error: BaseException) -> Iterator[list[int]]:
    """Count the calls of ``STEPS`` and raise ``error`` in the call number ``at`` (from 0); the list holds
    the number of calls made. Calls made after the failure, by the roll back, pass."""
    calls = [0]

    def wrap(real: Callable[..., Any]) -> Callable[..., Any]:
        def step(*args: Any, **kwargs: Any) -> Any:
            index = calls[0]
            calls[0] += 1
            if index == at:
                raise error
            return real(*args, **kwargs)

        return step

    with monkeypatch.context() as patch:
        for module, name in STEPS:
            patch.setattr(module, name, wrap(getattr(module, name)))
        yield calls


def _three(folder: Path) -> list[tuple[Path, bytes]]:
    """Three targets of which the first exists with a ``.bak``."""
    (folder / "a.txt").write_bytes(b"a-old")
    (folder / "a.txt.bak").write_bytes(b"a-older")
    return [(folder / "a.txt", b"a-new"), (folder / "b.txt", b"b-new"), (folder / "c.txt", b"c-new")]


def _fail_replace_of(monkeypatch: pytest.MonkeyPatch, name: str, error: BaseException) -> None:
    real = os.replace

    def replace(src: Any, dst: Any, **kwargs: Any) -> None:
        if Path(dst).name == name and Path(src).suffix == ".tmp":
            raise error
        real(src, dst, **kwargs)

    monkeypatch.setattr(os, "replace", replace)


def test_rollback_after_a_failure_in_the_middle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    writes = _three(tmp_path)
    before = snapshot(tmp_path)
    _fail_replace_of(monkeypatch, "c.txt", PermissionError(13, "Permission denied", str(tmp_path / "c.txt")))
    with pytest.raises(fio.WriteError) as caught:
        fio.atomic_write_all(writes)
    assert caught.value.path == tmp_path / "c.txt"
    assert caught.value.reason == "permission denied" and str(tmp_path) not in caught.value.reason
    assert isinstance(caught.value, FenoliteError) and caught.value.cli_code == "FEN-1002"
    assert (tmp_path / "a.txt").read_bytes() == b"a-old"
    assert (tmp_path / "a.txt.bak").read_bytes() == b"a-older"
    assert not (tmp_path / "b.txt").exists() and not (tmp_path / "c.txt").exists()
    assert snapshot(tmp_path) == before, "no temporary file is left"


def test_rollback_without_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_link(*_args: object, **_kwargs: object) -> None:
        raise OSError(1, "Operation not permitted")

    monkeypatch.setattr(os, "link", no_link)
    writes = _three(tmp_path)
    before = snapshot(tmp_path)
    _fail_replace_of(monkeypatch, "c.txt", PermissionError(13, "Permission denied"))
    with pytest.raises(fio.WriteError) as caught:
        fio.atomic_write_all(writes)
    assert caught.value.path == tmp_path / "c.txt"
    assert snapshot(tmp_path) == before


def test_written_without_links(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_link(*_args: object, **_kwargs: object) -> None:
        raise OSError(1, "Operation not permitted")

    monkeypatch.setattr(os, "link", no_link)
    fio.atomic_write_all(_three(tmp_path))
    assert snapshot(tmp_path) == {
        "a.txt": hashlib.sha256(b"a-new").hexdigest(),
        "a.txt.bak": hashlib.sha256(b"a-old").hexdigest(),
        "b.txt": hashlib.sha256(b"b-new").hexdigest(),
        "c.txt": hashlib.sha256(b"c-new").hexdigest(),
    }


def test_folders_made_for_the_write_are_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fail_replace_of(monkeypatch, "d.txt", OSError(28, "No space left on device"))
    with pytest.raises(fio.WriteError) as caught:
        fio.atomic_write_all([(tmp_path / "a" / "b" / "c.txt", b"c"), (tmp_path / "d.txt", b"d")])
    assert caught.value.reason == "no space left on device"
    assert not (tmp_path / "a").exists() and list(tmp_path.iterdir()) == []


def test_receipts_equal_single_writes(tmp_path: Path) -> None:
    files = {"one.txt": b"1-new", "sub/two.txt": b"2-new"}
    together, single = tmp_path / "together", tmp_path / "single"
    for folder in (together, single):
        folder.mkdir()
        (folder / "one.txt").write_bytes(b"1-old")
    many = fio.atomic_write_all([(together / name, data) for name, data in files.items()])
    ones = tuple(fio.atomic_write(single / name, data) for name, data in files.items())

    def relative(receipts: tuple[fio.WriteReceipt, ...], folder: Path) -> list[tuple[str, str, str | None]]:
        return [
            (
                r.path.relative_to(folder).as_posix(),
                r.sha256,
                None if r.backup_path is None else r.backup_path.relative_to(folder).as_posix(),
            )
            for r in receipts
        ]

    assert relative(many, together) == relative(ones, single)
    assert snapshot(together) == snapshot(single) and "one.txt.bak" in snapshot(together)


def test_no_backup_removes_the_kept_files(tmp_path: Path) -> None:
    writes = _three(tmp_path)
    receipts = fio.atomic_write_all(writes, backup=False)
    assert [r.backup_path for r in receipts] == [None, None, None]
    assert sorted(snapshot(tmp_path)) == ["a.txt", "a.txt.bak", "b.txt", "c.txt"]
    assert (tmp_path / "a.txt.bak").read_bytes() == b"a-older", "an earlier .bak is left as it was"


def test_interrupt_rolls_back_and_passes_on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.txt").write_bytes(b"a-old")
    (tmp_path / "b.txt").write_bytes(b"b-old")
    before = snapshot(tmp_path)
    _fail_replace_of(monkeypatch, "b.txt", KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        fio.atomic_write_all([(tmp_path / "a.txt", b"a-new"), (tmp_path / "b.txt", b"b-new")])
    assert snapshot(tmp_path) == before


def test_other_exception_is_raised_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "a.txt").write_bytes(b"a-old")
    before = snapshot(tmp_path)
    _fail_replace_of(monkeypatch, "b.txt", RuntimeError("not the system"))
    with pytest.raises(RuntimeError, match="not the system"):
        fio.atomic_write_all([(tmp_path / "a.txt", b"a-new"), (tmp_path / "b.txt", b"b-new")])
    assert snapshot(tmp_path) == before


def test_two_entries_with_one_path(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"a-old")
    with pytest.raises(ValueError, match="two writes"):
        fio.atomic_write_all([(tmp_path / "a.txt", b"1"), (tmp_path / "sub" / ".." / "a.txt", b"2")])
    assert snapshot(tmp_path) == {"a.txt": hashlib.sha256(b"a-old").hexdigest()}


def test_blocked_parent_names_the_target(tmp_path: Path) -> None:
    (tmp_path / "blocker").write_bytes(b"a file")
    with pytest.raises(fio.WriteError) as caught:
        fio.atomic_write_all([(tmp_path / "ok.txt", b"ok"), (tmp_path / "blocker" / "x.txt", b"x")])
    assert caught.value.path == tmp_path / "blocker" / "x.txt"
    assert sorted(snapshot(tmp_path)) == ["blocker"]


@pytest.mark.skipif(sys.platform == "win32", reason="a symbolic link needs a privilege on Windows")
def test_symbolic_link_is_replaced_not_followed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "real.txt").write_bytes(b"real")
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "a.txt").symlink_to(outside / "real.txt")
    fio.atomic_write_all([(inside / "a.txt", b"new")])
    assert (outside / "real.txt").read_bytes() == b"real" and sorted(snapshot(outside)) == ["real.txt"]
    assert not (inside / "a.txt").is_symlink() and (inside / "a.txt").read_bytes() == b"new"
    assert (inside / "a.txt.bak").read_bytes() == b"real"

    (inside / "a.txt.bak").unlink()
    (inside / "a.txt").unlink()
    (inside / "a.txt").symlink_to(outside / "real.txt")
    _fail_replace_of(monkeypatch, "b.txt", OSError(5, "Input/output error"))
    with pytest.raises(fio.WriteError):
        fio.atomic_write_all([(inside / "a.txt", b"new"), (inside / "b.txt", b"b")])
    assert (inside / "a.txt").is_symlink() and (inside / "a.txt").read_bytes() == b"real"
    assert sorted(snapshot(inside)) == ["a.txt"] and sorted(snapshot(outside)) == ["real.txt"]


def _prepared(folder: Path) -> list[tuple[Path, bytes]]:
    """A folder with an existing target that has a ``.bak``, an existing target without one, a new target
    and a new target under two new folders."""
    folder.mkdir()
    (folder / "a.txt").write_bytes(b"a-old")
    (folder / "a.txt.bak").write_bytes(b"a-older")
    (folder / "b.txt").write_bytes(b"b-old")
    return [
        (folder / "a.txt", b"a-new"),
        (folder / "b.txt", b"b-new"),
        (folder / "c.txt", b"c-new"),
        (folder / "x" / "y" / "d.txt", b"d-new"),
    ]


@pytest.mark.parametrize("backup", [True, False])
@pytest.mark.parametrize("links", [True, False])
@pytest.mark.parametrize("error", [OSError(5, "Input/output error"), KeyboardInterrupt()], ids=["os", "int"])
def test_any_single_failure_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backup: bool, links: bool, error: BaseException
) -> None:
    """Every call that touches the file system fails once, in turn: the folder's names and hashes then
    equal those before the call. An interrupt after the last step of the commit is the one exception:
    the write is then done."""
    if not links:

        def no_link(*_args: object, **_kwargs: object) -> None:
            raise OSError(1, "Operation not permitted")

        monkeypatch.setattr(os, "link", no_link)
    with failing(monkeypatch, -1, error) as calls:
        done = _prepared(tmp_path / "count")
        fio.atomic_write_all(done, backup=backup)
    total = calls[0]
    written = snapshot(tmp_path / "count")
    assert total > 12
    for at in range(total):
        folder = tmp_path / f"run-{at}"
        writes = _prepared(folder)
        before = snapshot(folder)
        with failing(monkeypatch, at, error):
            try:
                fio.atomic_write_all(writes, backup=backup)
            except fio.WriteError as failure:
                assert isinstance(error, OSError)
                assert failure.path in [path for path, _ in writes]
                assert snapshot(folder) == before, at
            except KeyboardInterrupt:
                assert snapshot(folder) == before, at
            else:  # a failed link is answered by a copy: the write succeeds
                assert snapshot(folder) == written, at
