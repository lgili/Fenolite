# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Container measurement of the cached Altium Draftsman documents (change c0172, task 1.2).

    uv run python tools/draftsman_census.py [--json] [--tree] [FILE ...]

Without files, reads every cached row of ``tests/corpus/manifest.toml`` that carries ``altium-draftsman``.
For each document it measures the container (``docs/evidence/altium-draftsman.md``, "Census"): the first
eight bytes and what they are, the chunks with their flags and lengths, the LZ4 sequences of each chunk (the
block format of S-0803), whether every block decodes on its own, whether the decoded text is well-formed XML,
and the result of each candidate decoder of design Decision 1 at the start of the file and of each chunk.
With ``--tree`` it adds the tree census of task 2.2, read with ``fenolite.backends.altium.read.draftsman``.

The output holds row ids, counts, lengths, flags, byte values of the container and the names of the
candidates only, never a value or a name of the document's content. The measuring code is Fenolite's own,
written from the public block format description; no third-party parser or program code was read.
"""

from __future__ import annotations

import argparse
import bz2
import json
import lzma
import os
import sys
import tomllib
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
TAG = "altium-draftsman"
NAMESPACE = "http://schemas.datacontract.org/2004/07/Altium.Designer.PcbDrawing.DataSerialization.V1"
MAGICS: dict[str, bytes] = {
    "lz4-frame": bytes.fromhex("04224d18"),
    "zstd-frame": bytes.fromhex("28b52ffd"),
    "xz": bytes.fromhex("fd377a585a00"),
    "gzip": bytes.fromhex("1f8b"),
    "snappy-framed": bytes.fromhex("ff060000734e61507059"),
    "zlib-default": bytes.fromhex("789c"),
}
"""The leading bytes of the framed candidates (S-0804, S-0807, S-0808, S-0809, S-0811, S-0805)."""
STDLIB: dict[str, Any] = {
    "deflate-raw": lambda b: zlib.decompressobj(-15).decompress(b, 64),
    "zlib": lambda b: zlib.decompressobj(15).decompress(b, 64),
    "gzip": lambda b: zlib.decompressobj(31).decompress(b, 64),
    "lzma-auto": lambda b: lzma.LZMADecompressor(lzma.FORMAT_AUTO).decompress(b, 64),
    "lzma-alone": lambda b: lzma.LZMADecompressor(lzma.FORMAT_ALONE).decompress(b, 64),
    "bzip2": lambda b: bz2.BZ2Decompressor().decompress(b, 64),
}
"""The candidates that Python's standard library decodes (S-0805 to S-0807, S-0809; bzip2 by the library)."""


class ContainerError(ValueError):
    """The bytes do not follow the measured chunk form; the message names the offset."""


def default_cache() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def cached_rows(cache: Path, manifest: Path = MANIFEST) -> tuple[list[tuple[str, Path]], list[str]]:
    """``(row id, cached path)`` of every row with ``altium-draftsman``, and the ids not cached."""
    rows = tomllib.loads(manifest.read_text(encoding="utf-8")).get("file", [])
    found: list[tuple[str, Path]] = []
    missing: list[str] = []
    for row in rows:
        if TAG not in row.get("uses", []):
            continue
        name = urllib.parse.unquote(Path(urllib.parse.urlparse(row["url"]).path).name) or row["id"]
        path = cache / row["id"] / name
        if path.is_file():
            found.append((row["id"], path))
        else:
            missing.append(row["id"])
    return found, missing


def varint(data: bytes, at: int) -> tuple[int, int]:
    """A 7-bit encoded unsigned integer at ``at`` (low group first, high bit set on every byte but the last;
    S-0810) and the offset after it."""
    value = shift = 0
    while True:
        if at >= len(data):
            raise ContainerError(f"offset {at}: the length runs past the end")
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, at
        shift += 7
        if shift > 35:
            raise ContainerError(f"offset {at}: a length of more than five bytes")


def encode_varint(value: int) -> bytes:
    """``value`` in the 7-bit form that ``varint`` reads."""
    out = bytearray()
    while True:
        out.append((value & 0x7F) | (0x80 if value > 0x7F else 0))
        value >>= 7
        if not value:
            return bytes(out)


def _length(block: bytes, at: int, base: int) -> tuple[int, int]:
    length = base
    if base == 15:
        while True:
            if at >= len(block):
                raise ContainerError(f"block offset {at}: a length runs past the end")
            byte = block[at]
            at += 1
            length += byte
            if byte != 255:
                break
    return length, at


