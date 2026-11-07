# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite import --to python`` rebuilds two public PCB documents exactly (change c0426, capability
design-conversion, "Library made from a board"; capability design-dsl, "Via without a ring in a copper
table").

On ``origin/cac/lote-24`` 948b6a376 the emitted code of ``altium-third-party-pcbdoc-02`` did not build (a
via whose drill equals its diameter), and that of ``altium-third-party-pcbdoc-01`` rebuilt one pad 1 nm
off (a footprint variant whose file another footprint of the converted library overwrote). The test reads
codes and the equivalence verdict only: no name, coordinate or identifier of the documents.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import run

pytestmark = pytest.mark.needs_corpus
IDS = ("altium-third-party-pcbdoc-01", "altium-third-party-pcbdoc-02")
ITEMS = {item.id: item for item in manifest_items("altium-import") if item.id in IDS}
STAMP = "2026-11-05T00:00:00Z"


@pytest.mark.parametrize("item_id", IDS)
def test_the_emitted_code_rebuilds_the_document(item_id: str, tmp_path: Path) -> None:
    source = require(ITEMS[item_id])
    reply = run(
        "import", str(source), "--to", "python", "--out", "out", "--allow-lossy", "--dry-run", cwd=tmp_path,
        timestamp=STAMP,
    )  # fmt: skip
    issues = (reply.envelope or {}).get("issues", [])
    unequal = [issue["message"] for issue in issues if issue["code"] == "import.unequal"]
    assert unequal == [], unequal
    assert reply.exit_code == 0, reply.error
    assert reply.result["equivalence"]["equivalent"] is True
