# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad accepts a project built from catalog lib ids alone (capability fenolite-component-catalog,
"Catalog-only design passes check"; hypothesis H-K-FP-FIELDS; change c0077).

The catalog blink of ``tests/_catalog_design.py`` is built for each target the running ``kicad-cli`` can
read and given to the whole ``fenolite check``. Its footprints carry the generated ``Reference`` and
``Value`` properties in the board and in the vendored library: KiCad must name each pad by its reference
(no ``netlist.*`` issue, no unconnected item) and must find nothing to say about the library footprints
(no ``lib_footprint_issues``, no ``lib_footprint_mismatch``). The control builds the same design without
the generated fields and expects ``check`` to refuse it.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _catalog_design import NAME, REFS, write_script
from _kicad import cli, supported_version

import fenolite.cli.main as cli_main
from fenolite.backends.kicad import embed

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]
LIBRARY_TYPES = ("lib_footprint_issues", "lib_footprint_mismatch")


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue() or "{}"), json.loads(stderr.getvalue() or "{}")


def built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: int) -> Path:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    script = write_script(tmp_path / "P")
    out = tmp_path / "out"
    code, env, err = run(
        monkeypatch, "--kicad-version", str(target), "build", str(script), "--out", str(out), "--confirm"
    )
    assert code == 0, err
    assert set(env["result"]["libraries"].values()) == {"builtin"}
    assert (out / f"{NAME}.kicad_pcb").is_file()
    return out


def stage(envelope: dict[str, Any], name: str) -> dict[str, Any]:
    return next(s for s in envelope["result"]["stages"] if s["name"] == name)


@pytest.mark.parametrize("target", TARGETS)
def test_kicad_accepts_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    version = supported_version()
    out = built(monkeypatch, tmp_path, target)
    code, env, err = run(monkeypatch, "check", str(out), "--kicad-cli", cli())
    issues = env["issues"]
    print(f"kicad-cli {version}, target {target}: exit {code}, issues {[i['code'] for i in issues]}")
    assert code == 0, (err, issues)
    assert not [i for i in issues if i["code"].startswith("netlist.")]
    drc = stage(env, "drc.kicad")
    assert drc["status"] == "ok" and drc["summary"]["violations_judged"] is True
    assert drc["summary"]["unconnected"] == 0
    assert not [kind for kind in drc["summary"]["by_type"] if kind in LIBRARY_TYPES]
    assert not [i for i in issues if any(kind.replace("_", "-") in i["code"] for kind in LIBRARY_TYPES)]
    nets = stage(env, "netlist.assignment_compare")
    assert nets["status"] == "ok"
    pairs = {(p["a"], p["b"]): p for p in nets["summary"]["pairs"]}
    for key in (("model", "board"), ("board", "export")):
        assert (pairs[key]["common"], pairs[key]["differences"]) == (6, 0), key
        assert (pairs[key]["only_a"], pairs[key]["only_b"]) == (0, 0), key
    assert stage(env, "parity")["status"] == "ok"
    print(f"drc by_type {drc['summary']['by_type']}, refs {REFS}")


@pytest.mark.parametrize("target", TARGETS)
def test_control_without_the_fields_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    supported_version()
    with monkeypatch.context() as patch:
        # the state before c0077: prepared definitions get no field, and a placement adds none
        patch.setattr(embed, "default_fields", lambda defn: ())
        out = built(monkeypatch, tmp_path, target)
    code, env, _ = run(monkeypatch, "check", str(out), "--kicad-cli", cli())
    found = sorted({i["code"] for i in env["issues"] if i["severity"] == "error"})
    print(f"target {target}: exit {code}, errors {found}")
    assert code == 5
    assert any(c.startswith("netlist.") for c in found)
