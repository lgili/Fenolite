# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT-A2 on every example build (capability altium-verification, "Round-trip level RT-A2"; change c0044):
each script under ``examples/`` is built for the Altium target into ``tmp_path``, in the binary and in the
ASCII schematic form, and ``fenolite check --stages roundtrip.rta2`` judges the level. Evidence of level
INFERRED (``H-A-VER-RTA2-2``): Fenolite's writers read by Fenolite's readers."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from _altium_built import BLINK, EXAMPLES, build_altium_example, built_blink

import fenolite.cli.main as cli_main
from fenolite.backends.altium.roundtrip import RT_A2_SCOPE
from fenolite.checks.rta2 import CIRCUIT_KINDS
from fenolite.model.canonical import load_dir

FORMS = {"binary": (), "ascii": ("--altium-format", "ascii")}
OFFICIAL = "blink_official/design.py"
"""The one example that needs the official KiCad libraries: built only where they are installed."""
WITH_PCB = {
    "altium_hier_board/design.py",
    "blink_2layer/design.py",
    "blink_official/design.py",
    "blink_routed/design.py",
    "board_40parts/design.py",
}
"""The examples whose build writes a PCB document."""
SCHEMATIC_ONLY = {
    "altium_hier/design.py",
    "altium_hier/partial.py",
    "altium_kicad/design.py",
    "altium_kicad/no_connect.py",
    "altium_sample/design.py",
}
SCRIPTS = sorted(path.relative_to(EXAMPLES).as_posix() for path in EXAMPLES.glob("*/*.py"))
NOT_IN_MODEL = {"footprint", "pad", "track", "arc", "via", "zone"}
"""The board kinds that the built model of an Altium build does not hold today."""


def _check(monkeypatch: pytest.MonkeyPatch, folder: Path) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", str(folder), "--stages", "roundtrip.rta2", "--json"])
    return code, json.loads(out.getvalue())


def _judge(monkeypatch: pytest.MonkeyPatch, folder: Path, *, pcb: bool) -> dict[str, Any]:
    code, env = _check(monkeypatch, folder)
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"]) == ("roundtrip.rta2", "ok")
    summary = stage["summary"]
    assert summary["level"] == "RT-A2" and summary["holds"] is True and summary["differences"] == 0
    assert summary["compared"]["schematic"] == sorted(CIRCUIT_KINDS)
    assert ("pcb" in summary["compared"]) is pcb
    assert stage["evidence"]["level"] == "INFERRED"
    assert "H-A-VER-RTA2-2" in stage["evidence"]["hypotheses"]
    assert not [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    return summary


def test_every_example_is_classified() -> None:
    """A new script under ``examples/`` must be named here, so that it is built and judged."""
    assert set(SCRIPTS) == WITH_PCB | SCHEMATIC_ONLY and not WITH_PCB & SCHEMATIC_ONLY


@pytest.mark.parametrize("form", sorted(FORMS))
@pytest.mark.parametrize("script", [s for s in SCRIPTS if s != OFFICIAL])
def test_example_holds_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, script: str, form: str) -> None:
    code, folder, error = build_altium_example(monkeypatch, tmp_path, EXAMPLES / script, *FORMS[form])
    assert code == 0, error
    summary = _judge(monkeypatch, folder, pcb=script in WITH_PCB)
    if script in WITH_PCB:
        # The built model is the script's model: it holds no footprint and no copper, so these kinds are
        # counted and not compared. The net classes are compared.
        assert "netclass" in summary["compared"]["pcb"]
        outside = summary["not_in_model"]["pcb"]
        assert set(outside) <= NOT_IN_MODEL and outside["footprint"] >= 3 and outside["pad"] >= 3
        assert set(summary["compared"]["pcb"]) | set(outside) <= set(RT_A2_SCOPE.fields)
    else:
        assert summary["not_in_model"] == {}


def test_module_sheets_hold_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = EXAMPLES / "altium_hier" / "design.py"
    code, folder, error = build_altium_example(monkeypatch, tmp_path, script, "--altium-sheets", "modules")
    assert code == 0, error
    assert len(list(folder.glob("*.SchDoc"))) > 1
    _judge(monkeypatch, folder, pcb=False)


@pytest.mark.needs_libs
@pytest.mark.parametrize("form", sorted(FORMS))
def test_official_example_holds_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, form: str) -> None:
    code, folder, error = build_altium_example(monkeypatch, tmp_path, EXAMPLES / OFFICIAL, *FORMS[form])
    if code != 0:
        pytest.skip(f"the official libraries do not resolve here: {error[:200]}")
    _judge(monkeypatch, folder, pcb=True)


def test_built_blink_holds_rta2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Built blink holds RT-A2"."""
    folder = built_blink(monkeypatch, tmp_path)
    summary = _judge(monkeypatch, folder, pcb=True)
    assert summary["compared"] == {"schematic": ["component", "net", "no_connect"], "pcb": ["netclass"]}
    assert summary["not_in_model"] == {"pcb": {"footprint": 3, "pad": 36}}


def test_changed_document_is_caught_in_the_built_blink(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Scenario "A changed document is caught": the stored model gives R1 another value."""
    folder = built_blink(monkeypatch, tmp_path)
    circuit = folder / ".fenolite" / "circuit.json"
    text = circuit.read_text(encoding="utf-8")
    assert text.count('"value": "330"') == 1 and BLINK.is_file()
    circuit.write_text(text.replace('"value": "330"', '"value": "470"'), encoding="utf-8", newline="\n")
    code, env = _check(monkeypatch, folder)
    assert code == 5
    failed = [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    assert [(i["severity"], i["where"]) for i in failed] == [("error", "schematic:/component/R1/value")]
    assert '"470"' in failed[0]["message"] and '"330"' in failed[0]["message"]
    summary = env["result"]["stages"][0]["summary"]
    assert (summary["holds"], summary["differences"]) == (False, 1)


def test_built_model_stores_the_written_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Regression (found by RT-A2): a component whose value is empty in the script is written with its
    symbol's name as the comment, and the built model stores that value."""
    script = EXAMPLES / "altium_sample" / "design.py"
    code, folder, error = build_altium_example(monkeypatch, tmp_path, script)
    assert code == 0, error
    model = load_dir(folder / ".fenolite")
    assert 'Part("J1"' in script.read_text(encoding="utf-8")
    assert model.by_ref["J1"].value == "HDR2"
    assert all(component.value for component in model.circuit.components)
