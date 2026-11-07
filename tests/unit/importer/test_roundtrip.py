# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Round trips of the authored examples (change c0275): an example is built, its board imported, and the
emitted code built again by the import's self-check; the two boards are equal at levels 1 to 5 and copper
item by item, and nothing is left out."""

from __future__ import annotations

from pathlib import Path

import pytest
from _importcode import ROOT, STAMP, imported

from fenolite.api import run

EXAMPLES = (
    ("blink_routed/design.py", "blink_routed"),
    ("board_40parts/design.py", "board_40parts"),
    ("roles/half_bridge/good.py", "half_bridge_good"),
    ("roles/buck_shunt/good.py", "buck_shunt_good"),
    ("roles/bms/good.py", "bms_good"),
)


@pytest.mark.parametrize(("script", "name"), EXAMPLES, ids=[name for _, name in EXAMPLES])
def test_example_round_trip(tmp_path: Path, script: str, name: str) -> None:
    built = run(
        "build", str(ROOT / "examples" / script), "--out", "built", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert built.exit_code == 0, built.error
    reply = imported(tmp_path, tmp_path / "built" / f"{name}.kicad_pro", "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    assert reply.result["equivalence"] == {"levels": [1, 2, 3, 4, 5], "equivalent": True}
    again = run("build", "design.py", "--out", "again", "--confirm", cwd=tmp_path / "out", timestamp=STAMP)
    assert again.exit_code == 0, again.error
