# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reproduce the authored starter benches and capture their exact local layouts.

No GUI placement or human review is claimed. Coordinates and copper below are original
bench choices. Connector copper is left to the containing board; these assets contain
only copper joined to the block. Run from a checkout after reviewing the five benches.
"""

from __future__ import annotations

import argparse
import dataclasses
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from fenolite import api
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.core.state import using_state
from fenolite.model.board import ZoneFill
from fenolite.testing import load

ROOT = Path(__file__).resolve().parents[2]
BLOCKS = ROOT / "src/fenolite/blocks"
# Part positions are in the instance frame. Pads are resolved from the shipped lands.
BENCHES = {
    "voltage_divider": """
top, bot = dut.part("divider_top"), dut.part("divider_bot")
top.place(mm(0), mm(0), rot=270)
bot.place(mm(0), mm(4), rot=270)
design.track("divider_mid", top.pad(2), bot.pad(1), width=mm("0.25"))
""",
    "rc_lowpass": """
r, c = dut.part("filter_R"), dut.part("filter_C")
r.place(mm(0), mm(0))
c.place(mm(4), mm(0))
design.track("filter_out", r.pad(2), c.pad(1), width=mm("0.25"))
""",
    "led_indicator": """
r, led = dut.part("r"), dut.part("led")
r.place(mm(0), mm(0))
led.place(mm(4), mm(0), rot=180)
design.track("indicator_anode", r.pad(2), led.pad(2), width=mm("0.25"))
""",
    "i2c_pullups": """
sda, scl = dut.part("r_sda"), dut.part("r_scl")
sda.place(mm(0), mm(0))
scl.place(mm(0), mm(3))
design.track("pullup_supply", sda.pad(1), scl.pad(1), width=mm("0.25"))
""",
    "protected_input": """
tvs, r = dut.part("tvs"), dut.part("r")
tvs.place(mm(0), mm(0), rot=180)
r.place(mm(4), mm(0))
design.track("protected_ext", tvs.pad("K"), r.pad(1), width=mm("0.25"))
return_via = tvs.pad("A").at(mm(0), mm(1))
design.via("protection_return", return_via, net=dut.GND.main(), diameter=mm("0.6"), drill=mm("0.3"))
design.track("protection_ground", tvs.pad("A"), return_via, width=mm("0.25"))
design.zone(dut.GND.main(), layers=("B.Cu",), name="local_return", outline=(
    (mm(10), mm(10)), (mm(12), mm(10)), (mm(12), mm(12)), (mm(10), mm(12))),
    connection="solid")
""",
}


def capture(name: str, output: Path) -> bytes:
    """Build a separately authored bench and use the normal reviewed capture writer."""
    with TemporaryDirectory(prefix="fenolite-starter-layout-") as temp:
        folder = Path(temp)
        source = (BLOCKS / "usage" / f"{name}.py").read_text(encoding="utf-8").split("# Host copper:")[0]
        source += "\nfrom fenolite.dsl import row\ndut.layout(row())\n" + BENCHES[name]
        script = folder / "design.py"
        script.write_text(source, encoding="utf-8")
        shutil.copytree(BLOCKS / "usage/devices", folder / "devices")
        with load(script) as design, using_state(folder / "state"):
            if name == "protected_input":
                # The tiny isolated bottom rectangle is authored copper, not an oracle fill.
                # Capture retains the outline and discards this derived fill as its contract requires.
                board = design.model.board
                assert board is not None
                zones = tuple(
                    dataclasses.replace(z, fills=(ZoneFill("B.Cu", z.outline),), filled=True)
                    for z in board.zones
                )
                model = dataclasses.replace(design.model, board=dataclasses.replace(board, zones=zones))
                next(design.path.glob("*.kicad_pcb")).write_text(KicadBackend().write(model).text)
            reply = api.run(
                "blocks",
                "capture",
                str(design.path),
                "--instance",
                "dut",
                "-o",
                str(output),
                "--confirm",
                cwd=output.parent,
                seed=0,
                timestamp="2026-01-01T00:00:00Z",
            )
            if reply.exit_code:
                raise RuntimeError(f"{name}: {reply.error}; {(reply.envelope or {}).get('issues')}")
        return output.read_bytes()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="capture privately and compare bytes")
    args = parser.parse_args()
    for name in sorted(BENCHES):
        target = BLOCKS / "layouts" / f"{name}.toml"
        target.parent.mkdir(exist_ok=True)
        if args.check:
            with TemporaryDirectory(prefix="fenolite-starter-recapture-") as temp:
                actual = capture(name, Path(temp) / target.name)
            if not target.is_file() or actual != target.read_bytes():
                raise RuntimeError(f"{name}: captured layout differs")
        else:
            capture(name, target)
        print(f"{name}: {'equal' if args.check else 'captured'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
