# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Atomic file writes with backups, and SHA-256 helpers.

No file is ever modified in place: data goes to a temporary file in the target directory, which
is then renamed over the target. When the target existed and ``backup`` is true, its previous
content is kept next to it as ``<name>.bak``. :func:`atomic_write_all` rolls a failed group back; if the
rollback itself fails, it preserves recovery files and reports that separately (capability
core-primitives, "Atomic writes of several files").
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.errors import FenoliteError

_CHUNK = 1 << 20


@dataclass(frozen=True, slots=True)
class WriteReceipt:
    """What :func:`atomic_write` wrote."""

    path: Path
    sha256: str
    backup_path: Path | None


def sha256_bytes(data: bytes) -> str:
    """Hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_of(path: str | os.PathLike[str]) -> str:
    """Hex SHA-256 of the file at ``path``, read in chunks."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_mode() -> int:
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def atomic_write(path: str | os.PathLike[str], data: bytes, *, backup: bool = True) -> WriteReceipt:
    """Write ``data`` to ``path`` atomically and return a receipt.

    Parent directories are created. If ``path`` exists and ``backup`` is true, its previous content
    is copied to ``<path>.bak`` before the rename. On any failure the target is left untouched and
    the temporary file is removed.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp_name)
    backup_path: Path | None = None
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if target.exists():
            shutil.copymode(target, tmp)
            if backup:
                backup_path = target.with_name(target.name + ".bak")
                shutil.copy2(target, backup_path)
        else:
            os.chmod(tmp, _default_mode())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    return WriteReceipt(path=target, sha256=sha256_bytes(data), backup_path=backup_path)


class WriteError(FenoliteError):
    """A write of :func:`atomic_write_all` failed and everything was put back. ``path`` is the file at
    which the step failed, ``reason`` the system's message, which names no path."""

    cli_code = "FEN-1002"

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path.name}: {reason}")


class RecoveryError(FenoliteError):
    """A failed write could not be fully put back. ``failed`` names unfinished undo steps and
    ``preserved`` the remaining recovery files. Neither retry nor cleanup is safe before inspection."""

    cli_code = "FEN-1004"

    def __init__(self, path: Path, failed: tuple[Path, ...], preserved: tuple[Path, ...]) -> None:
        self.path, self.failed, self.preserved = path, failed, preserved
        names = ", ".join(p.name for p in failed)
        super().__init__(f"rollback incomplete for {names}; some files may have changed")


def _reason(exc: OSError) -> str:
    return (exc.strerror or type(exc).__name__).lower()


def _beside(target: Path, suffix: str) -> Path:
    """A new empty file beside ``target``, for a temporary or a kept copy."""
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=suffix, dir=target.parent)
    os.close(fd)
    return Path(name)


def _keep(path: Path) -> Path:
    """``path`` kept beside itself under another name: a hard link, or a copy where the file system
    refuses a link or ``path`` is a symbolic link (whose content is kept, never the link)."""
    kept = _beside(path, ".keep")
    try:
        try:
            if path.is_symlink():
                raise OSError("a symbolic link is kept by a copy")
            kept.unlink()
            os.link(path, kept)
        except OSError:
            shutil.copy2(path, kept)
    except BaseException:
        _remove(kept)
        raise
    return kept


