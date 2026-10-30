# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board image through ``fenolite import --to python`` (capability board-to-code; change c0277): the reader
models it, the import writes ``design.image()`` and the PNG beside the code, and the build writes the image
again."""

from __future__ import annotations

import base64
from pathlib import Path

from _importcode import build, imaged, imported
from _png import png

from fenolite.backends.kicad.pcb import read_board


def test_image_is_written(tmp_path: Path) -> None:
    data = png(24, 16)
    reply = imported(tmp_path, imaged(tmp_path / "src", data), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    flat = " ".join(code.split())
    assert (
        'design.image("F.SilkS/image/1", "images/F.SilkS-1.png", (mm("20"), mm("40")), scale="0.5")' in flat
    )
    assert (tmp_path / "out" / "images" / "F.SilkS-1.png").read_bytes() == data
    assert build(tmp_path / "out").exit_code == 0
    back = read_board(tmp_path / "out" / "built" / "imaged.kicad_pcb")
    assert back.board is not None
    (image,) = back.board.images
    assert base64.b64decode(image.data) == data and image.scale == "0.5"
