# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored proposal overlays on Fenolite's own small board, for viewer interaction tests."""

import hashlib
import json
from pathlib import Path

from _visual import DATA, export

from fenolite.cli.cmd_view import scene_of

CANDIDATE = "c-" + "1" * 16
OTHER = "c-" + "2" * 16
PROPOSAL = "p-" + "a" * 16
BUNDLE = "b-" + "a" * 16
PAYLOAD = '</script><img src=x onerror="window.__proposalInjected=true">'


def proposal_page(folder: Path, *, bundle: bool = False) -> Path:
    board = DATA / "kicad" / "board" / "two_layer.kicad_pcb"
    scene = scene_of(board)
    x0, y0, x1, y1 = scene["bounds"]
    width, height = x1 - x0, y1 - y0
    start = [x0 + width // 4, y0 + height // 2]
    end = [x0 + width * 3 // 4, start[1]]
    middle = [(start[0] + end[0]) // 2, start[1]]
    bent = [middle[0], start[1] + height // 6]
    net = next(name for name in scene["nets"] if name)

    def nm(point):
        return [int(value) * 1000 for value in point]

    def track(points):
        return {"kind": "track", "layer": "F.Cu", "width": 250_000, "points": [nm(p) for p in points]}

    def ends(a, b):
        return [
            {"kind": "pad", "name": "A-1", "layers": ["F.Cu"], "at": nm(a)},
            {"kind": "pad", "name": "B-1", "layers": ["F.Cu"], "at": nm(b)},
        ]

    reply = {
        "command": "route",
        "input": {"path": board.name, "sha256": hashlib.sha256(board.read_bytes()).hexdigest()},
        "evidence": {"level": "UNVERIFIED"},
        "result": {
            "mode": "propose",
            "order": "generation",
            "controls": {"schema": "fenolite.proposal_controls.v0", "portable": True},
            "locked": [],
            "proposals": [
                {
                    "id": PROPOSAL,
                    "kind": "connection",
                    "net": net,
                    "subject": "connection:AUTHORED:A~B",
                    "ends": ends(start, end),
                    "candidates": [
                        {
                            "id": CANDIDATE,
                            "source": "shape",
                            "facts": {"length": None, "vias": 1},
                            "geometry": [
                                track((start, end)),
                                {
                                    "kind": "via",
                                    "at": nm(middle),
                                    "diameter": 600_000,
                                    "drill": 300_000,
                                    "layers": ["F.Cu", "B.Cu"],
                                },
                            ],
                        },
                        {
                            "id": OTHER,
                            "source": PAYLOAD,
                            "relaxed": ["authored relaxation"],
                            "facts": {},
                            "geometry": [track((start, bent, end))],
                        },
                    ],
                },
                {
                    "id": "p-" + "b" * 16,
                    "kind": "connection",
                    "net": "UNRESOLVED",
                    "subject": "unresolved:AUTHORED",
                    "reason": PAYLOAD,
                    "ends": ends([start[0], start[1] + height // 4], [end[0], end[1] + height // 4]),
                    "candidates": [],
                },
            ],
        },
    }
    if bundle:
        result = reply["result"]
        first = result["proposals"][0]
        second = {**first, "id": "p-" + "c" * 16, "subject": "connection:AUTHORED:C~D"}
        second["candidates"] = [first["candidates"].pop()]
        second["candidates"][0]["source"] = "search"
        result["proposals"].insert(1, second)
        for row in (first, second):
            row["candidates"][0]["bundle"] = BUNDLE
        result["bundles"] = [
            {
                "id": BUNDLE,
                "fingerprint": "f" * 64,
                "members": [CANDIDATE, OTHER],
                "subjects": [first["subject"], second["subject"]],
            }
        ]
        result["controls"]["router_options"] = ["negotiate=on"]
    path = folder / "proposals.json"
    path.write_text(json.dumps(reply), encoding="utf-8")
    return export(board, folder / "proposals.html", "--proposals", str(path), "--no-models", "--no-review")
