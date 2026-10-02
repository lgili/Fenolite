# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library resolution during build (capability design-dsl, "Library resolution during build"; c0011)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import LIBS, blink, build, project

from fenolite.dsl import Design, Part, mm
from fenolite.lens.build import UnresolvedLibrariesError


def test_two_unknown_lib_ids() -> None:
    d = Design("t")
    d.board(mm(20), mm(20))
    d.add(
        Part("R1", "Nope:A", footprint="Mini:Mini_R_0603"), Part("D1", "Nope:B", footprint="Mini:Mini_R_0603")
    )
    with pytest.raises(UnresolvedLibrariesError) as caught:
        build(d)
    error = caught.value
    assert error.cli_code == "FEN-3001" and len(error.issues) == 2
    assert all(i.code.startswith("kicad.lib.") for i in error.issues)


def test_footprint_and_value_from_the_symbol() -> None:
    d = Design("t")
    d.board(mm(30), mm(30))
    u1 = Part("U1", "Mini:Mini_QFP32_IC")
    d.add(u1)
    u1.place(mm(15), mm(15))
    out = build(d)
    (component,) = out.design.circuit.components
    assert (
        component.lib_footprint_ref == "Mini:Mini_QFP-32_7x7mm_P0.8mm" and component.value == "Mini_QFP32_IC"
    )


def test_no_footprint_anywhere() -> None:
    d = Design("t")
    d.board(mm(20), mm(20))
    d.add(Part("X1", "Mini:Mini_GND"))
    out = build(d)
    assert out.files == {} and any(i.code == "build.no-footprint" and "X1" in i.message for i in out.issues)


def test_row_origins_reported() -> None:
    out = build(blink())
    assert out.summary["libraries"]["Mini:Mini_R_0603"] == "project"  # type: ignore[index]


def test_global_footprint_not_vendored(tmp_path: Path) -> None:
    config = tmp_path / "config"
    (config / "10.0").mkdir(parents=True)
    row = f'(lib (name "G") (type "KiCad") (uri "{LIBS / "Mini_v9.pretty"}") (options "") (descr ""))'
    (config / "10.0" / "fp-lib-table").write_text(
        f"(fp_lib_table\n\t(version 7)\n\t{row}\n)\n", encoding="utf-8"
    )
    (tmp_path / "p").mkdir()
    folder = project(
        tmp_path / "p", {"Mini": str(LIBS / "Mini_v9.pretty")}, {"Mini": str(LIBS / "Mini_v9.kicad_sym")}
    )
    d = blink()
    d.parts["R1"].footprint = "G:Mini_R_0603"
    out = build(d, project_dir=folder, config_home=config)
    found = [i for i in out.issues if i.code == "build.global-library"]
    assert len(found) == 1 and "G:Mini_R_0603" in found[0].message
    assert not any(k.startswith("lib/G.pretty/") for k in out.files)
    assert b'"G"' not in out.files["fp-lib-table"] and b"(name G)" not in out.files["fp-lib-table"]
