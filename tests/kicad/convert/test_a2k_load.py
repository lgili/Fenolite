# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad loading and DRC of converted public Altium boards (c0161 task 4.1)."""

from __future__ import annotations

import _a2kcases
import pytest
from _corpus import manifest_items, require
from _probes import runner

pytestmark = pytest.mark.needs_kicad


def test_sample_load() -> None:
    assert _a2kcases.load(_a2kcases.SAMPLE, runner())


@pytest.mark.needs_corpus
@pytest.mark.slow
@pytest.mark.parametrize("item", [i for i in manifest_items("rta") if "-pcbdoc-" in i.id], ids=lambda i: i.id)
def test_public_load(item) -> None:
    assert _a2kcases.load(require(item), runner())
