# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored MS-CFB containers and mutations built from the local format fact page."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

SECTOR = 512
ENTRY = 128
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF
SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")


@dataclass(frozen=True)
class Built:
    data: bytes
    offsets: dict[str, int]


def _entry(
    name: str,
    kind: int,
    *,
    left: int = NOSTREAM,
    right: int = NOSTREAM,
    child: int = NOSTREAM,
    clsid: bytes = bytes(16),
    state: int = 0,
    created: int = 0,
    modified: int = 0,
    start: int = 0,
    size: int = 0,
    colour: int = 1,
) -> bytes:
    encoded = (name + "\0").encode("utf-16-le")
    return struct.pack(
        "<64sHBBIII16sIQQIQ",
        encoded,
        len(encoded),
        kind,
        colour,
        left,
        right,
        child,
        clsid,
        state,
        created,
        modified,
        start,
        size,
    )


def spec_example() -> bytes:
    """MS-CFB section 3's worked example, encoded from its field values."""
    header = struct.pack(
        "<8s16sHHHHH6s9I",
        SIGNATURE,
        bytes(16),
        0x003E,
        3,
        0xFFFE,
        9,
        6,
        bytes(6),
        0,
        1,
        1,
        0,
        4096,
        2,
        1,
        ENDOFCHAIN,
        0,
    ) + struct.pack("<109I", 0, *([FREESECT] * 108))
    fat = struct.pack("<128I", FATSECT, ENDOFCHAIN, ENDOFCHAIN, 4, ENDOFCHAIN, *([FREESECT] * 123))
    unused = bytes(68) + struct.pack("<3I", NOSTREAM, NOSTREAM, NOSTREAM) + bytes(48)
    directory = b"".join(
        (
            _entry("Root Entry", 5, child=1, start=3, size=576),
            _entry(
                "Storage 1",
                1,
                child=2,
                clsid=bytes(range(1, 17)),
                created=0x01D0000000000001,
                modified=0x01D0000000000002,
            ),
            _entry("Stream 1", 2, start=0, size=544),
            unused,
        )
    )
    minifat = struct.pack("<128I", *range(1, 9), ENDOFCHAIN, *([FREESECT] * 119))
    stream = bytes(0x41 + i % 26 for i in range(544))
    return header + fat + directory + minifat + stream.ljust(2 * SECTOR, b"\0")


