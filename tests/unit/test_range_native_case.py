# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hermetic setup/negative controls for c0246's direct native case; no external tool."""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

TESTS = Path(__file__).resolve().parents[1]


@pytest.fixture
def case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    from fenolite.backends.kicad.cli import KicadCli

    def forbidden(*args, **kwargs):
        raise AssertionError("hermetic checkpoint attempted native execution")

    monkeypatch.setattr(KicadCli, "run", forbidden)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    kicad = TESTS / "kicad"
    for folder in (kicad, *(p for p in kicad.iterdir() if p.is_dir() and any(p.glob("_*.py")))):
        monkeypatch.syspath_prepend(str(folder))
    spec = importlib.util.spec_from_file_location(
        "native_range_case", kicad / "build/test_value_range_build.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("target", (9, 10))
def test_both_range_variants_build_in_temporary_sources(case, tmp_path: Path, target: int) -> None:
    from _buildhelp import BLINK_DIR

    before = {p.relative_to(BLINK_DIR): p.read_bytes() for p in BLINK_DIR.rglob("*") if p.is_file()}
    pair = case._build_pair(tmp_path, target)
    assert pair["nominal"] == pair["range"]
    assert {"blink.kicad_sch", "blink.kicad_pcb", "blink.kicad_pro"} <= pair["nominal"].keys()
    assert {p.relative_to(BLINK_DIR): p.read_bytes() for p in BLINK_DIR.rglob("*") if p.is_file()} == before
    assert case.pytestmark.name == "needs_kicad"


@pytest.mark.parametrize(
    "defect", (None, "connected-pin-lost", "erc-execution", "erc-invalid", "erc-finding")
)
def test_native_case_consumes_both_inputs_and_rejects_bad_results(
    case, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str | None
) -> None:
    calls = []

    def export(tool, files):
        calls.append("netlist")
        found = case.own_netlist(
            case.sch.read_schematic(files[case.ROOT_SHEET].decode("utf-8")), project="blink"
        )
        if defect == "connected-pin-lost":
            target = next(n for n in found.nets if any(p.ref == "R1" for p in n.nodes))
            bad = replace(target, nodes=tuple(n for n in target.nodes if n.ref != "R1"))
            found = replace(found, nets=tuple(bad if n == target else n for n in found.nets))
        return found

    def erc(tool, schematic, files):
        calls.append("ERC")
        data = {
            "source": "blink.kicad_sch",
            "date": "2026-10-29",
            "kicad_version": "10.0.6",
            "sheets": [{"path": "/", "uuid_path": "/", "violations": []}],
        }
        if defect == "erc-invalid":
            data = {}
        if defect == "erc-finding":
            data["sheets"][0]["violations"] = [
                {
                    "type": "pin_not_connected",
                    "severity": "error",
                    "description": "authored defect",
                    "items": [],
                }
            ]
        return case._erc.Report(3 if defect == "erc-execution" else 0, data, "authored tool stub")

    monkeypatch.setattr(case, "_export", export)
    monkeypatch.setattr(case._erc, "run_erc", erc)
    if defect:
        from fenolite.core.errors import FormatError

        with pytest.raises((AssertionError, FormatError)):
            case._measure_pair(tmp_path, 10, object())
    else:
        assert set(case._measure_pair(tmp_path, 10, object())) == {"nominal", "range"}
        assert calls == ["netlist", "ERC", "netlist", "ERC"]
