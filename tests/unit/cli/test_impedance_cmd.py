# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite impedance`` (capability cli-contract, "Impedance command"; change c0105). Hermetic: no tool
runs."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from _asmcli import FIXTURE, isolate
from _buildhelp import blink_variant
from _checkcli import run, without_elapsed
from _projects import tree_snapshot
from _zdesign import script

from fenolite.analysis.impedance import microstrip_mohm
from fenolite.cli.cmd_impedance import COMMAND
from fenolite.exports.impedance import COLUMNS


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolate(monkeypatch, tmp_path)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def _built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **options: object) -> Path:
    source = blink_variant(tmp_path / "src")
    source.write_text(script(**options), encoding="utf-8", newline="\n")  # type: ignore[arg-type]
    out = tmp_path / "z"
    code, env, err, _ = run(monkeypatch, tmp_path, "build", str(source), "--out", str(out), "--confirm")
    assert code == 0, (env.get("issues"), err)
    return out


def test_command_registration() -> None:
    assert COMMAND.name == "impedance" and COMMAND.mutates
    assert COMMAND.mutation_example_args[-2:] == ("--out", "impedance.csv")


def test_built_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _built(monkeypatch, tmp_path)
    before = tree_snapshot(folder)
    code, env, _, first = run(monkeypatch, tmp_path, "impedance", str(folder))
    assert code == 0, env["issues"]
    result = env["result"]
    assert result["source"] == "model" and result["columns"] == list(COLUMNS)
    assert [(r["target"], r["layer"]) for r in result["rows"]] == [
        ("SE50", "F.Cu"),
        ("SE50", "B.Cu"),
        ("USB90", "F.Cu"),
    ]
    assert result["counts"] == {"targets": 2, "rows": 3, "estimated": 0, "left_out": 0}
    usb = result["rows"][2]
    assert (usb["width"], usb["gap"], usb["nets"]) == (200_000, 150_000, ["USB_N", "USB_P"])
    assert result["rows"][0]["heights"] == [200_000] and result["rows"][0]["epsilon_r"] == "4.3"
    assert env["evidence"]["level"] == "INFERRED" and env["receipt"] is None
    assert tree_snapshot(folder) == before
    _, _, _, second = run(monkeypatch, tmp_path, "impedance", str(folder))
    assert without_elapsed(first) == without_elapsed(second)


def test_estimate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _built(monkeypatch, tmp_path)
    code, env, _, _ = run(monkeypatch, tmp_path, "impedance", str(folder), "--estimate")
    assert code == 0, env["issues"]
    se50, _, usb = env["result"]["rows"]
    assert se50["estimate"]["mohm"] == microstrip_mohm(350_000, 200_000, 35_000, "4.3")
    assert se50["estimate"]["form"] == "microstrip" and se50["estimate"]["in_range"] is True
    assert isinstance(se50["estimate"]["suggested_width"], int)
    assert usb["estimate"] == {
        "mohm": None,
        "suggested_width": None,
        "in_range": None,
        "form": "",
        "reason": "differential",
    }
    codes = [i["code"] for i in env["issues"]]
    assert codes.count("impedance.estimate-unsupported") == 1
    assert env["evidence"]["level"] == "INFERRED"
    assert {"H-G-AN-ZMS", "H-G-AN-ZSL"} <= set(env["evidence"]["hypotheses"])
    assert env["result"]["counts"]["estimated"] == 2


def test_estimate_without_stackup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _built(monkeypatch, tmp_path, usb90=False, stackup=None)
    code, env, _, _ = run(monkeypatch, tmp_path, "impedance", str(folder), "--estimate")
    assert code == 0
    assert env["result"]["counts"]["left_out"] == 2
    assert [i["code"] for i in env["issues"]].count("impedance.no-stackup") == 1
    assert env["evidence"]["level"] == "UNVERIFIED"


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _built(monkeypatch, tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    code, env, _, _ = run(monkeypatch, work, "impedance", str(folder), "--out", "impedance.csv")
    assert code == 4 and not (work / "impedance.csv").exists()
    assert [w["path"] for w in env["result"]["plan"]] == ["impedance.csv"]
    code, env, _, _ = run(monkeypatch, work, "impedance", str(folder), "--out", "impedance.csv", "--confirm")
    assert code == 0
    data = (work / "impedance.csv").read_bytes()
    (written,) = env["receipt"]["written"]
    assert written["sha256"] == hashlib.sha256(data).hexdigest()
    lines = data.decode("utf-8").splitlines()
    assert lines[0] == ",".join(COLUMNS)
    assert lines[3].startswith("USB90,differential,microstrip,F.Cu,In1.Cu,90,10,0.2,0.15,0.2,4.3,USB90,")


def test_project_without_targets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _, _ = run(monkeypatch, tmp_path, "impedance", str(FIXTURE))
    assert code == 0 and env["result"]["rows"] == [] and env["result"]["source"] == "project"
    assert [i["code"] for i in env["issues"]] == ["impedance.none"]


def test_native_project_reads_profiles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = _built(monkeypatch, tmp_path)
    for path in (folder / ".fenolite").iterdir():
        path.unlink()
    (folder / ".fenolite").rmdir()
    code, env, _, _ = run(monkeypatch, tmp_path, "impedance", str(folder))
    assert code == 0 and env["result"]["source"] == "project"
    assert [r["target"] for r in env["result"]["rows"]] == ["SE50", "SE50", "USB90"]
    assert env["result"]["rows"][0]["ohms"] == "50"


def test_altium_document_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    document = tmp_path / "board.PcbDoc"
    document.write_bytes(b"\xd0\xcf\x11\xe0")
    code_bom, _, err_bom, _ = run(monkeypatch, tmp_path, "bom", str(document), "--source", "model")
    code, _, err, _ = run(monkeypatch, tmp_path, "impedance", str(document))
    assert code == code_bom != 0 and err["code"] == err_bom["code"]