def lz4_block(block: bytes, stats: Counter[str] | None = None) -> bytes:
    """Decode one LZ4 block (S-0803) that refers to no earlier data. ``stats`` gains the sequence count,
    the literal and match bytes, the longest literal run and the largest offset."""
    out = bytearray()
    at = 0
    seen = stats if stats is not None else Counter()
    while True:
        if at >= len(block):
            raise ContainerError(f"block offset {at}: the block ends without a last literal run")
        token = block[at]
        literals, at = _length(block, at + 1, token >> 4)
        if at + literals > len(block):
            raise ContainerError(f"block offset {at}: {literals} literals run past the end")
        out += block[at : at + literals]
        at += literals
        seen["sequences"] += 1
        seen["literal_bytes"] += literals
        seen["longest_literal_run"] = max(seen["longest_literal_run"], literals)
        if at == len(block):
            seen["last_literals"] = literals
            return bytes(out)
        if at + 2 > len(block):
            raise ContainerError(f"block offset {at}: the offset runs past the end")
        offset = block[at] | block[at + 1] << 8
        if offset == 0 or offset > len(out):
            raise ContainerError(f"block offset {at}: offset {offset} reaches before the block")
        match, at = _length(block, at + 2, token & 15)
        match += 4
        seen["match_bytes"] += match
        seen["largest_offset"] = max(seen["largest_offset"], offset)
        start = len(out) - offset
        if offset >= match:
            out += out[start : start + match]
        else:
            pattern = bytes(out[start:])
            out += (pattern * (match // offset + 1))[:match]


def chunks(data: bytes) -> list[dict[str, int]]:
    """The chunks of a document: ``flag``, ``offset``, ``header`` (bytes before the payload), ``size``
    (decoded length) and ``stored`` (payload length)."""
    found: list[dict[str, int]] = []
    at = 0
    while at < len(data):
        flag = data[at]
        size, after = varint(data, at + 1)
        if flag == 0:
            stored = size
        elif flag == 1:
            stored, after = varint(data, after)
        else:
            raise ContainerError(f"offset {at}: chunk flag {flag} is neither 0 nor 1")
        if after + stored > len(data):
            raise ContainerError(f"offset {at}: the chunk runs past the end")
        found.append({"flag": flag, "offset": at, "header": after - at, "size": size, "stored": stored})
        at = after + stored
    return found


def decode(data: bytes, stats: Counter[str] | None = None) -> bytes:
    """The decoded text of a document: each chunk is stored (flag 0) or one LZ4 block (flag 1)."""
    parts: list[bytes] = []
    for chunk in chunks(data):
        start = chunk["offset"] + chunk["header"]
        payload = data[start : start + chunk["stored"]]
        text = payload if chunk["flag"] == 0 else lz4_block(payload, stats)
        if len(text) != chunk["size"]:
            declared = chunk["size"]
            raise ContainerError(f"offset {chunk['offset']}: {len(text)} bytes decoded, {declared} declared")
        parts.append(text)
    return b"".join(parts)


def _is_text(piece: bytes) -> bool:
    """At least 16 decoded bytes, all printable ASCII, tab or line ends: a raw-deflate decoder returns a
    few bytes of many inputs before it fails, which is no decoding."""
    return len(piece) >= 16 and all(32 <= byte < 127 or byte in (9, 10, 13) for byte in piece)


def _candidates(data: bytes, starts: list[int]) -> dict[str, int]:
    """Per candidate, at how many of ``starts`` (and the offsets 0 to 8) it decodes text (``_is_text``)
    or its leading bytes are present."""
    offsets = sorted({*range(9), *starts})
    result: dict[str, int] = {}
    for name, function in STDLIB.items():
        hits = 0
        for at in offsets:
            try:
                hits += _is_text(function(data[at : at + 4096]))
            except (zlib.error, lzma.LZMAError, OSError, EOFError, ValueError):
                pass
        result[name] = hits
    for name, magic in MAGICS.items():
        result[f"{name}-magic"] = sum(data.startswith(magic, at) for at in offsets)
    return result


def _xml(text: bytes) -> dict[str, Any]:
    """Well-formedness, the root's namespace and the element count, by a streaming parse."""
    count = 0
    root_ns = ""
    try:
        for event, element in ET.iterparse(_Reader(text), events=("start", "end")):
            if event == "start":
                if count == 0:
                    root_ns = element.tag[1:].split("}")[0] if element.tag.startswith("{") else ""
                count += 1
            else:
                element.clear()
    except ET.ParseError as error:
        return {"well_formed": False, "error": str(error.code), "elements": count}
    return {"well_formed": True, "namespace_ok": root_ns == NAMESPACE, "elements": count}


class _Reader:
    """A file-like view of ``text`` for ``iterparse`` without copying it."""

    def __init__(self, text: bytes) -> None:
        self._view = memoryview(text)
        self._at = 0

    def read(self, size: int = -1) -> bytes:
        end = len(self._view) if size < 0 else min(len(self._view), self._at + size)
        piece = bytes(self._view[self._at : end])
        self._at = end
        return piece


def measure(data: bytes) -> dict[str, Any]:
    """The container census of one document: counts and container bytes only."""
    found = chunks(data)
    stats: Counter[str] = Counter()
    text = decode(data, stats)
    first = found[0]
    payload = data[first["offset"] + first["header"] :]
    lengths = (encode_varint(first["stored"]) if first["flag"] == 1 else b"") + payload
    head_ok = data[:4] == bytes([first["flag"]]) + encode_varint(first["size"])
    sizes = Counter(chunk["size"] for chunk in found[:-1])
    return {
        "bytes": len(data),
        "first_bytes": data[:8].hex(" "),
        "first_four_are_flag_and_size": head_ok,
        "field_is_length_and_first_token": data[4:8] == lengths[:4],
        "chunks": len(found),
        "flags": dict(sorted(Counter(str(chunk["flag"]) for chunk in found).items())),
        "chunk_header_lengths": dict(sorted(Counter(str(chunk["header"]) for chunk in found).items())),
        "full_chunk_sizes": {str(size): count for size, count in sorted(sizes.items())},
        "last_chunk_size": found[-1]["size"],
        "ends_at_last_chunk": True,  # chunks() refuses a chunk that runs past the end and stops at it
        "independent_blocks": True,  # lz4_block() refuses an offset before the start of its own block
        "decoded_bytes": len(text),
        "ratio_percent": round(100 * len(data) / max(1, len(text)), 2),
        "sequences": stats["sequences"],
        "literal_bytes": stats["literal_bytes"],
        "match_bytes": stats["match_bytes"],
        "longest_literal_run": stats["longest_literal_run"],
        "largest_offset": stats["largest_offset"],
        "starts_with_document": text.startswith(b'<Document xmlns="' + NAMESPACE.encode() + b'"'),
        "xml": _xml(text),
        "candidates": {
            **_candidates(data, [c["offset"] + c["header"] for c in found]),
            "lz4-block-chunks": sum(chunk["flag"] == 1 for chunk in found),
        },
    }


def tree(data: bytes) -> dict[str, Any]:
    """The tree census of one document (task 2.2) with Fenolite's reader: element counts, the root's
    members and which are nil, the share of the board data members, and per sheet its paper and the kinds
    of its items; views with side and scale, tables with side, notes with their entry count."""
    from fenolite.backends.altium.read.draftsman import INSTANCE, read_draftsman, summary

    file = read_draftsman(data)
    root = file.root
    counts = {child.tag.split("}")[-1]: sum(1 for _ in child.iter()) for child in root}
    nil = sorted(
        child.tag.split("}")[-1]
        for child in root
        if child.get(f"{{{INSTANCE}}}nil") == "true" and not len(child)
    )
    total = sum(1 for _ in root.iter())
    board = sum(count for name, count in counts.items() if name.endswith("Information"))
    result = summary(file)
    return {
        "elements": total,
        "root_members": sorted(counts),
        "nil_members": nil,
        "board_data_elements": board,
        "board_data_percent": round(100 * board / total, 1),
        "page_elements": counts.get("Pages", 0),
        "format_version": result.format_version,
        "sheets": [
            {
                "paper": sheet.paper,
                "sizing": sheet.sizing,
                "size": list(sheet.size),
                "items": len(sheet.items),
            }
            for sheet in result.sheets
        ],
        "kinds": dict(sorted(Counter(item.kind for sheet in result.sheets for item in sheet.items).items())),
        "views": [[item.name, item.side, list(item.scale or ())] for item in result.items("view")],
        "tables": [[item.name, item.side] for item in result.items("table")],
        "note_entries": [len(item.texts) for item in result.items("note")],
        "texts": len(result.items("text")),
        "parameter_texts": sum(1 for item in result.items("text") if item.texts[0].startswith("=")),
        "document_parameters": len(result.parameters),
    }


def census(paths: list[tuple[str, Path]], *, with_tree: bool = False) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for ident, path in paths:
        data = path.read_bytes()
        try:
            rows[ident] = measure(data)
            if with_tree:
                rows[ident]["tree"] = tree(data)
        except (ContainerError, ValueError) as error:
            rows[ident] = {"error": str(error)}
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tree", action="store_true", help="add the tree census of each document")
    args = parser.parse_args(argv)
    if args.files:
        rows, missing = [(f"file-{n}", p) for n, p in enumerate(args.files, 1)], []
    else:
        rows, missing = cached_rows(default_cache())
    result = {"rows": census(rows, with_tree=args.tree), "missing": missing}
    if args.json:
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        for ident, row in result["rows"].items():
            print(ident, {k: v for k, v in row.items() if k not in ("candidates", "tree")})
            if "tree" in row:
                print("  tree", row["tree"])
            print("  candidates", row.get("candidates"))
        if missing:
            print("missing", missing)
    return 1 if any("error" in row for row in result["rows"].values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
