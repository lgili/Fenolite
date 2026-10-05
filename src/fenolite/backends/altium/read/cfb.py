# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded, read-only reader for MS-CFB versions 3 and 4."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fenolite.backends.altium import cfb as writer
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level

SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
DIFSECT = 0xFFFFFFFC
NOSTREAM = 0xFFFFFFFF
MAX_REGULAR = 0xFFFFFFFA
NOTE_CODES = (
    "cfb.note.minor-version",
    "cfb.note.header-fields",
    "cfb.note.partial-sector",
    "cfb.note.fat-marks",
    "cfb.note.high-size-bits",
    "cfb.note.long-chain",
    "cfb.note.entry-fields",
    "cfb.note.tree-order",
    "cfb.note.orphan-entries",
)
ERROR_RULES = (
    "cfb.signature",
    "cfb.truncated",
    "cfb.header",
    "cfb.difat",
    "cfb.chain",
    "cfb.shared-sector",
    "cfb.directory",
    "cfb.name",
    "cfb.duplicate-name",
    "cfb.size",
    "cfb.limit",
)
EVIDENCE_V3 = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-RD-CFB-CORPUS", "H-A-RD-CFB-DIFAT"))
EVIDENCE_V4 = Evidence(Level.INFERRED, hypotheses=("H-A-RD-CFB-CORPUS", "H-A-RD-CFB-DIFAT", "H-A-RD-CFB-V4"))


class CompoundError(FormatError):
    """A compound-file error with a stable rule code and source location."""

    def __init__(
        self, rule: str, message: str, *, file: str = "", locator: str = "header", offset: int | None = None
    ) -> None:
        if rule not in ERROR_RULES and rule not in NOTE_CODES:
            raise ValueError(f"unknown compound rule {rule}")
        self.rule = rule
        super().__init__(f"{rule}: {message}", file=file, locator=locator, offset=offset)


@dataclass(frozen=True, slots=True)
class Limits:
    max_file_bytes: int = 1 << 30
    max_entries: int = 1 << 18
    max_depth: int = 64


DEFAULT_LIMITS = Limits()


@dataclass(frozen=True, slots=True)
class Header:
    major: int
    minor: int
    sector_size: int
    mini_sector_size: int
    sector_count: int
    fat_sectors: int
    difat_sectors: int
    directory_entries: int
    transaction: int


@dataclass(frozen=True, slots=True)
class Node:
    path: str
    name: str
    kind: Literal["root", "storage", "stream"]
    size: int
    entry: int
    clsid: bytes
    state_bits: int
    created: int
    modified: int
    children: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _Entry:
    index: int
    name: str
    kind: int
    colour: int
    left: int
    right: int
    child: int
    clsid: bytes
    state: int
    created: int
    modified: int
    start: int
    size: int
    offset: int


