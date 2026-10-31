# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad 10.0.6 demo boards imported as code (change c0275, task 4.3; ``H-G-IMPORT-CODE``).

Each demo board of the corpus with an allow-listed licence is imported with ``--allow-lossy`` into the
test's temporary folder (nothing converted is kept, corpus-policy "Converted code stays out of the tool
repository"); the import builds the emitted code and compares it with the board at levels 1 to 5 and copper
item by item. Every board must come through equivalent, and the kinds it leaves out must equal its row of
the table in ``docs/evidence/import-corpus.md``. The corpus holds the boards without their project files,
so each is read alone.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import run

pytestmark = pytest.mark.needs_corpus
ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "docs" / "evidence" / "import-corpus.md"
PREFIX = "kicad-demo-10-0-6-pcb-"
ALLOWED = ("CC-BY-SA-4.0", "CC-BY-4.0", "CC0-1.0", "CERN-OHL-S-2.0", "CERN-OHL-W-2.0", "CERN-OHL-P-2.0")
"""Licences under which an import of a board may be published; the corpus measurement takes only those."""
BEGIN, END = "<!-- import-corpus:begin -->", "<!-- import-corpus:end -->"
ITEMS = [item for item in manifest_items("rt0") if item.id.startswith(PREFIX) and item.license in ALLOWED]


def recorded() -> dict[str, str]:
    """Row number → the ``kind count`` list of the page's table, as written."""
    text = PAGE.read_text(encoding="utf-8")
    body = text.split(BEGIN, 1)[1].split(END, 1)[0]
    rows: dict[str, str] = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"\d\d", cells[0]):
            rows[cells[0]] = cells[2]
    return rows


def shown(unexpressed: list[dict[str, object]]) -> str:
    return ", ".join(f"{row['kind']} {row['count']}" for row in unexpressed) or "none"


@pytest.mark.parametrize("item", ITEMS, ids=[item.id.removeprefix(PREFIX) for item in ITEMS])
def test_demo_board_imports_equivalent(item: object, tmp_path: Path) -> None:
    board = require(item)  # type: ignore[arg-type]
    folder = tmp_path / "src"
    folder.mkdir()
    copy = folder / board.name.replace(" ", "_")
    shutil.copy(board, copy)
    started = time.monotonic()
    reply = run(
        "import", str(copy), "--to", "python", "--out", "out", "--allow-lossy", "--dry-run",
        cwd=tmp_path, timestamp="2026-10-30T00:00:00Z",
    )  # fmt: skip
    measurement = {
        "row": item.id.removeprefix(PREFIX),  # type: ignore[attr-defined]
        "board": board.name,
        "left_out": shown(reply.result.get("unexpressed", [])),
        "counts": reply.result.get("counts", {}),
        "exit_code": reply.exit_code,
        "equivalent": reply.result.get("equivalence", {}).get("equivalent"),
        "seconds": round(time.monotonic() - started),
    }
    report = json.dumps(measurement, sort_keys=True)
    (tmp_path / "import-census.json").write_text(report + "\n", encoding="utf-8")
    print("IMPORT_CENSUS " + report)
    errors = [issue for issue in (reply.envelope or {}).get("issues", []) if issue["severity"] == "error"]
    assert reply.exit_code == 0, (reply.error, errors)
    assert reply.result["equivalence"]["equivalent"] is True
    row = item.id.removeprefix(PREFIX)  # type: ignore[attr-defined]
    assert recorded().get(row) == shown(reply.result["unexpressed"]), row
