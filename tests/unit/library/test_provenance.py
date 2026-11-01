# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``PROVENANCE.json`` (capability fenolite-library, "Provenance record"; change c0279)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fenolite.library.items import canonical_json, read_item
from fenolite.library.provenance import provenance_problems, step_problems

DEMO = Path(__file__).resolve().parents[2] / "data" / "library_repo" / "demo"
BOARD = DEMO / "boards" / "cern-ohl-s" / "demo-src" / "blink"


def _board() -> dict[str, Any]:
    return json.loads((BOARD / "PROVENANCE.json").read_text(encoding="utf-8"))


def test_every_demo_record_is_valid_and_canonical() -> None:
    for path in sorted(DEMO.rglob("PROVENANCE.json")):
        data = path.read_bytes()
        record = json.loads(data)
        item = read_item((path.parent / "item.json").read_bytes())
        assert provenance_problems(record, item) == [], path
        assert canonical_json(record) == data, path


def test_converted_needs_a_commit() -> None:
    record = _board()
    record["upstream"]["commit"] = "main"
    assert any(p.startswith("upstream.commit") for p in provenance_problems(record))


def test_disagreement_names_both_values() -> None:
    record = _board()
    item = read_item((BOARD / "item.json").read_bytes())
    record["spdx"] = "MIT"
    found = [p for p in provenance_problems(record, item) if p.startswith("spdx:")]
    assert found and "'MIT'" in found[0] and "'CERN-OHL-S-2.0'" in found[0]


def test_board_needs_fidelity_and_import() -> None:
    record = _board()
    del record["fidelity"], record["import"]
    problems = provenance_problems(record)
    assert any(p.startswith("fidelity") for p in problems) and any(p.startswith("import") for p in problems)


def test_steps_refuse_other_tools_and_plan_ids() -> None:
    steps = [
        {"tool": "sh", "argv": ["-c", "true"]},
        {"tool": "fenolite", "argv": ["import", "--confirm", "--plan", "0123456789abcdef"]},
    ]
    problems = step_problems(steps)
    assert "conversion.steps[1]" in problems[0] and "'sh'" in problems[0]
    assert "conversion.steps[2]" in problems[1] and "--plan" in problems[1]
    assert step_problems([{"tool": "fenolite", "argv": ["import", "--confirm"]}]) == []
