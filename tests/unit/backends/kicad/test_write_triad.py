# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated projects are coherent (capability kicad-file-backend; change c0010)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import _netclass_bench as nb
import pytest
from _prodesigns import project, text

from fenolite.backends.kicad._json import JsonNumber
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pro import read_project_text
from fenolite.backends.kicad.triad import TRIAD_SUFFIXES, write_triad
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Net

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "src" / "fenolite"


def test_three_files_always() -> None:
    files = write_triad(nb.bench_design(target=10, hv_clearance=None), name="blink", target=10)
    assert set(files) == {"blink.kicad_pcb", "blink.kicad_pro", "blink.kicad_dru"}
    empty = dataclasses.replace(nb.bench_design(target=10), rules=None)
    assert write_triad(empty, name="blink", target=10)["blink.kicad_dru"] == "(version 1)\n"
    assert TRIAD_SUFFIXES == (".kicad_pcb", ".kicad_pro", ".kicad_dru")


def test_existing_project_updated_not_replaced() -> None:
    data = project(10, x_unknown={"k": JsonNumber("1")})
    files = write_triad(nb.bench_design(target=10), name="b", target=10, existing_project=text(data))
    assert read_project_text(files["b.kicad_pro"])["x_unknown"] == {"k": JsonNumber("1")}


def test_one_failing_writer_aborts_the_set() -> None:
    bench = nb.bench_design(target=10)
    hv = bench.circuit.netclasses[0].id
    clk = Net(id=derived_id("net", "test", "clk"), name="CLK*", netclass_id=hv)
    broken = dataclasses.replace(
        bench, circuit=dataclasses.replace(bench.circuit, nets=(*bench.circuit.nets, clk))
    )
    with pytest.raises(LossyWriteError):
        write_triad(broken, name="b", target=10)


def test_backend_lowering_returns_the_triad() -> None:
    blink = dataclasses.replace(nb.bench_design(target=10), rules=None)
    assert KicadBackend().lower(blink, name="blink") == write_triad(blink, name="blink", target=10)


def test_backend_lowering_keeps_the_issues() -> None:
    bench = nb.bench_design(target=10, hv_clearance=500_000)
    data = project(10)
    data["board"]["design_settings"]["rules"]["min_clearance"] = JsonNumber("1.5")
    issues: list[Issue] = []
    other: list[Issue] = []
    KicadBackend().lower(bench, name="b", existing_project=text(data), issues=issues)
    write_triad(bench, name="b", target=10, existing_project=text(data), issues=other)
    assert issues and issues == other
    assert any(i.code == "kicad.project.below-floor" and "HV" in i.message for i in issues)


def test_no_prl_in_src() -> None:
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        strings = [
            n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        assert not any(s.endswith(".kicad_prl") or s == "kicad_prl" for s in strings), path
