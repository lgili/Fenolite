# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board filter of the viewer page (capability review-panels, scenario "Parts of a footprint on the
bottom"; change c0187). The page's own query functions run in Node on a scene authored here."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

import pytest

from fenolite.view.export import template

L = ["F.Cu", "s", [0, 0, 1000, 0, 200], 0, -1, ""]
SCENE: dict[str, Any] = {
    "layers": [
        {"id": "F.Cu", "name": "Top Layer", "side": "top"},
        {"id": "B.Cu", "name": "Bottom Layer", "side": "bottom"},
    ],
    "nets": ["GND", "VCC", "SDA"],
    "comps": [
        {"ref": "R1", "value": "10k", "footprint": "R_0402", "side": "top", "params": {"Tolerance": "1%"}},
        {"ref": "R2", "value": "4k7", "footprint": "R_0402", "side": "top", "params": {}},
        {"ref": "C7", "value": "100n", "footprint": "C_0402", "side": "bottom", "params": {}},
        {"ref": "U1", "value": "MCU", "footprint": "QFN-32", "side": "top", "params": {}},
    ],
    "prims": [
        ["F.Cu", "p", [0], 0, 0, "R1-1"],
        ["F.Cu", "p", [1], 1, 0, "R1-2"],
        ["F.Cu", "p", [2], 0, 1, "R2-1"],
        ["B.Cu", "p", [3], 0, 2, "C7-1"],
        ["B.Cu", "p", [4], 1, 2, "C7-2"],
        ["F.Cu", "p", [5], 2, 3, "U1-1"],
        L,
        ["B.Cu", "s", [0, 0, 1, 1, 200], 0, -1, ""],
    ],
}


def _run(queries: list[str]) -> list[dict[str, Any]]:
    html = template()
    start, end = html.index("// ---- query (c0187)"), html.index("// ---- end query")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the query functions are not run")
    script = html[start:end] + (
        f"const sc = {json.dumps(SCENE)}; const out = [];"
        f"for (const text of {json.dumps(queries)}) {{ const r = queryRun(sc, queryParse(text));"
        "out.push({ comps: r.comps.map(i => sc.comps[i].ref),"
        " prims: sc.prims.filter(p => r.prims.has(p)).length }); }"
        "out.push({ similar: [similarQuery(sc, null, 0), similarQuery(sc, sc.prims[7], -1)] });"
        "console.log(JSON.stringify(out));"
    )
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def test_parts_of_a_footprint_on_the_bottom() -> None:
    """Scenario "Parts of a footprint on the bottom"."""
    (found, _similar) = _run(["footprint:*0402* side:bottom"])
    assert found == {"comps": ["C7"], "prims": 2}


def test_query_forms() -> None:
    *found, similar = _run(
        [
            "net:GND",
            "ref:R* -value:4k7",
            "ref:U1 | ref:C?",
            'layer:"Bottom Layer"',
            "tolerance:1%",
            "VCC",
            "nope:x",
        ]
    )
    assert found[0] == {
        "comps": ["R1", "R2", "C7"],
        "prims": 5,
    }  # parts with a pad on the net, and two tracks
    assert found[1]["comps"] == ["R1"]
    assert found[2]["comps"] == ["C7", "U1"]
    assert found[3] == {"comps": ["C7"], "prims": 3}
    assert found[4] == {"comps": ["R1"], "prims": 2}
    assert found[5]["comps"] == ["R1", "C7"]  # a bare value: a reference or a net
    assert found[6] == {"comps": [], "prims": 0}
    assert similar["similar"] == ['footprint:"R_0402" value:"10k"', 'net:"GND" layer:"Bottom Layer"']
