# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored placed project for c0365's reviewed and oracle acceptance proofs."""

import contextlib
import io
import json
import sys
from pathlib import Path
from typing import Any

from fenolite.cli.main import main

ROLES_TESTS = Path(__file__).resolve().parent / "unit" / "roles"
if str(ROLES_TESTS) not in sys.path:
    sys.path.insert(0, str(ROLES_TESTS))
from _critical import bench  # noqa: E402

SEARCH = (
    "--router-option",
    "search=only",
    "--router-option",
    "search-grid=0.5mm",
    "--router-option",
    "search-max-states=50000",
    "--router-option",
    "search-max-vias=0",
    "--router-option",
    "max-length=60mm",
)


def cli(*words: str) -> tuple[int, dict[str, Any], str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([*words, "--json"])
    return code, json.loads(out.getvalue() or "{}"), err.getvalue()


def project(folder: Path, layers: int, *, bottom: bool = False, extra: str = ""):
    return bench(
        folder,
        "search_maze",
        f"""
from fenolite.dsl import Design, Net, Part, connect, mm

design=Design("search_maze")
design.board(mm(24),mm(20),copper={layers})
a=Part("R1","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k")
b=Part("R2","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k")
c=Part("R3","Fenolite:Resistor",footprint="Fenolite:Chip_0603",value="1k")
design.add(a,b,c)
sig,fence=Net("SIG"),Net("FENCE")
connect(sig,a[1],b[1])
connect(fence,c[1],c[2])
design.rules.netclass("SIGNAL",clearance=mm("0.2"),track_width=mm("0.25"),
                      via_diameter=mm("0.6"),via_drill=mm("0.3"),nets=(sig,fence))
a.place(mm(4),mm(10),rot=90)
b.place(mm(20),mm(10),rot=90,side="{"bottom" if bottom else "top"}")
c.place(mm(22),mm(16))
design.track("wall_a",(mm(8),mm(1)),(mm(8),mm(12)),width=mm("0.25"),net=fence)
design.track("wall_b",(mm(16),mm(8)),(mm(16),mm(19)),width=mm("0.25"),net=fence)
{extra}
""",
    )
