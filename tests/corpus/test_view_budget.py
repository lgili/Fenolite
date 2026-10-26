# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Scene budgets of the viewer on the largest public board (capability viewer-performance, change c0182).

The board of S-0187 (``altium-third-party-pcbdoc-08``, a heavy row) is read from the corpus cache. The
measured numbers of 2026-10-25 are in
``openspec/changes/archive/2026-10-25-c0182-viewer-performance/tasks.md``.
"""

from __future__ import annotations

import json
import time

import pytest
from _corpus import manifest_items, require

from fenolite.cli.cmd_view import scene_of
from fenolite.view.compact import compact, pack

pytestmark = pytest.mark.needs_corpus
BOARD = next(item for item in manifest_items("rta") if item.id == "altium-third-party-pcbdoc-08")
BUILD_SECONDS = 20.0
"""A loose bound for slow runners: the scene was built in 12.7 s before c0182 and about 7 s after."""


def _size(value: object) -> int:
    return len(json.dumps(value, separators=(",", ":")))


def test_scene_budget() -> None:
    path = require(BOARD)
    started = time.perf_counter()
    scene = scene_of(path)
    assert time.perf_counter() - started < BUILD_SECONDS
    small = compact(scene)
    assert _size(small["p1"]) <= _size(scene["prims"]) / 2
    assert len(pack(scene)) <= _size(scene) / 10
