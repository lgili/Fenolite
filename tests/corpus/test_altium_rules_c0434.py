# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A public PCB document converted to KiCad and back to Altium keeps every rule, and the refusal without
``--allow-lossy`` lists every loss (change c0434, capability altium-pcb-writer, "Rule lowering table";
capability design-conversion, "Exit 7 without consent").

On ``origin/cac/lote-24`` 2ca60daf4 the way back wrote 4 of the 8 rules of ``altium-third-party-pcbdoc-01``
(S-1931), and its refusal named the refused kinds only. The test reads codes, kinds and counts: no name,
coordinate or identifier of the document.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import run

pytestmark = pytest.mark.needs_corpus
ITEM = next(item for item in manifest_items("altium-import") if item.id == "altium-third-party-pcbdoc-01")
STAMP = "2026-11-06T00:00:00Z"


def _kicad_project(tmp_path: Path) -> Path:
    source = require(ITEM)
    planned = run("convert", str(source), "--to", "kicad", "--out", "k", "--allow-lossy", "--dry-run",
                  cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert planned.exit_code == 0, planned.error
    plan = str(planned.result["plan_id"])
    written = run("convert", str(source), "--to", "kicad", "--out", "k", "--allow-lossy", "--confirm",
                  "--plan", plan, cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert written.exit_code == 0, written.error
    return next((tmp_path / "k").rglob("*.kicad_pro"))


def test_the_rules_come_back_and_the_refusal_lists_every_loss(tmp_path: Path) -> None:
    project = _kicad_project(tmp_path)
    refused = run("convert", str(project), "--to", "altium", "--out", "a", "--dry-run", cwd=tmp_path,
                  timestamp=STAMP)  # fmt: skip
    assert refused.exit_code == 7 and refused.error is not None and refused.error["code"] == "FEN-7001"
    lossy = [
        issue["where"]
        for issue in (refused.envelope or {}).get("issues", [])
        if issue["code"] == "convert.lossy"
    ]
    consented = run("convert", str(project), "--to", "altium", "--out", "a", "--allow-lossy", "--dry-run",
                    cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert consented.exit_code == 0, consented.error
    rows = consented.result["report"]["rows"]
    assert lossy == [row["kind"] for row in rows if row["lost"]]
    assert len(lossy) > len(consented.result["report"]["refused"])
    assert "--allow-lossy also loses items of" in refused.error["message"]
    (rule,) = [row for row in rows if row["kind"] == "rule"]
    assert (rule["source"], rule["written"], rule["lost"]) == (8, 8, 0)
    assert rule["changed"] == 3
