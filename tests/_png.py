# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A PNG made byte by byte for the tests of board images (change c0277), authored for Fenolite."""

from __future__ import annotations

import struct
import zlib


def png(width: int = 40, height: int = 40) -> bytes:
    """A grey-scale checkerboard PNG of ``width`` × ``height`` pixels."""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    rows = b"".join(b"\x00" + bytes(255 * ((x + y) % 2) for x in range(width)) for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
