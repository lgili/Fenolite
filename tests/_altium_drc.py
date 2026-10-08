# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Planted faults for the light DRC of Altium input (change c0088): the routed blink of ``tests/_routed.py``
with one more copper intent in its script, built for Altium by ``fenolite build`` itself.

No record of a PCB document is edited: the fault is in the script, and the build writes it (with
``--copper-check warn``, because the copper guard refuses a short otherwise). Everything is authored for
Fenolite."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

from _routed import NAME, Routed

import fenolite.cli.main as cli_main

ANCHOR = "# Stitching vias every 5 mm"
CROSSING = (
    'design.track("cross", r1.pad(2), (mm(36), mm(5)), (mm(20), mm(5)), (mm(20), mm(8)), width=mm(0.3))\n'
)
"""A track of LED_A that crosses the LED_DRV track along y = 7 mm on F.Cu: one short."""
NEAR = 'design.track("near", r1.pad(2), (mm(36), mm(7.4)), (mm(31.65), mm(7.4)), width=mm(0.3))\n'
"""A track of LED_A whose end is 0.15 mm from the edge of the LED_DRV track that comes down to R1 pad 1 at
x = 31.2 mm (both 0.3 mm wide; the clearance is 0.2 mm), and touches nothing: one clearance finding."""
PROJECT = f"{NAME}.PrjPcb"
DOCUMENT = f"{NAME}.PcbDoc"


def plant(routed: Routed, *lines: str) -> None:
    """Add copper intents to the script of ``routed``, before its stitching vias."""
    routed.edit_script(ANCHOR, "".join(lines) + ANCHOR)


def cli(routed: Routed, *args: str) -> tuple[int, dict[str, Any], str]:
    """``fenolite <args> --json`` in this process: the exit code, the envelope and stderr."""
    out, err = io.StringIO(), io.StringIO()
    routed.monkeypatch.setattr("sys.stdout", out)
    routed.monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def build_altium(routed: Routed, *flags: str, out: Path | None = None) -> tuple[int, dict[str, Any], str]:
    """``fenolite build --target altium`` of the script of ``routed`` into ``out`` (default: its folder)."""
    return cli(
        routed, "build", str(routed.script), "--out", str(out or routed.out), "--target", "altium", *flags
    )


def native(folder: Path, target: Path) -> Path:
    """A copy of the built project ``folder`` without its ``.fenolite/`` cache: native input."""
    shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".fenolite"))
    return target


def stages(envelope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {stage["name"]: stage for stage in envelope["result"]["stages"]}


def coded(envelope: dict[str, Any], code: str) -> list[dict[str, Any]]:
    return [found for found in envelope["issues"] if found["code"] == code]


__all__ = [
    "CROSSING",
    "DOCUMENT",
    "NEAR",
    "PROJECT",
    "build_altium",
    "cli",
    "coded",
    "native",
    "plant",
    "stages",
]
