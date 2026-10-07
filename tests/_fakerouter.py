# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Create a temporary KiCadRoutingTools-compatible checkout for isolated subprocess tests.

Environment read by the fake ``route.py``: ``FAKE_ROUTER_MODE`` (``append``, the default: one segment on
the first net of ``--nets``; ``drop``; ``fail``; ``sleep``), ``FAKE_ROUTER_RECORD`` (a JSON file that
receives the arguments and the folder of the last run), ``FAKE_ROUTER_RUNS`` (a file that receives one
JSON line per run: its arguments, its names of ``--nets``, the text of its input board (change c0109)
and the text of the rules file beside it (change c0107)),
``FAKE_ROUTER_SLEEP_NET`` and ``FAKE_ROUTER_FAIL_NET`` (the run whose ``--nets`` names that net sleeps
5 s, or exits 2 printing ``boom``).
"""

from __future__ import annotations

import textwrap
from pathlib import Path


def create_fake_router(folder: Path, *, version: str = "0.22.1") -> Path:
    """Create a fake router whose modes are controlled by the environment (see the module text)."""
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
            import zlib
            from pathlib import Path
            sys.path.insert(0, os.environ["FENOLITE_TEST_SOURCE"])
            from fenolite.backends.kicad.pcb import read_board, write_board
            from fenolite.core.coords import Point
            from fenolite.core.ids import new_id
            from fenolite.model.board import Track

            source, output = Path(sys.argv[1]), Path(sys.argv[2])
            named = []
            if "--nets" in sys.argv:
                for word in sys.argv[sys.argv.index("--nets") + 1:]:
                    if word.startswith("--"):
                        break
                    named.append(word)
            record = os.environ.get("FAKE_ROUTER_RECORD")
            if record:
                Path(record).write_text(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd()}))
            runs = os.environ.get("FAKE_ROUTER_RUNS")
            if runs:
                beside = source.with_suffix(".kicad_dru")
                rules = beside.read_text(encoding="utf-8") if beside.is_file() else ""
                entry = {
                    "argv": sys.argv[1:],
                    "nets": named,
                    "board": source.read_text(encoding="utf-8"),
                    "rules": rules,
                }
                with open(runs, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(entry) + "\\n")
            mode = os.environ.get("FAKE_ROUTER_MODE", "append")
            if mode == "sleep" or os.environ.get("FAKE_ROUTER_SLEEP_NET") in named:
                time.sleep(5)
            if mode == "fail" or os.environ.get("FAKE_ROUTER_FAIL_NET") in named:
                print("boom from fake router", file=sys.stderr)
                raise SystemExit(2)
            design = read_board(source.read_text(encoding="utf-8"), file=source.name)
            if design.board is None:
                raise SystemExit(3)
            board = design.board
            if mode == "drop" and board.tracks:
                board = dataclasses.replace(board, tracks=board.tracks[1:])
            elif mode == "append":
                nets = design.circuit.nets
                net = next((n for n in nets if n.name in named[:1]), None)
                net = net or next((n for n in nets if n.name in sys.argv), nets[0])
                track = Track(
                    id=new_id("trk", random.Random(zlib.crc32(net.name.encode("utf-8")))),
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
