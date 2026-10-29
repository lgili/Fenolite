# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Prepare the authored first-use project and exported viewer pages for c0208 media.

Run from the repository root: uv run python tools/marketing/prepare.py
All writes use the released CLI's reviewed plan. No CAD verification or external routing runs.
The capabilities command may probe the versions of installed external tools.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("build/presentation")


def command(*args: str) -> dict:
    done = subprocess.run(
        [sys.executable, "-m", "fenolite", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        raise RuntimeError(f"fenolite {' '.join(args)}: {done.stderr or done.stdout}")
    return json.loads(done.stdout)


def write(*args: str) -> dict:
    plan = command(*args, "--dry-run")["result"]["plan_id"]
    return command(*args, "--confirm", "--plan", plan)


def main() -> None:
    folder = ROOT / OUT
    if folder.exists():
        raise SystemExit("build/presentation already exists; keep it or move it before regenerating")
    command("capabilities", "--brief")
    project = OUT / "blink"
    write("init", str(project))
    write("build", str(project / "design.py"), "--out", str(project / "build"))
    write("route", str(project / "build"), "--router", "direct")
    write(
        "view",
        str(project / "build"),
        "--doc",
        "blink.kicad_pcb",
        "--export",
        str(OUT / "blink.html"),
        "--cache",
        "off",
    )
    write("build", "examples/blink_routed/design.py", "--out", str(OUT / "routed"))
    write(
        "view",
        str(OUT / "routed"),
        "--doc",
        "blink_routed.kicad_pcb",
        "--export",
        str(OUT / "routed.html"),
        "--cache",
        "off",
    )
    # The released, authored Altium sample demonstrates cross-probing between documents.
    write(
        "view",
        "tests/data/altium/blink/blink.PrjPcb",
        "--doc",
        "blink.PcbDoc",
        "--export",
        str(OUT / "altium.html"),
        "--cache",
        "off",
    )
    print("Prepared build/presentation: blink, routed and their exported pages, plus altium.html")


if __name__ == "__main__":
    main()
