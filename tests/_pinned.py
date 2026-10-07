# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the pinned-build test of change c0123 measures (``tests/unit/lens/test_build_bytes_pinned.py``).

One short digest per output of a build, so a pin that moves says which output moved:

- KiCad: ``files`` (every built file but the two that hold the package version), ``netlist`` (Fenolite's
  own netlist of the written sheets), ``parity`` (the comparison of the written sheets with the written
  board), ``bom`` and ``pnp`` (the default tables of the built model, as CSV).
- Altium: the files of a build in the ASCII and in the binary schematic form.

Run ``uv run python tests/_pinned.py`` to print the two tables. A pin is changed only by the change that
changes the writer, with the reason beside it.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONED = (".fenolite/meta.json", ".fenolite/build.json")
"""The two built files that hold the package version, or the hash of a file that holds it."""
TARGETS = (9, 10)
GENERATED = 25
GENERATED_MODULES = 5
WIDTH = 12


def _short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:WIDTH]


def files_digest(files: Mapping[str, bytes]) -> str:
    """The digest of the sorted ``(path, SHA-256)`` list of ``files`` without ``VERSIONED``."""
    lines = [f"{path}\0{hashlib.sha256(data).hexdigest()}\n" for path, data in sorted(files.items())]
    return _short("".join(line for line in lines if line.split("\0")[0] not in VERSIONED).encode("utf-8"))


def kicad_designs() -> dict[str, Callable[[], tuple[object, Path]]]:
    """Name → a function that gives the design and the folder of its library tables."""
    import _gendesigns
    from _buildhelp import BLINK_DIR, blink
    from _schbuild import nested_design, units_design

    from fenolite.cli._script import run_design_script

    board40 = ROOT / "examples" / "board_40parts"
    found: dict[str, Callable[[], tuple[object, Path]]] = {
        "blink": lambda: (blink(), BLINK_DIR),
        "blink-unmarked": lambda: (blink(marks=False), BLINK_DIR),
        "board_40parts": lambda: (run_design_script(board40 / "design.py").design, board40),
        "nested": lambda: (nested_design(), BLINK_DIR),
        "units": lambda: (units_design(), BLINK_DIR),
    }
    for index in range(GENERATED):
        found[f"gen-{index:02d}"] = lambda index=index: (
            _gendesigns.design(_gendesigns.SEED, index),
            BLINK_DIR,
        )
    for index in range(GENERATED_MODULES):
        found[f"genmod-{index:02d}"] = lambda index=index: (
            _gendesigns.design(_gendesigns.MODULE_SEED, index, True),
            BLINK_DIR,
        )
    return found


def kicad_pin(design: object, project_dir: Path, target: int) -> str:
    """``files:netlist:parity:bom:pnp`` of the build of ``design`` for ``target``."""
    from _buildhelp import build
    from _schbuild import root_name, write_files

    from fenolite.backends.kicad import parity_inputs
    from fenolite.backends.kicad.pcb import read_board
    from fenolite.checks import parity
    from fenolite.exports import bom, placement
    from fenolite.exports.assembly import DEFAULT, render_csv

    output = build(design, target, project_dir=project_dir)  # type: ignore[arg-type]
    errors = [issue.code for issue in output.issues if issue.severity == "error"]
    assert not errors, errors
    model = output.layout
    assert model is not None
    with tempfile.TemporaryDirectory() as name:
        folder = write_files(output, Path(name))
        root = folder / root_name(output)
        sheets = parity_inputs.read_sheets(root)
        netlist = parity_inputs.own_netlist(sheets, project=root.stem)
        nets = sorted(
            (net.name, sorted((node.ref, node.pin, node.pintype) for node in net.nodes))
            for net in netlist.nets
        )
        board_file = root.with_suffix(".kicad_pcb")
        board = read_board(board_file.read_text(encoding="utf-8"), file=board_file.name)
        report = parity.compare(parity_inputs.schematic_side(root), board)
    findings = [finding.to_json() for finding in report.findings]
    lines = bom.group(bom.parts_from_model(model), DEFAULT.bom)
    bill = render_csv([c.name for c in DEFAULT.bom.columns], bom.table(lines, DEFAULT.bom), DEFAULT.csv)
    rows = placement.apply(placement.rows_from_model(model), DEFAULT.placement)
    places = render_csv(
        [c.name for c in DEFAULT.placement.columns], placement.table(rows, DEFAULT.placement), DEFAULT.csv
    )
    parts = (
        files_digest(output.files),
        _short(repr(nets).encode("utf-8")),
        _short(repr((findings, sorted(report.summary.items()))).encode("utf-8")),
        _short(bill),
        _short(places),
    )
    return ":".join(parts)


def altium_designs() -> dict[str, Callable[[], tuple[object, Path]]]:
    kicad = kicad_designs()
    return {name: kicad[name] for name in ("blink", "blink-unmarked", "board_40parts", "nested", "units")}


def altium_pin(design: object, project_dir: Path, form: str) -> str:
    """The digest of the files of the Altium build of ``design`` in the schematic form ``form``."""
    from _buildhelp import resolver

    from fenolite.dsl import placements, to_model
    from fenolite.lens.altium import build_altium

    output = build_altium(
        to_model(design),  # type: ignore[arg-type]
        name=design.name,  # type: ignore[attr-defined]
        placed=tuple(placements(design)),  # type: ignore[arg-type]
        placements=placements(design),  # type: ignore[arg-type]
        form=form,  # type: ignore[arg-type]
        resolver=resolver(10, project_dir),
    )
    errors = [issue.code for issue in output.issues if issue.severity == "error"]
    assert not errors, errors
    return files_digest(output.files)


def measured() -> tuple[dict[str, str], dict[str, str]]:
    kicad = {
        f"{name}@{target}": kicad_pin(*make(), target)
        for name, make in kicad_designs().items()
        for target in TARGETS
    }
    altium = {
        f"{name}@{form}": altium_pin(*make(), form)
        for name, make in altium_designs().items()
        for form in ("ascii", "binary")
    }
    return kicad, altium


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tests"))
    for title, table in zip(("KICAD", "ALTIUM"), measured(), strict=True):
        print(f"{title} = {{")
        for key, value in table.items():
            print(f'    "{key}": "{value}",')
        print("}")
