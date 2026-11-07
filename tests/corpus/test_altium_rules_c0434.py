# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A public PCB document converted to KiCad and back to Altium writes every rule record its source holds, as
it was read, and no other (change c0434; capabilities altium-pcb-writer, "Source rule records written back",
and design-conversion, "Rule records through KiCad").

On ``origin/cac/lote-26`` e55b7cd5e the way back of ``altium-third-party-pcbdoc-08`` (a heavy row,
``FENOLITE_HEAVY=1``) wrote 18 Clearance, 15 Width and 15 Routing Via Style records where the source holds
4, 1 and 3 (S-1931). The extra records came from the 14 net classes of the KiCad project, which hold KiCad's
defaults, and from Fenolite's ``All`` defaults; the records KiCad has no rule for were lost. The test
compares the records' keys and values; it prints none.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _corpus import manifest_items, require

from fenolite.api import run
from fenolite.backends.altium.read.pcb import read_pcbdoc

pytestmark = pytest.mark.needs_corpus
ITEM = next(item for item in manifest_items("altium-import") if item.id.endswith("-pcbdoc-08"))
STAMP = "2026-11-06T00:00:00Z"


def _convert(source: Path, to: str, out: str, cwd: Path, *extra: str) -> Mapping[str, Any]:
    args = ("convert", str(source), "--to", to, "--out", out, "--allow-lossy", *extra)
    planned = run(*args, "--dry-run", cwd=cwd, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    written = run(*args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=cwd, timestamp=STAMP)
    assert written.exit_code == 0, written.error
    return written.result


def _records(path: Path) -> list[tuple[int, tuple[tuple[str, str | None], ...]]]:
    """Each rule record: its kind number and its keys from ``RULEKIND`` on (``UNIQUEID`` included)."""
    found: list[tuple[int, tuple[tuple[str, str | None], ...]]] = []
    for rule in read_pcbdoc(path.read_bytes()).rules:
        fields = tuple(rule.record.fields)
        start = [key for key, _value in fields].index("RULEKIND")
        found.append((rule.kind_number, fields[start:]))
    return found


def test_the_way_back_writes_every_rule_record_as_it_was_read(tmp_path: Path) -> None:
    source = require(ITEM)
    _convert(source, "kicad", "k", tmp_path)
    result = _convert(next((tmp_path / "k").rglob("*.kicad_pro")), "altium", "a", tmp_path, "--altium-pour",
                      "outline")  # fmt: skip
    before = _records(source)
    after = _records(next((tmp_path / "a").rglob("*.PcbDoc")))
    assert len(before) == 56
    assert after == before
    rows = {row["kind"]: row for row in result["report"]["rows"]}
    assert rows["rule"]["written"] == rows["rule"]["source"] and rows["rule"]["lost"] == 0
    assert (rows["netclass"]["source"], rows["netclass"]["changed"], rows["netclass"]["lost"]) == (14, 14, 0)
