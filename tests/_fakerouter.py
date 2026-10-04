# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Create a temporary KiCadRoutingTools-compatible checkout for isolated subprocess tests."""

from __future__ import annotations

import textwrap
from pathlib import Path


def create_fake_router(folder: Path, *, version: str = "0.22.1") -> Path:
    """Create a fake router with append, drop, fail and sleep modes controlled by environment."""
    checkout = folder / "fake-krt"
    route_dir = checkout / "py_router"
    binary_dir = checkout / "rust_router"
    route_dir.mkdir(parents=True)
    binary_dir.mkdir()
    (checkout / "VERSION").write_text(version + "\n", encoding="utf-8")
    (binary_dir / "grid_router.so").write_bytes(b"fake")
    (route_dir / "route.py").write_text(
        textwrap.dedent(
            """\
            import dataclasses
            import json
            import os
            import random
            import sys
            import time
            from pathlib import Path
            sys.path.insert(0, os.environ["FENOLITE_TEST_SOURCE"])
            from fenolite.backends.kicad.pcb import read_board, write_board
            from fenolite.core.coords import Point
            from fenolite.core.ids import new_id
            from fenolite.model.board import Track

            source, output = Path(sys.argv[1]), Path(sys.argv[2])
            record = os.environ.get("FAKE_ROUTER_RECORD")
            if record:
                Path(record).write_text(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}))
            mode = os.environ.get("FAKE_ROUTER_MODE", "append")
            if mode == "sleep":
                time.sleep(5)
            if mode == "fail":
                print("boom from fake router", file=sys.stderr)
                raise SystemExit(2)
            design = read_board(source.read_text(encoding="utf-8"), file=source.name)
            if design.board is None:
                raise SystemExit(3)
            board = design.board
            if mode == "drop" and board.tracks:
                board = dataclasses.replace(board, tracks=board.tracks[1:])
            elif mode == "append":
                net = next((n for n in design.circuit.nets if n.name in sys.argv), design.circuit.nets[0])
                track = Track(
                    id=new_id("trk", random.Random(1)),
                    start=Point(100_000, 100_000), end=Point(200_000, 200_000),
                    width=250_000, layer="F.Cu", net_id=net.id,
                )
                board = dataclasses.replace(board, tracks=(*board.tracks, track))
            output.write_text(write_board(dataclasses.replace(design, board=board), target=10).text)
            """
        ),
        encoding="utf-8",
    )
    return checkout