def build(
    entries: list[dict[str, Any]],
    *,
    version: int = 3,
    root: dict[str, Any] | None = None,
    pad_fat_sectors: int = 0,
) -> Built:
    """Build a small version 3/4 container from rows with ``path`` and ``data`` fields.

    Parent storages are inferred from slash-separated paths. Optional row fields configure entry
    metadata (``colour``, ``clsid``, ``state``, ``created`` and ``modified``).
    """
    if version not in (3, 4):
        raise ValueError("version must be 3 or 4")
    sector = 512 if version == 3 else 4096
    per_fat = sector // 4
    per_dir = sector // ENTRY
    storage_rows = {str(row["path"]): row for row in entries if row.get("kind") == "storage"}
    paths = {str(row["path"]): row for row in entries if row.get("kind") != "storage"}
    storages: set[str] = set(storage_rows)
    for path in (*paths, *storage_rows):
        parts = path.split("/")
        storages.update("/".join(parts[:i]) for i in range(1, len(parts)))
    names: dict[str, list[str]] = {"": []}
    for storage in sorted(storages):
        parent, _, name = storage.rpartition("/")
        names.setdefault(parent, []).append(name)
        names.setdefault(storage, [])
    for path in paths:
        parent, _, name = path.rpartition("/")
        names.setdefault(parent, []).append(name)
    # Root and each storage own an independent, name-ordered sibling tree. A balanced all-black
    # binary search tree is sufficient for these authored structures.
    rows: list[dict[str, Any]] = [{"path": "", "name": "Root Entry", "kind": 5, **(root or {})}]
    for path in sorted(storages, key=lambda p: (p.count("/"), p)):
        rows.append(
            {
                **storage_rows.get(path, {}),
                "path": path,
                "name": path.rsplit("/", 1)[-1],
                "kind": 1,
            }
        )
    for path, source in paths.items():
        rows.append({**source, "path": path, "name": path.rsplit("/", 1)[-1], "kind": 2})
    index = {str(row["path"]): i for i, row in enumerate(rows)}
    links: dict[int, tuple[int, int]] = {}
    children: dict[int, int] = {}
    for parent, siblings in names.items():
        ids = sorted(
            (index[parent + "/" + n if parent else n] for n in siblings),
            key=lambda i: (len(rows[i]["name"].upper()), rows[i]["name"].upper()),
        )

        def tree(items: list[int]) -> int:
            if not items:
                return NOSTREAM
            mid = len(items) // 2
            i = items[mid]
            links[i] = (tree(items[:mid]), tree(items[mid + 1 :]))
            return i

        top = tree(ids)
        owner = index[parent]
        if top != NOSTREAM:
            children[owner] = top

    # Layout large streams first, then mini streams packed in 64-byte mini sectors.
    mini_payload = bytearray()
    minifat_items: list[int] = []
    regular_payload: list[bytes] = []
    starts: dict[int, int] = {}
    regular_counts: dict[int, int] = {}
    for i, row in enumerate(rows):
        if row["kind"] != 2:
            continue
        data = bytes(row.get("data", b""))
        row["size"] = len(data)
        if len(data) < 4096:
            first = len(minifat_items)
            count = (len(data) + 63) // 64
            starts[i] = first if count else ENDOFCHAIN
            for n in range(count):
                minifat_items.append(first + n + 1 if n + 1 < count else ENDOFCHAIN)
            mini_payload.extend(data.ljust(count * 64, b"\0"))
        else:
            count = (len(data) + sector - 1) // sector
            starts[i] = -1
            regular_counts[i] = count
            regular_payload.extend(
                data[j * sector : (j + 1) * sector].ljust(sector, b"\0") for j in range(count)
            )
    dir_sectors = max(1, (len(rows) + per_dir - 1) // per_dir)
    minifat_sectors = (len(minifat_items) * 4 + sector - 1) // sector
    mini_sectors = (len(mini_payload) + sector - 1) // sector
    nonfat_count = dir_sectors + minifat_sectors + mini_sectors + len(regular_payload)
    fat_count = 1
    while True:
        difat_count = max(0, (fat_count - 109 + (per_fat - 2)) // (per_fat - 1))
        needed = (fat_count + nonfat_count + pad_fat_sectors + difat_count + per_fat - 1) // per_fat
        if needed <= fat_count:
            break
        fat_count = needed
    # Lay out FAT, directory, mini FAT, root mini stream and large stream sectors.
    fat_ids = list(range(fat_count))
    next_id = fat_count
    dir_ids = list(range(next_id, next_id + dir_sectors))
    next_id += dir_sectors
    mf_ids = list(range(next_id, next_id + minifat_sectors))
    next_id += minifat_sectors
    mini_ids = list(range(next_id, next_id + mini_sectors))
    next_id += mini_sectors
    regular_sector_payloads: dict[int, bytes] = {}
    for i, count in regular_counts.items():
        starts[i] = next_id
        stream = bytes(rows[i].get("data", b""))
        for n in range(count):
            regular_sector_payloads[next_id + n] = stream[n * sector : (n + 1) * sector].ljust(sector, b"\0")
        next_id += count
    # Padding creates unowned, FREESECT sectors and can force a DIFAT chain in tests.
    total = next_id + pad_fat_sectors
    difat_ids = list(range(total, total + difat_count))
    total += difat_count
    fat = [FREESECT] * (fat_count * per_fat)
    for i in fat_ids:
        fat[i] = FATSECT
    for chain in (dir_ids, mf_ids, mini_ids):
        for a, b in zip(chain, chain[1:], strict=False):
            fat[a] = b
        if chain:
            fat[chain[-1]] = ENDOFCHAIN
    for i, count in regular_counts.items():
        start = starts[i]
        for n in range(count):
            fat[start + n] = start + n + 1 if n + 1 < count else ENDOFCHAIN
    for sector_id in difat_ids:
        fat[sector_id] = 0xFFFFFFFC
    for i, row in enumerate(rows):
        if row["kind"] == 5:
            row["start"] = mini_ids[0] if mini_ids else ENDOFCHAIN
            row["size"] = len(minifat_items) * 64
        elif row["kind"] == 1:
            row["start"] = 0
            row["size"] = 0
        else:
            row["start"] = starts[i]
    # Directory slots and FAT sectors are serialized independently of product code.
    unused = bytes(68) + struct.pack("<3I", NOSTREAM, NOSTREAM, NOSTREAM) + bytes(48)
    directory = bytearray(unused * (dir_sectors * per_dir))
    offsets: dict[str, int] = {}
    for i, row in enumerate(rows):
        pos = i * ENTRY
        offsets[f"entry:{row['path']}"] = (1 + dir_ids[0]) * sector + pos
        left, right = links.get(i, (NOSTREAM, NOSTREAM))
        directory[pos : pos + ENTRY] = _entry(
            str(row["name"]),
            int(row["kind"]),
            left=left,
            right=right,
            child=children.get(i, NOSTREAM),
            clsid=bytes(row.get("clsid", bytes(16))),
            state=int(row.get("state", 0)),
            created=int(row.get("created", 0)),
            modified=int(row.get("modified", 0)),
            start=int(row.get("start", ENDOFCHAIN)),
            size=int(row.get("size", 0)),
            colour=int(row.get("colour", 1)),
        )
    fat_data = b"".join(
        struct.pack(f"<{per_fat}I", *fat[i * per_fat : (i + 1) * per_fat]) for i in range(fat_count)
    )
    minifat_data = (
        struct.pack(
            f"<{minifat_sectors * per_fat}I",
            *(minifat_items + [FREESECT] * (minifat_sectors * per_fat - len(minifat_items))),
        )
        if minifat_sectors
        else b""
    )
    difat_entries = fat_ids[109:]
    difat_data = bytearray()
    stride = per_fat - 1
    for i in range(difat_count):
        chunk = difat_entries[i * stride : (i + 1) * stride]
        chunk += [FREESECT] * (stride - len(chunk))
        difat_data.extend(
            struct.pack(f"<{stride}II", *chunk, difat_ids[i + 1] if i + 1 < difat_count else ENDOFCHAIN)
        )
    header = struct.pack(
        "<8s16sHHHHH6s9I",
        SIGNATURE,
        bytes(16),
        0x003E,
        version,
        0xFFFE,
        9 if version == 3 else 12,
        6,
        bytes(6),
        0 if version == 3 else dir_sectors,
        fat_count,
        dir_ids[0],
        0,
        4096,
        mf_ids[0] if mf_ids else ENDOFCHAIN,
        minifat_sectors,
        difat_ids[0] if difat_ids else ENDOFCHAIN,
        difat_count,
    )
    header_difat = (fat_ids[:109] + [FREESECT] * 109)[:109]
    header += struct.pack("<109I", *header_difat)
    header = header.ljust(sector, b"\0")
    sectors = [bytes(sector) for _ in range(total)]
    for i in range(fat_count):
        sectors[fat_ids[i]] = fat_data[i * sector : (i + 1) * sector]
    for i, sid in enumerate(dir_ids):
        sectors[sid] = bytes(directory[i * sector : (i + 1) * sector])
    for i, sid in enumerate(mf_ids):
        sectors[sid] = minifat_data[i * sector : (i + 1) * sector]
    for i, sid in enumerate(mini_ids):
        sectors[sid] = bytes(mini_payload[i * sector : (i + 1) * sector]).ljust(sector, b"\0")
    for sid, payload in regular_sector_payloads.items():
        sectors[sid] = payload
    for i in range(difat_count):
        sectors[difat_ids[i]] = bytes(difat_data[i * sector : (i + 1) * sector])
    offsets.update(
        {
            "header": 0,
            "fat": sector,
            "directory": (1 + dir_ids[0]) * sector,
            "minifat": (mf_ids[0] + 1) * sector if mf_ids else -1,
            "mini-stream": (mini_ids[0] + 1) * sector if mini_ids else -1,
            "difat": (1 + difat_ids[0]) * sector if difat_ids else -1,
        }
    )
    return Built(header + b"".join(sectors), offsets)


def cycle(data: bytearray, offset: int, first_sector: int) -> int:
    """Point a FAT entry back to ``first_sector`` and return the changed field offset."""
    struct.pack_into("<I", data, offset, first_sector)
    return offset


def share(data: bytearray, offset: int, sector_number: int) -> int:
    """Point a directory start field at an already-owned sector."""
    struct.pack_into("<I", data, offset, sector_number)
    return offset


def cut(data: bytearray, count: int = 1) -> int:
    """Remove bytes from the end and return the first removed offset."""
    offset = max(0, len(data) - count)
    del data[offset:]
    return offset


def set_field(data: bytearray, offset: int, value: int, width: int = 4) -> int:
    """Change an integer field and return its byte offset."""
    struct.pack_into({2: "<H", 4: "<I", 8: "<Q"}[width], data, offset, value)
    return offset
