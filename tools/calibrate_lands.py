# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Calibrate the land constants ``lands/1`` from cited manufacturer patterns (change c0260, decision 5).

    uv run python tools/calibrate_lands.py [--check]

Reads every record of ``tests/data/packages/calibration``, back-solves the toe, heel and side goals each
manufacturer land implies, takes the lower median per land class (at least three records), rounds it to
10 µm, and writes ``src/fenolite/catalog/footprints/_table1.py``. The constants no pattern can calibrate
(pad gap, grid, courtyard, hole clearance, annular ring, paste cell and window) are Fenolite's own choices,
kept as they are. ``--check`` writes nothing and exits 1 when the committed table differs. Both modes list,
per class, the records used. The output is a function of the records only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fenolite.catalog.footprints.calibration import MIN_RECORDS, Calibration, calibrate, sample  # noqa: E402
from fenolite.catalog.footprints.lands import LAND_CLASSES  # noqa: E402
from fenolite.catalog.footprints.record import read_package  # noqa: E402

RECORDS = ROOT / "tests" / "data" / "packages" / "calibration"
TABLE = ROOT / "src" / "fenolite" / "catalog" / "footprints" / "_table1.py"
FIXED = {
    "pad_gap": 200_000,
    "grid": 10_000,
    "courtyard": 500_000,
    "hole_clearance": 200_000,
    "annular_ring": 350_000,
    "paste_cell": 2_000_000,
}
"""Fenolite's own choices of ``lands/1`` (``docs/formats/library/lands.md``)."""


def _int(value: int) -> str:
    return f"{value:_}"


def render(result: Calibration) -> str:
    """The text of ``_table1.py`` for ``result``."""
    lines = [
        "# SPDX-License-Identifier: Apache-2.0",
        "# Copyright (c) 2026 Fenolite contributors",
        '"""The land constants ``lands/1`` (change c0260), written by ``tools/calibrate_lands.py``.',
        "",
        "Do not edit. The goals and ball ratios are back-solved from the cited manufacturer patterns of",
        "``tests/data/packages/calibration`` (lower median per class of at least three records,",
        "rounded to 10 µm); ``pad_gap``, ``grid``, ``courtyard``, ``hole_clearance``, ``annular_ring``,",
        "``paste_cell`` and ``paste_window`` are Fenolite's own choices",
        "(``docs/formats/library/lands.md``). Every value is ``INFERRED``. No value is taken from",
        'IPC-7351 tables or its calculator."""',
        "",
        "from __future__ import annotations",
        "",
        "from fractions import Fraction",
        "",
        "from fenolite.catalog.footprints.lands import Goals, LandTable",
        "",
        "TABLE = LandTable(",
        "    version=1,",
        "    goals={",
    ]
    for cls in LAND_CLASSES:
        goals = result.goals.get(cls)
        if goals is not None:
            values = f"toe={_int(goals.toe)}, heel={_int(goals.heel)}, side={_int(goals.side)}"
            lines.append(f'        "{cls}": Goals({values}),')
    lines.append("    },")
    for key, value in FIXED.items():
        lines.append(f"    {key}={_int(value)},")
    ratios = ", ".join(
        f'"{kind}": Fraction({ratio.numerator}, {ratio.denominator})'
        for kind, ratio in sorted(result.ball_ratio.items())
    )
    lines.append(f"    ball_ratio={{{ratios}}},")
    lines.append("    paste_window=Fraction(4, 5),")
    lines.append("    calibration={")
    for cls, names in result.used.items():
        lines.append(f'        "{cls}": (')
        lines += [f'            "{name}",' for name in names]
        lines.append("        ),")
    lines.append("    },")
    lines.append(")")
    return "\n".join(lines) + "\n"


def run() -> tuple[Calibration, str]:
    samples = [
        sample(read_package(path.read_text(encoding="utf-8"), file=path.relative_to(ROOT).as_posix()))
        for path in sorted(RECORDS.glob("*.toml"))
    ]
    result = calibrate(samples)
    return result, render(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 when the committed table differs")
    args = parser.parse_args(argv)
    result, text = run()
    for cls, names in result.used.items():
        state = (
            "calibrated"
            if cls in result.goals or cls.removeprefix("grid-") in result.ball_ratio
            else (f"no goals (fewer than {MIN_RECORDS} records)")
        )
        print(f"{cls}: {state}; {len(names)} record(s): {', '.join(names)}")
    current = TABLE.read_text(encoding="utf-8") if TABLE.exists() else ""
    if args.check:
        if current != text:
            print(f"{TABLE.relative_to(ROOT)} differs from the calibration; run the tool without --check")
            return 1
        print(f"{TABLE.relative_to(ROOT)} is up to date")
        return 0
    TABLE.write_text(text, encoding="utf-8")
    print(f"wrote {TABLE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
