# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Design scripts with meanders, written under a temporary folder with the authored ``Mini`` libraries
beside them (capability design-dsl, "Meanders in a build"; capability kicad-oracle, "Meanders pass the
oracle"; change c0106). Every part, net, point and length is authored for these tests with round values.

- ``pair``: ``USB_P`` and ``USB_N`` from ``U1`` to ``J1`` by the tracks ``usb_p`` (25.2 mm) and ``usb_n``
  (24 mm), and the meander ``n_tune`` that brings ``usb_n`` to the length of ``usb_p``.
- ``axis``: one 20 mm track along an axis, meandered to 23 mm.
- ``angle``: a 20 mm segment at 30° and a short one, meandered to 25 mm.
- ``pair4``: the pair on four layers; ``usb_p`` changes to ``In1.Cu`` and back through two vias, so its
  length holds the via heights of the target major.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "examples" / "blink_routed"
LIBS = ROOT / "tests" / "data" / "libs"

_HEAD = """# SPDX-License-Identifier: CC0-1.0
# Authored for the Fenolite tests; no file, value, name or layout comes from any other project.
from fenolite.dsl import Design, Net, Part, connect, mm, via_step

design = Design("{name}")
design.board(mm(50), mm(40), copper={copper})
"""
_PAIR_PARTS = """
u1 = Part("U1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="A")
j1 = Part("J1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="B")
design.add(u1, j1)
usb_p, usb_n = Net("USB_P"), Net("USB_N")
connect(usb_p, u1[1], j1[1])
connect(usb_n, u1[2], j1[2])
u1.place(mm(10), mm(10))
j1.place(mm(14), mm(30))
design.track("usb_n", u1.pad(2), (mm(10.8), mm(14)), (mm(14.8), mm(14)), j1.pad(2), width=mm(0.2))
"""
_PAIR_P = 'design.track("usb_p", u1.pad(1), (mm(8.6), mm(10)), (mm(8.6), mm(30)), j1.pad(1), width=mm(0.2))\n'
_PAIR4_P = (
    'design.track("usb_p", u1.pad(1),\n'
    '             via_step(mm(8.2), mm(10), to="In1.Cu", diameter=mm(0.6), drill=mm(0.3)),\n'
    '             via_step(mm(8.2), mm(30), to="F.Cu", diameter=mm(0.6), drill=mm(0.3)), j1.pad(1),\n'
    "             width=mm(0.2))\n"
)
_PAIR_MEANDER = (
    'design.meander("n_tune", track="usb_n", segment=1, match="usb_p", amplitude=mm({amplitude}), '
    "pitch=mm(0.4))\n"
)
_RUN_PARTS = """
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="A")
r2 = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="B")
design.add(r1, r2)
tune = Net("TUNE")
connect(tune, r1[2], r2[1])
r1.place(mm(10), mm(10))
"""
_AXIS = 'r2.place(mm(31.6), mm(10))\ndesign.track("t", r1.pad(2), r2.pad(1), width=mm(0.2))\n'
_ANGLE = (
    "r2.place(mm(30.8), mm(20))\n"
    'design.track("t", r1.pad(2), (mm(28.120508), mm(20)), r2.pad(1), width=mm(0.2))\n'
)
_RUN_MEANDER = (
    'design.meander("m", track="t", segment=0, target=mm({target}), amplitude=mm(1), pitch=mm(1))\n'
)

TARGETS = {"axis": 23, "angle": 25}
"""The target length of the meandered track of a run case, in millimetres."""
NETS = {"pair": ("USB_N", "USB_P"), "pair4": ("USB_N", "USB_P"), "axis": ("TUNE",), "angle": ("TUNE",)}
"""The nets of each case; the first is the meandered one."""


def script_text(case: str, *, meander: bool = True, amplitude: str = "0.5") -> str:
    """The script of ``case``; ``meander=False`` leaves the meander out, ``amplitude`` (millimetres) is that
    of the pair's meander."""
    head = _HEAD.format(name=case, copper=4 if case == "pair4" else 2)
    if case in ("pair", "pair4"):
        body = _PAIR_PARTS + (_PAIR4_P if case == "pair4" else _PAIR_P)
        wave = _PAIR_MEANDER.format(amplitude="1" if case == "pair4" else amplitude)
    else:
        body = _RUN_PARTS + (_AXIS if case == "axis" else _ANGLE)
        wave = _RUN_MEANDER.format(target=TARGETS[case])
    return head + body + (wave if meander else "")


def write_script(tmp_path: Path, case: str = "pair", **options: Any) -> Path:
    """The script of ``case`` under ``tmp_path``, with the library tables of the routed example beside it
    and the authored libraries where those tables point."""
    root = tmp_path / "repo"
    folder = root / "examples" / case
    folder.mkdir(parents=True, exist_ok=True)
    if not (root / "tests" / "data" / "libs").is_dir():
        shutil.copytree(LIBS, root / "tests" / "data" / "libs")
    for table in ("fp-lib-table", "sym-lib-table"):
        shutil.copyfile(TABLES / table, folder / table)
    script = folder / "design.py"
    script.write_text(script_text(case, **options), encoding="utf-8")
    return script


def pair_script(tmp_path: Path, **options: Any) -> Path:
    """The design script of "A pair matched in a build"."""
    return write_script(tmp_path, "pair", **options)


def isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def build(
    monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, target: int, *flags: str
) -> tuple[int, dict[str, Any], str]:
    """``fenolite --kicad-version <target> build <script> --out <out> <flags> --json`` in process: the exit
    code, the envelope and the text of stderr."""
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    args = ["--kicad-version", str(target), "build", str(script), "--out", str(out), *flags, "--json"]
    code = cli_main.main(args)
    return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()


def files(out: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(out)): p.read_bytes()
        for p in sorted(out.rglob("*"))
        if p.is_file() and not p.name.endswith(".bak")
    }
