# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper guard of ``fenolite build --target altium`` (capability altium-build, "Copper guard in an
Altium build"; change c0088): the PCB document that the build is about to write is read back and judged
with ``checks.copper``; a short refuses the build, a clearance finding is reported."""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium_drc import CROSSING, DOCUMENT, NEAR, build_altium, coded, plant
from _routed import Routed

from fenolite.cli.cmd_build import CLEARANCE_NOTE, WARN_NOTE, altium_copper_guard


def test_altium_guard_passes_the_routed_blink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, env, err = build_altium(routed, "--confirm")
    assert code == 0, (env.get("issues"), err)
    check = env["result"]["copper_check"]
    assert (check["mode"], check["ran"], check["shorts"], check["clearance"]) == ("refuse", True, 0, 0)
    assert check["unpoured"] == 0 and check["rules"]["opaque_clearance_rules"] == 0
    assert check["evidence"]["level"] == "INFERRED"
    assert not [found for found in env["issues"] if found["code"].startswith("copper.")]
    assert (routed.out / DOCUMENT).is_file()


def test_altium_guard_refuses_a_short(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Short refused": exit 5, ``copper.short`` names the nets, and no file is written."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, CROSSING)
    code, env, _ = build_altium(routed, "--confirm")
    assert code == 5
    (short,) = coded(env, "copper.short")
    assert short["severity"] == "error" and "LED_A" in short["message"] and "LED_DRV" in short["message"]
    assert env["result"]["copper_check"]["shorts"] == 1 and env["result"]["files"] == []
    assert not routed.out.exists() or list(routed.out.iterdir()) == []
    # a dry run refuses alike
    code, env, _ = build_altium(routed, "--dry-run")
    assert code == 5 and env["result"]["files"] == [] and not env["result"].get("plan")


def test_altium_guard_in_warn_mode_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, CROSSING)
    code, env, err = build_altium(routed, "--copper-check", "warn", "--confirm")
    assert code == 0, err
    (short,) = coded(env, "copper.short")
    assert short["severity"] == "warning" and short["message"].endswith(WARN_NOTE)
    assert env["result"]["copper_check"]["mode"] == "warn" and (routed.out / DOCUMENT).is_file()


def test_altium_guard_reports_a_clearance_finding_and_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Other copper findings are reported and do not stop the build."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, NEAR)
    code, env, err = build_altium(routed, "--confirm")
    assert code == 0, err
    (near,) = coded(env, "copper.clearance")
    assert near["severity"] == "warning" and near["message"].endswith(CLEARANCE_NOTE)
    assert env["result"]["copper_check"]["clearance"] == 1 and env["result"]["copper_check"]["shorts"] == 0
    assert (routed.out / DOCUMENT).is_file()


def test_altium_guard_without_a_pcb_document() -> None:
    assert altium_copper_guard({}, name="x", mode="refuse") == ((), {"mode": "refuse", "ran": False})
    with pytest.raises(ValueError, match="unknown copper-check mode"):
        altium_copper_guard({}, name="x", mode="off")


def test_altium_guard_unknown_mode_is_a_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    code, _, err = build_altium(routed, "--copper-check", "off", "--dry-run")
    assert code == 2 and "FEN-2001" in err
