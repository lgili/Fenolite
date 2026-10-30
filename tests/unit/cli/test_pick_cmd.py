# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite pick`` (change c0254; cli-contract, "Pick command", "Pick listing", "Pick updates")."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "picks"
ROWS = (
    "id,kind,value,footprint,case,tolerance,dielectric,voltage,mpn\n"
    "Vendor:C1,capacitor,10uF,Fenolite:Chip_0805,0805,10%,X7R,25V,ABC-1\n"
    "Vendor:C2,capacitor,10uF,Fenolite:Chip_1206,1206,20%,X5R,35V,ABC-2\n"
    "Vendor:C3,capacitor,10uF,Fenolite:Chip_0805,0805,10%,X7R,50V,ABC-3\n"
)


def _stale(tmp_path: Path) -> Path:
    work = tmp_path / "picks"
    shutil.copytree(EXAMPLE, work)
    script = work / "design.py"
    script.write_text(
        script.read_text(encoding="utf-8").replace("rating=volt(25)", "rating=volt(50)"), encoding="utf-8"
    )
    return work


def test_the_example_lists_its_picks(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, err, _ = run(monkeypatch, ROOT, "pick", "examples/picks")
    assert code == 0, err
    assert {pick["state"] for pick in env["result"]["picks"]} == {"ok"} and "plan" not in env["result"]
    assert env["evidence"]["level"] == "UNKNOWN"  # the illustrative project family is labelled UNKNOWN


def test_a_stale_pick_is_listed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _stale(tmp_path)
    code, env, _, _ = run(monkeypatch, work, "pick", ".")
    assert code == 5
    states = {pick["path"]: pick["state"] for pick in env["result"]["picks"]}
    assert states["C_in"] == "stale"


def test_update_a_stale_pick(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _stale(tmp_path)
    code, env, err, _ = run(monkeypatch, work, "pick", ".", "--update", "C_in", "--dry-run")
    assert code == 0, err
    assert env["result"]["updates"] == [
        {"path": "C_in", "before": "Example:C_0805_X7R_25V@10u", "after": "Example:C_0805_X7R_50V@10u"}
    ]
    assert [Path(item["path"]).name for item in env["result"]["plan"]] == ["design.lock"]
    plan = env["result"]["plan_id"]
    code, env, err, _ = run(monkeypatch, work, "pick", ".", "--update", "C_in", "--confirm", "--plan", plan)
    assert code == 0, err
    written = env["receipt"]["written"]
    assert [Path(item["path"]).name for item in written] == ["design.lock"] and written[0]["sha256"]
    code, env, err, _ = run(monkeypatch, work, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 0, err
    assert not [issue for issue in env["issues"] if issue["code"] == "pick.stale"]


def test_unknown_update_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _stale(tmp_path)
    code, _, err, _ = run(monkeypatch, work, "pick", ".", "--update", "R99", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, err, _ = run(
        monkeypatch, ROOT, "pick", "examples/picks", "--candidates", "buck1/FB_top", "--limit", "3"
    )
    assert code == 0, err
    result = env["result"]
    assert len(result["candidates"]) == 3 and result["page"]["total"] > 3
    assert all(item["row"] == "Fenolite:R_0603_E96_1pct" for item in result["candidates"])
    assert any(
        item["failed"].startswith("tolerance") or item["failed"].startswith("case")
        for item in result["excluded"]
    )


def test_proposals_from_a_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = tmp_path / "picks"
    shutil.copytree(EXAMPLE, work)
    (tmp_path / "rows.csv").write_text(ROWS, encoding="utf-8")
    before = (work / "design.lock").read_bytes()
    args = ("pick", "picks", "--propose", "capacitor(10uF, rating>=25V)", "--from", "rows.csv")
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, err
    planned = [item["path"] for item in env["result"]["plan"]]
    assert len(planned) == 3 and all(path.startswith("picks/devices/proposed/") for path in planned)
    assert not (work / "devices" / "proposed").exists()
    code, env, err, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, err
    text = (work / "devices" / "proposed" / "vendor_c1.toml").read_text(encoding="utf-8")
    assert 'evidence = "UNVERIFIED"' in text and "rows.csv, line 2" in text
    assert (work / "design.lock").read_bytes() == before


def test_propose_needs_one_source(monkeypatch: pytest.MonkeyPatch) -> None:
    code, _, err, _ = run(
        monkeypatch, ROOT, "pick", "examples/picks", "--propose", "capacitor(10uF)", "--dry-run"
    )
    assert code == 2 and err["code"] == "FEN-2001"
    code, _, err, _ = run(
        monkeypatch,
        ROOT,
        "pick",
        "examples/picks",
        "--propose",
        "capacitor(10uF)",
        "--supplier",
        "none",
        "--dry-run",
    )
    assert code == 2 and "fenolite.suppliers" in err["message"]


def test_propose_offsite_supplier_needs_allow_offsite(monkeypatch: pytest.MonkeyPatch) -> None:
    class Offsite:
        name = "far"
        sends_data_offsite = True

        def propose(self, query: object) -> list[dict[str, str]]:
            return []

    import fenolite.cli.cmd_pick as cmd_pick

    monkeypatch.setattr(cmd_pick, "suppliers", lambda: {"far": object()})
    monkeypatch.setattr(cmd_pick, "load_supplier", lambda name: Offsite())
    code, _, err, _ = run(
        monkeypatch,
        ROOT,
        "pick",
        "examples/picks",
        "--propose",
        "capacitor(10uF)",
        "--supplier",
        "far",
        "--dry-run",
    )
    assert code == 2 and "--allow-offsite" in err["hint"]
    code, env, err, _ = run(
        monkeypatch, ROOT, "pick", "examples/picks", "--propose", "capacitor(10uF)", "--supplier", "far",
        "--allow-offsite", "--dry-run",
    )  # fmt: skip
    assert code == 0, err
    assert env["result"]["proposed"] == []
