# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The acceptance preparation is local; external import stays in the oracle test."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def tool():
    name = "fenolite_acceptance_v03"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "acceptance_v03.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    folder = tmp_path_factory.mktemp("v03") / "prepared"
    result = tool().run(folder, prepare_only=True)
    return folder, result


def test_prepare_writes_every_required_feature_without_claiming_acceptance(prepared) -> None:
    folder, result = prepared
    assert result["passed"] and not result["acceptance_complete"]
    assert result["mode"] == "prepare"
    assert result["versions"]["kicad"] is None and result["versions"]["altium"] is None
    assert result["kit_run_id"] is None
    assert len(result["scope"]) == 12 and all(result["scope"].values())
    assert json.loads((folder / "summary.json").read_text(encoding="utf-8")) == result
    assert (folder / "kicad" / "acceptance_v03.kicad_pcb").is_file()
    assert (folder / "altium" / "acceptance_v03.PrjPcb").is_file()


def test_missing_output_is_detected_and_results_cannot_be_overwritten(prepared) -> None:
    folder, _result = prepared
    with pytest.raises(FileExistsError):
        tool().run(folder, prepare_only=True)
    job = folder / "altium" / "acceptance_v03.OutJob"
    data = job.read_bytes()
    job.unlink()
    try:
        assert not tool().inventory(folder)["outjob"]
    finally:
        job.write_bytes(data)


def test_readback_checks_and_project_rewrite_need_no_external_tool(prepared) -> None:
    folder, _result = prepared
    for name, args in [
        (
            "proof-kicad",
            [
                "check",
                str(folder / "kicad" / "acceptance_v03.kicad_pcb"),
                "--stages",
                "model.validate,roundtrip",
            ],
        ),
        (
            "proof-altium",
            [
                "check",
                str(folder / "altium" / "acceptance_v03.PrjPcb"),
                "--stages",
                "model.validate,roundtrip.rta1",
            ],
        ),
        ("proof-rta3", ["roundtrip", str(folder / "altium" / "acceptance_v03.PrjPcb"), "--level", "rta3"]),
    ]:
        result = tool().command(args, folder, name)
        assert result["passed"], json.dumps(result["reply"])


def test_exception_is_recorded_as_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = tool()
    monkeypatch.setattr(module, "build", lambda *args: {"name": "build", "passed": True, "exit_code": 0})

    def fail(*args):
        raise ValueError("bad prepared model")

    monkeypatch.setattr(module, "add_bus", fail)
    folder = tmp_path / "failed"
    with pytest.raises(ValueError, match="bad prepared model"):
        module.run(folder, prepare_only=True)
    result = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    assert not result["passed"] and not result["acceptance_complete"]
    assert result["steps"][-1]["error_type"] == "ValueError"


def test_target_equivalence_uses_only_committed_triangle_profile(prepared) -> None:
    from fenolite.backends.kicad import altium_import

    folder, _result = prepared
    profile = folder / "triangle.toml"
    profile.write_text(altium_import.exclusions_text(), encoding="utf-8")
    result = tool().command(
        [
            "equivalent",
            str(folder / "kicad" / "acceptance_v03.kicad_pcb"),
            str(folder / "altium" / "acceptance_v03.PcbDoc"),
            "--level",
            "5",
            "--exclusions",
            str(profile),
            "--profile",
            altium_import.PROFILE,
            "--ignore-ref",
            "",
            "--ignore-ref",
            "[*]",
        ],
        folder,
        "proof-equivalent",
    )
    assert result["passed"], json.dumps(result["reply"])
