# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Picks in ``fenolite build`` (change c0254; part-selection, "Picks resolved by the build", "Changed
queries", "Unverified rows", "Generator results", "Locked generator picks")."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "picks"


def _copy(tmp_path: Path) -> Path:
    work = tmp_path / "picks"
    shutil.copytree(EXAMPLE, work)
    return work


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _build(monkeypatch: pytest.MonkeyPatch, work: Path, script: str, *flags: str) -> tuple[int, dict, dict]:  # type: ignore[type-arg]
    code, env, err, _ = run(monkeypatch, work, "build", script, "--out", "out", *flags)
    return code, env, err


def _targets(env: dict) -> list[str]:  # type: ignore[type-arg]
    return [Path(item["path"]).name for item in env["result"].get("plan", [])]


def test_the_committed_lock_builds_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    code, env, err = _build(monkeypatch, work, "design.py", "--frozen", "--dry-run")
    assert code == 0, err
    states = {pick["path"]: pick["state"] for pick in env["result"]["picks"]}
    assert set(states.values()) == {"ok"} and env["result"]["lock"]["changes"] == []


def test_a_changed_query_is_not_a_silent_swap(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    before = (work / "design.lock").read_bytes()
    _edit(work / "design.py", "rating=volt(25)", "rating=volt(50)")
    code, env, _ = _build(monkeypatch, work, "design.py", "--confirm")
    assert code == 5
    stale = [issue for issue in env["issues"] if issue["code"] == "pick.stale"]
    assert len(stale) == 1 and stale[0]["where"] == "C_in"
    assert "Example:C_0805_X7R_25V@10u" in stale[0]["message"] and "rating>=50V" in stale[0]["message"]
    assert (work / "design.lock").read_bytes() == before and not (work / "out").exists()


def test_a_cosmetic_edit_keeps_the_part(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    _edit(work / "design.py", 'farad("10u")', 'farad("10 uF")')
    code, env, err = _build(monkeypatch, work, "design.py", "--dry-run")
    assert code == 0, err
    assert "design.lock" not in _targets(env)
    devices = {row["id"] for row in env["result"]["devices"]}
    assert "Example:C_0805_X7R_25V@10u" in devices


def test_a_better_match_does_not_replace_a_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    text = (work / "devices" / "caps.toml").read_text(encoding="utf-8")
    better = text.replace("Example:C_0805_X7R_25V", "Example:C_0805_X7R_25V_20").replace('"10%"', '"20%"')
    (work / "devices" / "better.toml").write_text(better, encoding="utf-8")
    code, env, err = _build(monkeypatch, work, "design.py", "--dry-run")
    assert code == 0, err
    assert "design.lock" not in _targets(env)
    picked = {pick["path"]: pick["device"] for pick in env["result"]["picks"]}
    assert picked["C_in"] == "Example:C_0805_X7R_25V@10u"


def test_frozen_refuses_a_new_pick(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    (work / "design.lock").unlink()
    code, _, err = _build(monkeypatch, work, "design.py", "--frozen", "--dry-run")
    assert code == 7 and err["code"] == "FEN-7004"


def test_a_proposal_is_not_picked_by_itself(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    proposed = work / "devices" / "proposed"
    proposed.mkdir()
    (proposed / "x.toml").write_text(
        'schema = "fenolite.device.v0"\nid = "Vendor:CAP10U"\nsummary = "s"\nsymbol = "Fenolite:Capacitor"\n'
        'footprint = "Fenolite:Chip_0805"\nvalue = "10uF"\nkind = "capacitor"\ncase = "0805"\n'
        'tolerance = "20%"\ndielectric = "X7R"\nevidence = "UNVERIFIED"\n\n[pins]\nP1 = "1"\nP2 = "2"\n\n'
        '[ratings]\nvoltage = { max = "25V" }\n',
        encoding="utf-8",
    )
    (work / "design.lock").unlink()
    code, env, err = _build(monkeypatch, work, "design.py", "--dry-run")
    assert code == 0, err
    picked = {pick["path"]: pick["device"] for pick in env["result"]["picks"]}
    assert picked["C_in"] == "Example:C_0805_X7R_25V@10u"
    unverified = [issue for issue in env["issues"] if issue["code"] == "pick.row-unverified"]
    assert len(unverified) == 1 and "Vendor:CAP10U" in unverified[0]["message"]


def test_a_malformed_family(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    _edit(work / "devices" / "caps.toml", 'min = "1u"', 'min = "ten"')
    code, _, err = _build(monkeypatch, work, "design.py", "--confirm")
    assert code == 3 and err["code"] == "FEN-3004"
    named = f"{err.get('where', '')} {err['message']}"
    assert "caps.toml" in named and "values.min" in named
    assert not (work / "out").exists()


def test_results_are_reported_in_one_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    (work / "divider.lock").unlink()
    code, env, err = _build(monkeypatch, work, "divider.py", "--confirm")
    assert code == 0, err
    achieved = [issue["message"] for issue in env["issues"] if issue["code"] == "gen.achieved"]
    generators = env["result"]["generators"]
    assert achieved == [generators[0]["message"]]
    assert "VOUT 3.224694–3.399373 V within 3.135–3.465 V" in achieved[0]
    lock = (work / "divider.lock").read_text(encoding="utf-8")
    assert lock.count(f'"achieved" = "{generators[0]["achieved"]}"') == 2
    assert generators[0]["achieved"] == "VOUT 3224694uV..3399373uV"


def test_a_feedback_divider_with_e96(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    code, env, err = _build(monkeypatch, work, "divider.py", "--dry-run")
    assert code == 0, err
    picked = {pick["path"]: pick["device"] for pick in env["result"]["picks"]}
    assert picked == {
        "buck1/FB_bot": "Fenolite:R_0603_E96_1pct@13k7",
        "buck1/FB_top": "Fenolite:R_0603_E96_1pct@61k9",
    }


def test_unachievable_by_a_hair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    (work / "divider.lock").unlink()
    _edit(work / "divider.py", 'VOUT = volt("3.3").pct(5)', 'VOUT = volt("3.3").pct(3)')
    code, env, _ = _build(monkeypatch, work, "divider.py", "--dry-run")
    assert code == 5 and _targets(env) == []
    message = next(issue["message"] for issue in env["issues"] if issue["code"] == "gen.unachievable")
    assert (
        "61.9kΩ / bottom 13.7kΩ" in message and "3.224694–3.399373 V" in message and "373 µV above" in message
    )


def test_a_tighter_family_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    (work / "divider.lock").unlink()
    _edit(work / "divider.py", 'VOUT = volt("3.3").pct(5)', 'VOUT = volt("3.3").pct(3)')
    _edit(work / "divider.py", '"tolerance": pct(1)', '"tolerance": pct("0.1")')
    (work / "devices" / "r_tight.toml").write_text(
        'schema = "fenolite.family.v0"\nid = "Example:R_0603_E96_0p1pct"\nkind = "resistor"\nsummary = "s"\n'
        'symbol = "Fenolite:Resistor"\nfootprint = "Fenolite:Chip_0603"\ncase = "0603"\nseries = "E96"\n'
        'values = { min = "1k", max = "100k" }\ntolerance = "0.1%"\nevidence = "UNKNOWN"\n',
        encoding="utf-8",
    )
    code, env, err = _build(monkeypatch, work, "divider.py", "--dry-run")
    assert code == 0, err
    message = next(issue["message"] for issue in env["issues"] if issue["code"] == "gen.achieved")
    assert "top 61.9kΩ, bottom 13.7kΩ" in message and "VOUT 3.272477–3.34954 V" in message


def test_a_wider_target_keeps_the_pair(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work = _copy(tmp_path)
    _edit(work / "divider.py", 'VOUT = volt("3.3").pct(5)', 'VOUT = volt("3.3").pct(6)')
    code, env, err = _build(monkeypatch, work, "divider.py", "--confirm")
    assert code == 0, err
    assert any(issue["code"] == "pick.query-changed" for issue in env["issues"])
    lock = (work / "divider.lock").read_text(encoding="utf-8")
    assert "3.3V (3.102V..3.498V)" in lock and "Fenolite:R_0603_E96_1pct@61k9" in lock
