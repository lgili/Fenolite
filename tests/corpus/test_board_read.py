# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every corpus board reads (capability kicad-file-backend, requirement "Board reading evidence"; c0009).

Items are named by their neutral manifest id only.
"""

from __future__ import annotations

import pytest
from _boardcorpus import MALFORMED_ITEMS, OLD_ITEMS, READABLE_ITEMS, read, readable
from _corpus import CorpusItem, require

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.versions import UnsupportedFormatError
from fenolite.core.errors import FormatError

pytestmark = pytest.mark.needs_corpus


@pytest.mark.parametrize("item", READABLE_ITEMS, ids=lambda i: i.id)
def test_board_reads(item: CorpusItem) -> None:
    path = require(item)
    assert readable(item), f"{item.id}: expected an 8.0 or newer board"
    design, issues = read(path)
    errors = [f"{i.code} at {i.where}: {i.message}" for i in issues if i.severity == "error"]
    assert not errors, f"{item.id}: " + "; ".join(errors)
    assert design.board is not None and design.board.layers, item.id


@pytest.mark.parametrize("item", OLD_ITEMS, ids=lambda i: i.id)
def test_old_boards_refused_with_upgrade_hint(item: CorpusItem) -> None:
    path = require(item)
    with pytest.raises(UnsupportedFormatError) as info:
        read_board(path)
    assert "pcb upgrade" in info.value.hint


@pytest.mark.parametrize("item", MALFORMED_ITEMS, ids=lambda i: i.id)
def test_malformed_board_raises(item: CorpusItem) -> None:
    if not item.path.is_file():
        pytest.skip(f"{item.id} not cached (fetch with --uses malformed)")
    with pytest.raises(FormatError):
        read_board(item.path)
