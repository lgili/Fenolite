# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded, in-memory local archives (c0264, ``docs/library-import.md``). Never extracts a member."""

from __future__ import annotations

import io
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from fenolite.core.errors import FormatError

MAX_ENTRIES = 2_000
MAX_MEMBER = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
MAX_RATIO = 200
RATIO_AFTER = 1024 * 1024
CHUNK = 64 * 1024
SUPPORTED = frozenset({".kicad_sym", ".kicad_mod", ".schlib", ".pcblib", ".step", ".stp"})


@dataclass(frozen=True, slots=True)
class Member:
    name: str
    data: bytes


@dataclass(frozen=True, slots=True)
class Skipped:
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class Archive:
    members: tuple[Member, ...]
    skipped: tuple[Skipped, ...]


def skipped_reason(name: str) -> str:
    suffix = PurePosixPath(name).suffix.casefold()
    if suffix == ".zip":
        return "nested archive"
    if suffix in {".lib", ".mod"}:
        return "legacy KiCad 5 library"
    return "unsupported format"


def _fail(file: str, member: str, rule: str) -> FormatError:
    return FormatError(f"archive {file}, member {member!r}: {rule}", file=file, locator=member)


def _name(info: zipfile.ZipInfo, file: str) -> str:
    # orig_filename retains a NUL that ZipInfo.filename truncates.
    raw = info.orig_filename.replace("\\", "/")
    if "\x00" in raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise _fail(file, raw, "absolute path, drive letter or NUL is forbidden")
    if ".." in raw.split("/"):
        raise _fail(file, raw, ".. path segment is forbidden")
    if stat.S_ISLNK(info.external_attr >> 16):
        raise _fail(file, raw, "symbolic link is forbidden")
    if info.flag_bits & 1:
        raise _fail(file, raw, "encrypted member is forbidden")
    normal = str(PurePosixPath(raw))
    if re.match(r"^[A-Za-z]:", normal):
        raise _fail(file, raw, "drive letter is forbidden")
    return normal


def read_zip(data: bytes, *, file: str) -> Archive:
    """Read supported members only, checking every member header before any inflation.

    Limits are Fenolite-authored, INFERRED choices. Actual inflated bytes are counted, independently
    of header sizes; each read is bounded so the refusal overshoots a limit by at most ``CHUNK``.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES:
                raise _fail(file, "<directory>", f"entry limit {MAX_ENTRIES} exceeded")
            names: set[str] = set()
            checked: list[tuple[str, zipfile.ZipInfo]] = []
            for info in infos:
                name = _name(info, file)
                folded = name.casefold()
                if folded in names:
                    raise _fail(file, name, "duplicate normalised casefold name")
                names.add(folded)
                checked.append((name, info))
            members: list[Member] = []
            skipped: list[Skipped] = []
            total = 0
            for name, info in sorted(checked):
                if info.is_dir():
                    continue
                if PurePosixPath(name).suffix.casefold() not in SUPPORTED:
                    skipped.append(Skipped(name, skipped_reason(name)))
                    continue
                body = bytearray()
                with archive.open(info) as stream:
                    while block := stream.read(CHUNK):
                        body.extend(block)
                        total += len(block)
                        if len(body) > MAX_MEMBER:
                            raise _fail(file, name, f"member size limit {MAX_MEMBER} bytes exceeded")
                        if total > MAX_TOTAL:
                            raise _fail(file, name, f"total size limit {MAX_TOTAL} bytes exceeded")
                        if len(body) > RATIO_AFTER and len(body) > MAX_RATIO * max(info.compress_size, 1):
                            raise _fail(file, name, f"compression ratio limit {MAX_RATIO}:1 exceeded")
                members.append(Member(name, bytes(body)))
            return Archive(tuple(members), tuple(skipped))
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError) as error:
        raise _fail(file, "<archive>", f"unreadable zip: {error}") from None


__all__ = ["Archive", "Member", "Skipped", "read_zip", "skipped_reason"]