def _remove(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


def _missing_parents(folder: Path) -> list[Path]:
    """The folders that must be created for ``folder`` to exist, the outermost first."""
    missing: list[Path] = []
    while not folder.exists():
        missing.append(folder)
        if folder.parent == folder:
            break
        folder = folder.parent
    return missing[::-1]


@dataclass(frozen=True, slots=True)
class _Undo:
    path: Path
    run: Callable[[], None]
    cleanup: bool = False


def _put_back(undo: list[_Undo]) -> tuple[Path, ...]:
    """Attempt restoration in reverse order. If any step fails, preserve recovery material instead of
    deleting it during cleanup; an interruption of one step does not prevent the remaining restores."""
    failed: list[Path] = []
    while undo:
        step = undo.pop()
        if step.cleanup and failed:
            continue
        try:
            step.run()
        except BaseException:  # record an I/O failure or interruption; still attempt the other restores
            failed.append(step.path)
    return tuple(dict.fromkeys(failed))


def atomic_write_all(
    writes: Sequence[tuple[str | os.PathLike[str], bytes]], *, backup: bool = True
) -> tuple[WriteReceipt, ...]:
    """Write every ``(path, data)`` of ``writes``, or roll back. If rollback itself fails, preserve the
    remaining recovery files and raise :class:`RecoveryError`. Receipts come in the given order.

    *Prepare*: the missing parent folders are created, every new content is written and flushed to a
    temporary file beside its target, and every existing target and ``<path>.bak`` is kept by a hard link
    beside it (a copy where a link is refused). *Commit*: the targets are replaced in order, then each kept
    target becomes ``<path>.bak`` (it is removed when ``backup`` is false). On any exception everything is
    put back: replaced targets and ``.bak`` files from what was kept, and the new targets, the temporary
    and kept files and the folders created are removed. An ``OSError`` then becomes :class:`WriteError`;
    any other exception (an interrupt included) is raised again. A failure or interruption during
    rollback instead becomes :class:`RecoveryError`, which never claims that nothing changed.
    An interrupt that arrives after the last step of the commit does not undo the write.

    Two entries with one path raise ``ValueError`` before anything is touched."""
    entries = [(Path(path), data) for path, data in writes]
    seen: set[str] = set()
    for target, _ in entries:
        key = os.path.normcase(os.path.abspath(target))
        if key in seen:
            raise ValueError(f"two writes name {target}")
        seen.add(key)

    undo: list[_Undo] = []
    recovery: list[Path] = []
    leftovers: list[Path] = []
    temps: list[Path] = []
    kept: list[Path | None] = []
    baks: list[Path | None] = []
    receipts: list[WriteReceipt] = []
    current = entries[0][0] if entries else Path()
    try:
        for target, data in entries:  # prepare
            current = target
            for folder in _missing_parents(target.parent):
                folder.mkdir()
                undo.append(_Undo(folder, lambda folder=folder: folder.rmdir(), cleanup=True))
            fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            tmp = Path(tmp_name)
            undo.append(_Undo(tmp, lambda tmp=tmp: _remove(tmp), cleanup=True))
            temps.append(tmp)
            recovery.append(tmp)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            old: Path | None = None
            if target.exists():
                shutil.copymode(target, tmp)
                old = _keep(target)
                undo.append(_Undo(old, lambda old=old: _remove(old), cleanup=True))
                recovery.append(old)
            else:
                os.chmod(tmp, _default_mode())
            kept.append(old)
            bak = target.with_name(target.name + ".bak")
            old_bak: Path | None = None
            if bak.is_file():
                old_bak = _keep(bak)
                undo.append(_Undo(old_bak, lambda old_bak=old_bak: _remove(old_bak), cleanup=True))
                recovery.append(old_bak)
                leftovers.append(old_bak)
            baks.append(old_bak)
        for (target, _), tmp, old in zip(entries, temps, kept, strict=True):  # commit: the targets
            current = target
            link = os.readlink(target) if target.is_symlink() else None
            os.replace(tmp, target)
            undo.append(_Undo(target, lambda target=target, old=old, link=link: _restore(target, old, link)))
        for (target, data), old, old_bak in zip(entries, kept, baks, strict=True):  # commit: the backups
            current = target
            backup_path: Path | None = None
            if old is not None and backup:
                backup_path = target.with_name(target.name + ".bak")
                os.replace(old, backup_path)
                recovery.append(backup_path)
                undo.append(
                    _Undo(
                        backup_path, lambda b=backup_path, old=old, before=old_bak: _unbackup(b, old, before)
                    )
                )
            elif old is not None:
                leftovers.append(old)
            receipts.append(WriteReceipt(path=target, sha256=sha256_bytes(data), backup_path=backup_path))
    except BaseException as exc:
        failed = _put_back(undo)
        if failed:
            preserved = tuple(dict.fromkeys(path for path in recovery if os.path.lexists(path)))
            raise RecoveryError(current, failed, preserved) from exc
        if isinstance(exc, OSError):
            raise WriteError(current, _reason(exc)) from exc
        raise
    while leftovers:  # written: what was kept is no longer needed, and no interrupt undoes the write
        try:
            _remove(leftovers[-1])
            leftovers.pop()
        except BaseException:
            continue
    return tuple(receipts)


def _restore(target: Path, old: Path | None, link: str | None) -> None:
    """Undo one replacement: the kept file back over ``target``, or ``target`` removed when it is new."""
    if link is not None:
        target.unlink()
        os.symlink(link, target)
    elif old is None:
        target.unlink()
    else:
        os.replace(old, target)


def _unbackup(backup_path: Path, old: Path, before: Path | None) -> None:
    """Undo one backup: the kept target back under its kept name, and the ``.bak`` that was there back."""
    os.replace(backup_path, old)
    if before is not None:
        os.replace(before, backup_path)


__all__ = [
    "RecoveryError",
    "WriteError",
    "WriteReceipt",
    "atomic_write",
    "atomic_write_all",
    "sha256_bytes",
    "sha256_of",
]
