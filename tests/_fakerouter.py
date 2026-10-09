# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Create a temporary KiCadRoutingTools-compatible checkout for isolated subprocess tests.

Environment read by the fake ``route.py``: ``FAKE_ROUTER_MODE`` (``append``, the default: one segment on
the first net of ``--nets``; ``drop``; ``fail``; ``sleep``), ``FAKE_ROUTER_RECORD`` (a JSON file that
receives the arguments and the folder of the last run), ``FAKE_ROUTER_RUNS`` (a file that receives one
JSON line per run: its arguments, its names of ``--nets``, the text of its input board (change c0109)
and the text of the rules file beside it (change c0107)),
``FAKE_ROUTER_SLEEP_NET`` and ``FAKE_ROUTER_FAIL_NET`` (the run whose ``--nets`` names that net sleeps
5 s, or exits 2 printing ``boom``). Change c0120 adds ``FAKE_ROUTER_FAIL_NETS`` (names separated by
commas: a run that names one of them fails), ``FAKE_ROUTER_STARTS`` (a file that gets one line per
process: its names of ``--nets``, joined by commas), ``FAKE_ROUTER_PID`` (a file that gets the process
id) and ``FAKE_ROUTER_SLEEP`` (the seconds of a sleep, 5 by default); in the append mode the segment of
each net lies on its own row.

Change c0110 writes the same fake as ``route_diff.py``, ``bga_fanout.py`` and ``qfn_fanout.py``: the
recorded runs then hold ``script``, the name of the script that ran. ``route_diff.py`` adds one segment on
each net of ``--nets``; the two escape scripts read the board of their first argument and write the one
after ``--output``, adding one stub on the first net of ``--nets`` (``escape`` in the track's row), and
exit 2 when ``FAKE_ESCAPE_FAIL`` names their ``--component``.
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
    script = textwrap.dedent(
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

            script = Path(sys.argv[0]).name
            escape = script in ("bga_fanout.py", "qfn_fanout.py")
            source = Path(sys.argv[1])
            output = Path(sys.argv[sys.argv.index("--output") + 1] if escape else sys.argv[2])
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
                    "script": script,
                    "argv": sys.argv[1:],
                    "nets": named,
                    "board": source.read_text(encoding="utf-8"),
                    "rules": rules,
                }
                with open(runs, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(entry) + "\\n")
            mode = os.environ.get("FAKE_ROUTER_MODE", "append")
            wanted = ",".join(named)
            starts = os.environ.get("FAKE_ROUTER_STARTS")
            if starts:
                with open(starts, "a", encoding="utf-8") as log:
                    log.write(wanted + "\\n")
            pid_file = os.environ.get("FAKE_ROUTER_PID")
            if pid_file:
                Path(pid_file).write_text(str(os.getpid()), encoding="utf-8")
            if mode == "sleep" or os.environ.get("FAKE_ROUTER_SLEEP_NET") in named:
                time.sleep(float(os.environ.get("FAKE_ROUTER_SLEEP", "5")))
            if escape and "--component" in sys.argv:
                part = sys.argv[sys.argv.index("--component") + 1]
                if part in os.environ.get("FAKE_ESCAPE_FAIL", "").split(","):
                    print("escape failed in fake", file=sys.stderr)
                    raise SystemExit(2)
            failing = [name for name in os.environ.get("FAKE_ROUTER_FAIL_NETS", "").split(",") if name]
            if os.environ.get("FAKE_ROUTER_FAIL_NET") in named or any(name in named for name in failing):
                mode = "fail"
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
                nets = design.circuit.nets
                chosen = [n for n in nets if n.name in named]
                if script != "route_diff.py":
                    chosen = [n for n in nets if n.name in named[:1]][:1]
                if not chosen:
                    chosen = [next((n for n in nets if n.name in sys.argv), nets[0])]
                for net in chosen:
                    row = 100_000 * (1 + nets.index(net))  # one track per net, each its own (c0120)
                    seed = zlib.crc32((script + net.name).encode("utf-8"))
                    x = 300_000 if escape else 100_000
                    track = Track(
                        id=new_id("trk", random.Random(seed)),
                        start=Point(x, row), end=Point(x + 100_000, row + 100_000),
                        width=250_000, layer="F.Cu", net_id=net.id,
                    )
                    board = dataclasses.replace(board, tracks=(*board.tracks, track))
            output.write_text(write_board(dataclasses.replace(design, board=board), target=10).text)
            """
    )
    for name in ("route.py", "route_diff.py", "bga_fanout.py", "qfn_fanout.py"):
        (route_dir / name).write_text(script, encoding="utf-8")
    return checkout