@dataclass
class CompoundFile:
    """A parsed tree with chain locations retained; stream data is copied only on ``read``."""

    header: Header
    notes: tuple[Issue, ...]
    evidence: Evidence
    root: Node
    _nodes: tuple[Node, ...] = field(repr=False)
    _by_path: dict[str, Node] = field(repr=False)
    _children: dict[str, tuple[str, ...]] = field(repr=False)
    _chains: dict[str, tuple[tuple[int, int], ...]] = field(repr=False)
    _mini_chains: dict[str, tuple[tuple[int, int], ...]] = field(repr=False)
    _data: memoryview = field(repr=False)
    _sector_size: int = field(repr=False)
    _mini_stream_start: int = field(repr=False)
    _mini_stream_size: int = field(repr=False)
    _mini_stream_sectors: tuple[int, ...] = field(repr=False)
    _sector_owners: dict[int, str] = field(repr=False)
    _fat_values: tuple[int, ...] = field(repr=False)
    file_sha256: str

    def nodes(self) -> tuple[Node, ...]:
        return self._nodes

    def node(self, path: str) -> Node:
        return self._by_path[_lookup_key(path)]

    def __contains__(self, path: object) -> bool:
        return isinstance(path, str) and _lookup_key(path) in self._by_path

    def children(self, path: str = "") -> tuple[Node, ...]:
        node = self.node(path)
        if node.kind == "stream":
            raise NotADirectoryError(path)
        return tuple(self._by_path[_lookup_key(p)] for p in self._children[node.path])

    def streams(self) -> tuple[str, ...]:
        return tuple(node.path for node in self._nodes if node.kind == "stream")

    def storages(self) -> tuple[str, ...]:
        return tuple(node.path for node in self._nodes if node.kind == "storage")

    def read(self, path: str) -> bytes:
        node = self.node(path)
        if node.kind != "stream":
            raise IsADirectoryError(path)
        if node.size == 0:
            return b""
        if node.path in self._mini_chains:
            return self._copy_mini(node.path)
        return self._copy_regular(node.path)

    def _copy_regular(self, path: str) -> bytes:
        node = self.node(path)
        path = node.path
        remaining = node.size
        out = bytearray()
        for first, count in self._chains[path]:
            for sid in range(first, first + count):
                take = min(remaining, self._sector_size)
                start = _sector_offset(sid, self._sector_size)
                out.extend(self._data[start : start + take])
                remaining -= take
                if not remaining:
                    return bytes(out)
        return bytes(out)

    def _copy_mini(self, path: str) -> bytes:
        node = self.node(path)
        path = node.path
        remaining = node.size
        out = bytearray()
        for first, count in self._mini_chains[path]:
            for mini in range(first, first + count):
                mini_offset = mini * 64
                absolute = (
                    _sector_offset(
                        self._mini_stream_sectors[mini_offset // self._sector_size], self._sector_size
                    )
                    + mini_offset % self._sector_size
                )
                take = min(remaining, 64)
                while take:
                    sector_left = self._sector_size - (absolute % self._sector_size)
                    chunk = min(take, sector_left)
                    out.extend(self._data[absolute : absolute + chunk])
                    absolute += chunk
                    take -= chunk
                    remaining -= chunk
                    if not remaining:
                        return bytes(out)
        return bytes(out)

    def as_dict(self) -> dict[str, bytes]:
        return {path: self.read(path) for path in self.streams()}

    def tree(self) -> tuple[writer.Entry, ...]:
        def items(path: str) -> tuple[writer.Entry, ...]:
            out: list[writer.Entry] = []
            for node in self.children(path):
                if node.kind == "storage":
                    out.append(writer.Storage(node.name, items(node.path)))
                else:
                    out.append((node.name, self.read(node.path)))
            return tuple(out)

        return items("")


def _lookup_key(path: str) -> str:
    return "/".join(part.upper() for part in path.split("/") if part)


def is_compound(data: bytes) -> bool:
    return data.startswith(SIGNATURE)


def _error(
    rule: str, message: str, *, file: str, locator: str = "header", offset: int | None = None
) -> CompoundError:
    return CompoundError(rule, message, file=file, locator=locator, offset=offset)


def _runs(numbers: list[int]) -> tuple[tuple[int, int], ...]:
    if not numbers:
        return ()
    result: list[tuple[int, int]] = []
    first = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        result.append((first, previous - first + 1))
        first = previous = number
    result.append((first, previous - first + 1))
    return tuple(result)


def _sector_offset(number: int, size: int) -> int:
    return (number + 1) * size


def _read_sector(data: memoryview, number: int, size: int) -> memoryview:
    start = _sector_offset(number, size)
    return data[start : start + size]


def _chain(
    table: list[int],
    start: int,
    sector_count: int,
    owner: str,
    *,
    file: str,
    fat_sectors: list[int],
    sector_size: int,
    owners: dict[int, str],
) -> list[int]:
    if start == ENDOFCHAIN:
        return []
    result: list[int] = []
    visited: set[int] = set()
    current = start
    while current != ENDOFCHAIN:
        per_fat = sector_size // 4
        offset = (
            _sector_offset(fat_sectors[current // per_fat], sector_size) + (current % per_fat) * 4
            if current < len(table)
            else None
        )
        if current > MAX_REGULAR or current >= sector_count or current >= len(table):
            raise _error(
                "cfb.chain",
                f"sector {current:#x} is outside the file",
                file=file,
                locator=owner,
                offset=offset,
            )
        if current in visited:
            raise _error(
                "cfb.chain", f"sector {current} repeats in chain", file=file, locator=owner, offset=offset
            )
        if current in owners:
            raise _error(
                "cfb.shared-sector",
                f"sector {current} is also owned by {owners[current]}",
                file=file,
                locator=owner,
                offset=offset,
            )
        visited.add(current)
        owners[current] = owner
        result.append(current)
        value = table[current]
        if value in (FREESECT, FATSECT, DIFSECT):
            raise _error(
                "cfb.chain",
                f"sector {current} ends with invalid value {value:#x}",
                file=file,
                locator=owner,
                offset=offset,
            )
        current = value
    return result


def open_compound(
    data: bytes, *, file: str = "", limits: Limits = DEFAULT_LIMITS, strict: bool = False
) -> CompoundFile:
    """Parse one byte string, validating all structures before exposing a container."""
    if len(data) > limits.max_file_bytes:
        raise _error(
            "cfb.limit",
            f"max_file_bytes is {limits.max_file_bytes}, found {len(data)}",
            file=file,
            offset=None,
        )
    if len(data) < 8:
        raise _error("cfb.truncated", f"signature is truncated at {len(data)} bytes", file=file, offset=0)
    if data[:8] != SIGNATURE:
        raise _error("cfb.signature", "signature bytes do not match MS-CFB", file=file, offset=0)
    if len(data) < 512:
        raise _error(
            "cfb.truncated", f"header is {len(data)} bytes, expected 512", file=file, offset=len(data)
        )
    view = memoryview(data)
    fields = struct.unpack_from("<8s16sHHHHH6s9I109I", view, 0)
    _, clsid, minor, major, byte_order, shift, mini_shift, reserved = fields[:8]
    (
        dir_count,
        fat_count,
        first_dir,
        transaction,
        cutoff,
        first_minifat,
        minifat_count,
        first_difat,
        difat_count,
    ) = fields[8:17]
    if major not in (3, 4):
        raise _error("cfb.header", f"major version is {major}", file=file, offset=0x1A)
    sector_size = 512 if major == 3 else 4096
    if shift != (9 if major == 3 else 12) or byte_order != 0xFFFE or mini_shift != 6 or cutoff != 4096:
        raise _error(
            "cfb.header",
            f"invalid shifts, byte order or cutoff (shift={shift}, byte_order={byte_order:#x}, "
            f"mini_shift={mini_shift}, cutoff={cutoff})",
            file=file,
            offset=0x1C,
        )
    if len(data) < sector_size:
        raise _error(
            "cfb.truncated",
            f"header sector is {len(data)} bytes, expected {sector_size}",
            file=file,
            offset=len(data),
        )
    sector_count = max(0, (len(data) - sector_size) // sector_size)
    partial = (len(data) - sector_size) % sector_size
    note_records: dict[str, list[tuple[str, int | None]]] = {code: [] for code in NOTE_CODES}
    if minor != 0x003E:
        note_records[NOTE_CODES[0]].append(("header minor version", 0x18))
    if clsid != bytes(16):
        note_records[NOTE_CODES[1]].append(("header CLSID", 8))
    if reserved != bytes(6):
        note_records[NOTE_CODES[1]].append(("reserved header bytes", 0x22))
    if transaction:
        raise _error("cfb.header", f"transaction signature is {transaction}", file=file, offset=0x34)
    if major == 3 and dir_count:
        note_records[NOTE_CODES[1]].append(("version 3 directory-sector count", 0x28))
    if major == 4 and any(view[512:sector_size]):
        note_records[NOTE_CODES[1]].append(("version 4 header padding", 512))
    if partial:
        note_records[NOTE_CODES[2]].append(("partial final sector", len(data) - partial))
    if major == 4 and dir_count > sector_count:
        raise _error(
            "cfb.limit", f"directory sector count {dir_count} exceeds {sector_count}", file=file, offset=0x28
        )
    if fat_count > sector_count or difat_count > sector_count:
        raise _error(
            "cfb.limit",
            f"header FAT/DIFAT counts {fat_count}/{difat_count} exceed {sector_count} sectors",
            file=file,
            offset=0x2C,
        )
    fat_ids: list[int] = []
    for index, sector_id in enumerate(fields[17:]):
        if sector_id == FREESECT:
            continue
        if sector_id > MAX_REGULAR or sector_id >= sector_count:
            raise _error(
                "cfb.difat",
                f"header FAT sector {sector_id:#x} is outside file",
                file=file,
                locator=f"difat[{index}]",
                offset=0x4C + index * 4,
            )
        if sector_id in fat_ids:
            raise _error(
                "cfb.difat",
                f"header FAT sector {sector_id} repeats",
                file=file,
                locator=f"difat[{index}]",
                offset=0x4C + index * 4,
            )
        fat_ids.append(sector_id)
    difat_ids: list[int] = []
    current = first_difat
    per_difat = sector_size // 4 - 1
    for step in range(difat_count):
        if current == ENDOFCHAIN or current >= sector_count or current > MAX_REGULAR:
            raise _error(
                "cfb.difat",
                f"DIFAT chain ends before sector count {difat_count}",
                file=file,
                locator=f"difat[{step}]",
                offset=0x44,
            )
        if current in difat_ids or current in fat_ids:
            raise _error(
                "cfb.difat",
                f"DIFAT sector {current} repeats",
                file=file,
                locator=f"difat[{step}]",
                offset=_sector_offset(current, sector_size),
            )
        difat_ids.append(current)
        raw = _read_sector(view, current, sector_size)
        values = struct.unpack(f"<{per_difat + 1}I", raw)
        for j, sector_id in enumerate(values[:-1]):
            if sector_id == FREESECT:
                continue
            if sector_id >= sector_count or sector_id > MAX_REGULAR or sector_id in fat_ids:
                raise _error(
                    "cfb.difat",
                    f"DIFAT FAT sector {sector_id:#x} is outside or repeats",
                    file=file,
                    locator=f"difat[{step}]",
                    offset=_sector_offset(current, sector_size) + 4 * j,
                )
            fat_ids.append(sector_id)
        current = values[-1]
    if len(fat_ids) != fat_count or current != ENDOFCHAIN:
        raise _error(
            "cfb.difat",
            f"DIFAT lists {len(fat_ids)} FAT sectors; header says {fat_count}",
            file=file,
            offset=0x2C,
        )
    per_fat = sector_size // 4
    fat_values: list[int] = []
    for sid in fat_ids:
        fat_values.extend(struct.unpack(f"<{per_fat}I", _read_sector(view, sid, sector_size)))
    note_records[NOTE_CODES[3]] += [
        (
            f"FAT sector {sid} lacks FATSECT mark",
            _sector_offset(fat_ids[sid // per_fat], sector_size) + (sid % per_fat) * 4,
        )
        for sid in fat_ids
        if fat_values[sid] != FATSECT
    ]
    note_records[NOTE_CODES[3]] += [
        (
            f"DIFAT sector {sid} lacks DIFSECT mark",
            _sector_offset(fat_ids[sid // per_fat], sector_size) + (sid % per_fat) * 4,
        )
        for sid in difat_ids
        if fat_values[sid] != DIFSECT
    ]
    if any(value != FREESECT for value in fat_values[sector_count:]):
        note_records[NOTE_CODES[3]].append(("FAT entries past end of file", None))
    # Directory and mini-FAT chains are validated with one owner table. FAT/DIFAT sectors own themselves.
    owners: dict[int, str] = {sid: "FAT" for sid in fat_ids} | {sid: "DIFAT" for sid in difat_ids}
    dir_chain = _chain(
        fat_values,
        first_dir,
        sector_count,
        "directory",
        file=file,
        fat_sectors=fat_ids,
        sector_size=sector_size,
        owners=owners,
    )
    if major == 4 and len(dir_chain) != dir_count:
        note_records[NOTE_CODES[1]].append(("directory chain count differs from header", 0x28))
    directory_raw = b"".join(_read_sector(view, sid, sector_size) for sid in dir_chain)
    entry_count = len(directory_raw) // 128
    if entry_count > limits.max_entries:
        raise _error(
            "cfb.limit",
            f"max_entries is {limits.max_entries}, found {entry_count}",
            file=file,
            locator="directory",
            offset=None,
        )
    entries: list[_Entry] = []
    for i in range(entry_count):
        off = i * 128
        raw = directory_raw[off : off + 128]
        (
            name_buf,
            name_len,
            entry_kind,
            colour,
            left,
            right,
            child,
            entry_clsid,
            state,
            created,
            modified,
            start,
            size,
        ) = struct.unpack("<64sHBBIII16sIQQIQ", raw)
        abs_off = _sector_offset(dir_chain[off // sector_size], sector_size) + off % sector_size
        if entry_kind not in (0, 1, 2, 5):
            raise _error(
                "cfb.directory",
                f"entry type is {entry_kind}",
                file=file,
                locator=f"directory[{i}]",
                offset=abs_off + 66,
            )
        if entry_kind == 0:
            entries.append(
                _Entry(
                    i,
                    "",
                    entry_kind,
                    colour,
                    left,
                    right,
                    child,
                    entry_clsid,
                    state,
                    created,
                    modified,
                    start,
                    size,
                    abs_off,
                )
            )
            continue
        if name_len < 2 or name_len > 64 or name_len % 2:
            raise _error(
                "cfb.name",
                f"name length is {name_len}",
                file=file,
                locator=f"directory[{i}]",
                offset=abs_off + 64,
            )
        try:
            decoded = name_buf[:name_len].decode("utf-16-le")
        except UnicodeDecodeError as exc:
            raise _error(
                "cfb.name", "name is not valid UTF-16LE", file=file, locator=f"directory[{i}]", offset=abs_off
            ) from exc
        if not decoded.endswith("\0") or "\0" in decoded[:-1]:
            raise _error(
                "cfb.name",
                "name lacks a unique terminating NUL",
                file=file,
                locator=f"directory[{i}]",
                offset=abs_off,
            )
        name = decoded[:-1]
        if not name or any(ch in name for ch in "/\\:!"):
            raise _error(
                "cfb.name",
                "name is empty or contains a forbidden character",
                file=file,
                locator=f"directory[{i}]",
                offset=abs_off,
            )
        if major == 3 and size >> 32:
            note_records[NOTE_CODES[4]].append((f"entry {i} high size bits", abs_off + 124))
            size &= 0xFFFFFFFF
        entries.append(
            _Entry(
                i,
                name,
                entry_kind,
                colour,
                left,
                right,
                child,
                entry_clsid,
                state,
                created,
                modified,
                start,
                size,
                abs_off,
            )
        )
    if not entries or entries[0].kind != 5:
        raise _error(
            "cfb.directory",
            "entry 0 is not the root storage",
            file=file,
            locator="directory[0]",
            offset=entries[0].offset + 66 if entries else None,
        )
    if entries[0].left != NOSTREAM or entries[0].right != NOSTREAM:
        raise _error(
            "cfb.directory",
            "root entry has a sibling link",
            file=file,
            locator="directory[0]",
            offset=entries[0].offset + (68 if entries[0].left != NOSTREAM else 72),
        )
    if entries[0].name != "Root Entry":
        note_records[NOTE_CODES[6]].append(("root name differs from Root Entry", entries[0].offset))

    for entry in entries:
        if entry.kind == 0:
            continue
        if entry.colour not in (0, 1):
            note_records[NOTE_CODES[6]].append(
                (f"entry {entry.index} has colour {entry.colour}", entry.offset + 67)
            )
        if entry.kind == 5 and entry.created:
            note_records[NOTE_CODES[6]].append(
                (f"root entry {entry.index} has a creation time", entry.offset + 100)
            )
        elif entry.kind == 1 and (entry.start != 0 or entry.size != 0):
            note_records[NOTE_CODES[6]].append(
                (f"storage entry {entry.index} has start/size", entry.offset + 116)
            )
        elif entry.kind == 2 and (entry.clsid != bytes(16) or entry.state or entry.created or entry.modified):
            note_records[NOTE_CODES[6]].append(
                (f"stream entry {entry.index} has metadata", entry.offset + 80)
            )

    by_index = {e.index: e for e in entries}
    for entry in entries:
        if entry.kind == 2 and entry.child != NOSTREAM:
            raise _error(
                "cfb.directory",
                f"stream entry {entry.index} has child link {entry.child}",
                file=file,
                locator=f"directory[{entry.index}]",
                offset=entry.offset + 76,
            )
    children_by_index: dict[int, list[int]] = {}
    reached: set[int] = {0}
    stack: list[tuple[int, str, int]] = [(0, "", 0)]
    node_paths: dict[int, str] = {0: ""}
    while stack:
        owner_index, parent_path, depth = stack.pop()
        owner = by_index[owner_index]
        if owner.kind not in (1, 5):
            if owner.child != NOSTREAM:
                raise _error(
                    "cfb.directory",
                    "stream has a child",
                    file=file,
                    locator=f"directory[{owner.index}]",
                    offset=owner.offset + 76,
                )
            continue
        pending = [(owner.child, owner.offset + 76)]
        local_seen: set[int] = set()
        child_ids: list[int] = []
        while pending:
            idx, link_offset = pending.pop()
            if idx == NOSTREAM:
                continue
            if idx not in by_index or by_index[idx].kind == 0:
                raise _error(
                    "cfb.directory",
                    f"link names unused or outside entry {idx}",
                    file=file,
                    locator=f"directory[{owner.index}]",
                    offset=link_offset,
                )
            if idx in local_seen or idx in reached:
                raise _error(
                    "cfb.directory",
                    f"entry {idx} is reached twice",
                    file=file,
                    locator=f"directory[{idx}]",
                    offset=link_offset,
                )
            local_seen.add(idx)
            reached.add(idx)
            item = by_index[idx]
            child_ids.append(idx)
            for link, field_offset in ((item.left, 68), (item.right, 72)):
                if link != NOSTREAM:
                    pending.append((link, item.offset + field_offset))
        # Compare the actual in-order link traversal with the required name order.
        in_order: list[int] = []
        walk: list[int] = []
        cursor = owner.child
        while cursor != NOSTREAM or walk:
            while cursor != NOSTREAM:
                walk.append(cursor)
                cursor = by_index[cursor].left
            cursor = walk.pop()
            in_order.append(cursor)
            cursor = by_index[cursor].right
        siblings = sorted(child_ids, key=lambda idx: writer.name_key(by_index[idx].name))
        if in_order != siblings:
            note_records[NOTE_CODES[7]].append(
                (f"storage entry {owner.index} sibling links are out of name order", owner.offset + 76)
            )
        keys: set[tuple[int, tuple[int, ...]]] = set()
        for idx in siblings:
            key = writer.name_key(by_index[idx].name)
            if key in keys:
                raise _error(
                    "cfb.duplicate-name",
                    f"entry {idx} duplicates a sibling name",
                    file=file,
                    locator=f"directory[{idx}]",
                    offset=by_index[idx].offset,
                )
            keys.add(key)
        children_by_index[owner_index] = siblings
        for idx in reversed(siblings):
            item = by_index[idx]
            path = f"{parent_path}/{item.name}" if parent_path else item.name
            node_paths[idx] = path
            if item.kind == 1:
                if depth + 1 > limits.max_depth:
                    raise _error(
                        "cfb.limit",
                        f"max_depth is {limits.max_depth}, found {depth + 1}",
                        file=file,
                        locator=f"storage:{path}",
                        offset=item.offset,
                    )
                stack.append((idx, path, depth + 1))
    orphans = [e for e in entries if e.kind in (1, 2) and e.index not in reached]
    if orphans:
        note_records[NOTE_CODES[8]].append((f"{len(orphans)} orphan entries", orphans[0].offset))

    # Chain every stream and the mini stream before returning. Runs are retained for lazy reads.
    mini_owner: dict[int, str] = {}
    mini_data_start = 0
    mini_data_size = entries[0].size
    root_entry = entries[0]
    mini_stream_chain = _chain(
        fat_values,
        root_entry.start,
        sector_count,
        "mini-stream",
        file=file,
        fat_sectors=fat_ids,
        sector_size=sector_size,
        owners=owners,
    )
    if len(mini_stream_chain) * sector_size < mini_data_size:
        raise _error(
            "cfb.size",
            "mini stream is larger than its sector chain",
            file=file,
            locator="mini-stream",
            offset=root_entry.offset + 120,
        )
    needed_root = (mini_data_size + sector_size - 1) // sector_size
    if len(mini_stream_chain) > needed_root:
        note_records[NOTE_CODES[5]].append(("root mini stream has a long chain", root_entry.offset + 116))
    if mini_stream_chain:
        mini_data_start = _sector_offset(mini_stream_chain[0], sector_size)
    minifat_chain = _chain(
        fat_values,
        first_minifat,
        sector_count,
        "mini-fat",
        file=file,
        fat_sectors=fat_ids,
        sector_size=sector_size,
        owners=owners,
    )
    if len(minifat_chain) != minifat_count:
        note_records[NOTE_CODES[1]].append(("mini-FAT chain count differs from header", 0x40))
    minifat_raw = b"".join(_read_sector(view, sid, sector_size) for sid in minifat_chain)
    minifat: list[int] = list(struct.unpack(f"<{len(minifat_raw) // 4}I", minifat_raw)) if minifat_raw else []
    chains: dict[str, tuple[tuple[int, int], ...]] = {}
    mini_chains: dict[str, tuple[tuple[int, int], ...]] = {}
    for entry in entries:
        if entry.kind != 2 or entry.index not in node_paths:
            continue
        path = node_paths[entry.index]
        required_size = entry.size
        if required_size >= cutoff:
            ids = _chain(
                fat_values,
                entry.start,
                sector_count,
                f"stream:{path}",
                file=file,
                fat_sectors=fat_ids,
                sector_size=sector_size,
                owners=owners,
            )
            needed = (required_size + sector_size - 1) // sector_size
            if len(ids) < needed:
                raise _error(
                    "cfb.chain",
                    f"chain has {len(ids)} sectors, size needs {needed}",
                    file=file,
                    locator=f"stream:{path}",
                    offset=entry.offset + 116,
                )
            if len(ids) > needed:
                note_records[NOTE_CODES[5]].append((f"stream {path} has a long chain", entry.offset + 116))
            chains[path] = _runs(ids[:needed])
        elif required_size:
            ids: list[int] = []
            seen: set[int] = set()
            current = entry.start
            needed = (required_size + 63) // 64
            while current != ENDOFCHAIN:
                if current >= len(minifat) or current in seen:
                    raise _error(
                        "cfb.chain",
                        f"mini sector {current} repeats or is outside mini FAT",
                        file=file,
                        locator=f"stream:{path}",
                        offset=entry.offset + 116,
                    )
                if current in mini_owner:
                    raise _error(
                        "cfb.shared-sector",
                        f"mini sector {current} also belongs to {mini_owner[current]}",
                        file=file,
                        locator=f"stream:{path}",
                        offset=entry.offset + 116,
                    )
                seen.add(current)
                mini_owner[current] = path
                ids.append(current)
                next_mini = minifat[current]
                if next_mini in (FREESECT, FATSECT, DIFSECT):
                    raise _error(
                        "cfb.chain",
                        f"mini sector {current} ends with invalid value {next_mini:#x}",
                        file=file,
                        locator=f"stream:{path}",
                        offset=entry.offset + 116,
                    )
                current = next_mini
            if len(ids) < needed:
                raise _error(
                    "cfb.chain",
                    f"mini chain has {len(ids)} sectors, size needs {needed}",
                    file=file,
                    locator=f"stream:{path}",
                    offset=entry.offset + 116,
                )
            if len(ids) > needed:
                note_records[NOTE_CODES[5]].append(
                    (f"stream {path} has a long mini chain", entry.offset + 116)
                )
            if ids and (max(ids) + 1) * 64 > mini_data_size:
                raise _error(
                    "cfb.size",
                    "mini stream is too short for this mini chain",
                    file=file,
                    locator="mini-stream",
                    offset=entry.offset + 116,
                )
            mini_chains[path] = _runs(ids[:needed])
    # Emit notes in the public, closed order and use the first locator for navigation.
    issues: list[Issue] = []
    for code in NOTE_CODES:
        found = note_records[code]
        if not found:
            continue
        message, offset = found[0]
        severity = "warning" if code in (NOTE_CODES[2], NOTE_CODES[7], NOTE_CODES[8]) else "info"
        entry = next((e for e in entries if offset is not None and e.offset <= offset < e.offset + 128), None)
        if entry is not None:
            if entry.kind == 2:
                locator = f"stream:{node_paths.get(entry.index, entry.name)}"
            elif entry.kind == 1:
                locator = f"storage:{node_paths.get(entry.index, entry.name)}"
            else:
                locator = "directory[0]"
        elif code == NOTE_CODES[3]:
            locator = "fat"
        else:
            locator = "header" if offset is None or offset < sector_size else "directory"
        issues.append(
            Issue(code, severity, f"{len(found)} case(s); first at {locator}: {message}", where=locator)
        )
    if strict and issues:
        issue = issues[0]
        raise _error(
            issue.code, issue.message, file=file, locator=issue.where, offset=note_records[issue.code][0][1]
        )
    nodes: list[Node] = []
    node_children: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        if entry.index not in reached:
            continue
        path = node_paths.get(entry.index, "")
        kind: Literal["root", "storage", "stream"] = (
            "root" if entry.kind == 5 else "storage" if entry.kind == 1 else "stream"
        )
        kids = tuple(node_paths[i] for i in children_by_index.get(entry.index, []))
        node_children[path] = kids
        nodes.append(
            Node(
                path,
                entry.name,
                kind,
                entry.size if kind == "stream" else 0,
                entry.index,
                entry.clsid,
                entry.state,
                entry.created,
                entry.modified,
                kids,
            )
        )
    # Public traversal is a stable depth-first walk, independent of directory index order.
    ordered: list[Node] = []
    node_map = {n.path: n for n in nodes}
    todo = [""]
    while todo:
        path = todo.pop()
        node = node_map[path]
        ordered.append(node)
        todo.extend(reversed(node_children.get(path, ())))
    public_header = Header(
        major, minor, sector_size, 64, sector_count, fat_count, difat_count, entry_count, transaction
    )
    return CompoundFile(
        public_header,
        tuple(issues),
        EVIDENCE_V3 if major == 3 else EVIDENCE_V4,
        node_map[""],
        tuple(ordered),
        {_lookup_key(n.path): n for n in ordered},
        node_children,
        chains,
        mini_chains,
        view,
        sector_size,
        mini_data_start,
        mini_data_size,
        tuple(mini_stream_chain),
        owners,
        tuple(fat_values[:sector_count]),
        hashlib.sha256(view).hexdigest(),
    )


def read_compound(path: str | Path, *, limits: Limits = DEFAULT_LIMITS, strict: bool = False) -> CompoundFile:
    """Read a compound file, checking its size before reading bytes from disk."""
    source = Path(path)
    size = source.stat().st_size
    if size > limits.max_file_bytes:
        raise _error(
            "cfb.limit",
            f"max_file_bytes is {limits.max_file_bytes}, found {size}",
            file=str(path),
            offset=None,
        )
    return open_compound(source.read_bytes(), file=str(path), limits=limits, strict=strict)
