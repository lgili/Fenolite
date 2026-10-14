# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent export/ ERC of generated schematics (c0161 task 4.3)."""

from __future__ import annotations

import _a2kcases
import pytest
from _altium_sets import SETS, lay_out
from _probes import runner

pytestmark = pytest.mark.needs_kicad


def test_sample_schematic() -> None:
    assert not _a2kcases.schematic(_a2kcases.SAMPLE, runner())


@pytest.mark.needs_corpus
@pytest.mark.slow
@pytest.mark.parametrize("name", list(SETS))
def test_public_schematic(name, tmp_path) -> None:
    folder = lay_out(SETS[name], tmp_path / name)
    project = next(folder.rglob("*.PrjPcb"))
    assert not _a2kcases.schematic(project, runner())
