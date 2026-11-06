# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A public PCB document converted to KiCad and back to Altium writes only the rules its source holds (change
c0434, capability altium-pcb-writer, "Design rule records").

On ``origin/cac/lote-26`` e55b7cd5e the way back of ``altium-third-party-pcbdoc-08`` (a heavy row,
``FENOLITE_HEAVY=1``) wrote 18 Clearance, 15 Width and 15 Routing Via Style records where the source holds
4, 1 and 3 (S-1931). The extra records came from the 14 net classes of the KiCad project, which hold KiCad's
defaults, and from Fenolite's ``All`` defaults. The test reads kinds, counts and limits: no name, coordinate
or identifier of the document.
"""

from __future__ import annotations

from collections import Counter
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
LIMITS = ("MINLIMIT", "MAXLIMIT", "PREFEREDWIDTH")


def _convert(source: Path, to: str, out: str, cwd: Path, *extra: str) -> Mapping[str, Any]:
    args = ("convert", str(source), "--to", to, "--out", out, "--allow-lossy", *extra)
    planned = run(*args, "--dry-run", cwd=cwd, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    written = run(*args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=cwd, timestamp=STAMP)
    assert written.exit_code == 0, written.error
    return written.result


def _records(path: Path) -> list[tuple[str | None, str, str, dict[str, str]]]:
    document = read_pcbdoc(path.read_bytes())
    return [
        (
            rule.rule_kind,
            rule.record.get("SCOPE1EXPRESSION") or "",
            rule.record.get("SCOPE2EXPRESSION") or "",
            {key: value for key, value in rule.record.fields if key in LIMITS},
        )
        for rule in document.rules
    ]


def test_the_way_back_writes_only_the_rules_of_the_source(tmp_path: Path) -> None:
    source = require(ITEM)
    _convert(source, "kicad", "k", tmp_path)
    result = _convert(next((tmp_path / "k").rglob("*.kicad_pro")), "altium", "a", tmp_path, "--altium-pour",
                      "outline")  # fmt: skip
    before = _records(source)
    after = _records(next((tmp_path / "a").rglob("*.PcbDoc")))
    counts, written = Counter(r[0] for r in before), Counter(r[0] for r in after)
    assert all(written[kind] <= counts[kind] for kind in written), (written, counts)
    assert not [r for r in after if r[1].startswith("InNetClass(")]
    assert [r for r in after if r[0] == "Width"] == [r for r in before if r[0] == "Width"]
    assert (written["Clearance"], written["Width"]) == (counts["Clearance"], counts["Width"]) == (4, 1)
    rows = {row["kind"]: row for row in result["report"]["rows"]}
    assert (rows["rule"]["source"], rows["rule"]["written"], rows["rule"]["lost"]) == (8, 7, 1)
    assert (rows["netclass"]["source"], rows["netclass"]["changed"], rows["netclass"]["lost"]) == (14, 14, 0)
