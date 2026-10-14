# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Agreement with the independent KiCad importer (c0161 task 4.2)."""

from __future__ import annotations

import _a2kcases
import pytest
from _corpus import manifest_items, require
from _probes import runner

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_sample_import() -> None:
    assert not _a2kcases.imported(_a2kcases.SAMPLE_BOARD, runner())


@pytest.mark.needs_corpus
@pytest.mark.slow
@pytest.mark.parametrize("item", [i for i in manifest_items("rta") if "-pcbdoc-" in i.id], ids=lambda i: i.id)
def test_public_import(item) -> None:
    assert not _a2kcases.imported(require(item), runner())
