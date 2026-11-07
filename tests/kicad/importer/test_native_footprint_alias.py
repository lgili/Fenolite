# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0342: native exported connectivity/Footprint identity agrees, alongside full3/S/8 proof."""

from __future__ import annotations

from pathlib import Path

import pytest
from _footprint_alias import alias_project
from _importcode import build, imported
from _kicad import cli
from _libs import isolated_kicad_env, kicad

from fenolite.api import run
from fenolite.backends.kicad.netlist import differences, read_netlist

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]


def test_native_original_alias_and_partition_survive_local_geometry_binding(tmp_path: Path) -> None:
    source = alias_project(tmp_path)
    copied = imported(tmp_path, source, "--confirm")
    assert copied.exit_code == 0, copied.error
    made = build(tmp_path / "out")
    assert made.exit_code == 0, made.error
    netlists = []
    for index, sheet in enumerate(
        [source.with_suffix(".kicad_sch"), tmp_path / "out/built/two_sheet.kicad_sch"]
    ):
        target = tmp_path / f"native-{index}.net"
        exported = kicad(
            cli(),
            isolated_kicad_env(tmp_path),
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadsexpr",
            "-o",
            target,
            sheet,
        )
        assert exported.returncode == 0, exported.stdout + exported.stderr
        netlists.append(read_netlist(target.read_text()))
    assert differences(netlists[0], netlists[1], pintypes=True) == ()
    assert next(c for c in netlists[1].components if c.ref == "J1").footprint == "Original:Mini_LED_THT_3mm"
    proof = run(
        "verify-source",
        str(tmp_path / "out/design.py"),
        "--against",
        str(source),
        "--levels",
        "3,S,8",
        cwd=tmp_path,
    )
    assert proof.exit_code == 0, proof.error
    assert proof.envelope is not None and proof.envelope["result"]["differences"] == []
