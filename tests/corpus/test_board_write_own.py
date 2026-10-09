# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Major-9 demo boards written for their own target 9 (capability kicad-file-backend, "Net form per
target"; change c0163).

Each readable non-heavy demo board of major 9 is written with ``write_board(design, target=9)``: the write
raises nothing, and the re-read model equals the source's apart from the board's header bag, net numbers
and the text of opaque fragments (a 9 → 9 write renumbers nets). No ``kicad-cli`` is needed; the KiCad
oracle of the same write is ``tests/kicad/board/test_written_own_target.py``. Items are named by their
manifest id only.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import canonical
from _corpus import CorpusItem, require

from fenolite.backends.kicad.pcb import opaque_count, read_board, write_board
from fenolite.backends.kicad.versions import FileKind, major_for
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
DEMOS = [i for i in READABLE_ITEMS if not i.heavy]
HEADER = re.compile(r"\(version (\d{8})\)")


def header_major(item: CorpusItem) -> int | None:
    """The major of the board's header, read from the first bytes of the file."""
    found = HEADER.search(item.path.read_text(encoding="utf-8")[:200])
    return major_for(FileKind.BOARD, int(found.group(1))) if found else None


def _opaque(key: str) -> bool:
    return key.startswith("slot:") and key.rpartition(":")[2].startswith("opaque")


def _normal(data: Any) -> Any:
    """``data`` with opaque fragment texts and minimum versions left out."""
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():  # pyright: ignore[reportUnknownVariableType]
            if key == "min_version":
                continue
            if key == "payload":
                value = [
                    [k.split("@")[0], "<fragment>"] if _opaque(k) else [k, v]
                    for k, v in value  # pyright: ignore[reportUnknownVariableType]
                ]
            out[key] = _normal(value)
        return out
    if isinstance(data, list):
        return [_normal(v) for v in data]  # pyright: ignore[reportUnknownVariableType]
    return data


def comparable(design: Design) -> Any:
    data = canonical(design)
    data[2].pop("ext", None)
    for net in data[1].get("nets", []):
        net.pop("ext", None)
    return _normal(data)


@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_written_for_own_target_9(item: CorpusItem) -> None:
    path = require(item)
    if header_major(item) != 9:
        pytest.skip(f"{item.id} is not a major-9 board")
    design = read(path)[0]
    text = write_board(design, target=9).text
    again = read_board(text)
    again = dataclasses.replace(again, header=dataclasses.replace(again.header, name=design.header.name))
    assert opaque_count(again) == opaque_count(design), item.id
    assert comparable(again) == comparable(design), f"{item.id}: the re-read model differs"


ROYALBLUE = "kicad-demo-10-0-6-pcb-13"


@pytest.mark.parametrize("item", [i for i in DEMOS if i.id == ROYALBLUE], ids=lambda i: i.id)
def test_teardrops_keep_the_stored_net_name(item: CorpusItem) -> None:
    """The four teardrops of the RoyalBlue board on nets stored with ``{slash}`` keep that spelling in
    both targets (c0163, the board that was refused)."""
    design = read(require(item))[0]
    for target in (9, 10):
        text = write_board(design, target=target).text
        assert "Net-(U1-P1.00/XL1)" not in text and "Net-(U1-P1.01/XL2)" not in text, target
    ten = write_board(design, target=10).text
    assert ten.count('(net "Net-(U1-P1.00{slash}XL1)")') >= 2
    assert ten.count('(net "Net-(U1-P1.01{slash}XL2)")') >= 2
