# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""H-K-BLOCK-LAYOUT-DRC: both sides read back in KiCad and have no DRC/unconnected findings (c0271)."""

from __future__ import annotations

import csv
import io
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from _probes import major, runner

import fenolite.cli.main as cli
from fenolite.model import canonical

pytestmark = pytest.mark.needs_kicad
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("flip", [False, True], ids=["both-sides", "kept-block-flipped"])
def test_block_layouts_both_sides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flip: bool) -> None:
    source = tmp_path / "source"
    shutil.copytree(ROOT / "examples/blocks", source)
    out = tmp_path / "out"
    original = (source / "layouts.py").read_text()
    if flip:
        (source / "layouts.py").write_text(original.replace('side="bottom"', 'side="top"'))
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli.main(
            [
                "--kicad-version",
                str(major()),
                "build",
                str(source / "layouts.py"),
                "--out",
                str(out),
                "--confirm",
                "--json",
            ]
        )
    assert code == 0, stderr.getvalue()
    if flip:
        (source / "layouts.py").write_text(original)
        with monkeypatch.context() as patch:
            patch.setattr("sys.stdout", io.StringIO())
            patch.setattr("sys.stderr", stderr)
            code = cli.main(
                [
                    "--kicad-version",
                    str(major()),
                    "build",
                    str(source / "layouts.py"),
                    "--out",
                    str(out),
                    "--confirm",
                    "--json",
                ]
            )
        assert code == 0, stderr.getvalue()
    model = canonical.load_dir(out / ".fenolite")
    assert model.board is not None and len(model.board.footprints) == 4 and len(model.board.tracks) == 2
    files = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    run = runner().run(
        [
            "pcb",
            "export",
            "pos",
            "--format",
            "csv",
            "--units",
            "mm",
            "--side",
            "both",
            "-o",
            "pos.csv",
            "block_layouts.kicad_pcb",
        ],
        files=files,
    )
    assert run.ok, run.stderr
    positions = {row["Ref"]: row for row in csv.DictReader(io.StringIO(run.outputs["pos.csv"].decode()))}
    refs = {c.id: c.ref for c in model.circuit.components}
    for fp in model.board.footprints:
        row = positions[refs[fp.component_id]]
        assert Decimal(row["PosX"]) * 1_000_000 == fp.position.x
        assert -Decimal(row["PosY"]) * 1_000_000 == fp.position.y
        assert int(Decimal(row["Rot"]) * 1_000_000) % 360_000_000 == fp.rotation
        assert row["Side"] == fp.side
    drc = runner().run(
        ["pcb", "drc", "--format", "json", "--severity-all", "-o", "drc.json", "block_layouts.kicad_pcb"],
        files=files,
    )
    assert drc.ok, drc.stderr
    report = json.loads(drc.outputs["drc.json"])
    assert report["violations"] == [] and report["unconnected_items"] == []
