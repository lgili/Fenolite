# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Waivers end to end against the running ``kicad-cli`` (capability verification-loop, "Waivers in the
check"; change c0114, task 3.5).

The routed blink is built with an authored net tie whose two pads overlap, a via in one of its pads that
stands for a test point, and a class clearance above the pad pitch of its controller. The script accepts
the via (``kicad.drc.via-dangling``), the pads (``copper.clearance``) and KiCad's own entries for the same
copper (``kicad.drc.clearance``). ``fenolite check`` then has no error left in the two stages that a waiver
reaches, and lists every accepted finding as ``info``; without the via, the waiver that named it is
reported as stale.

The check runs the stages ``copper.clearance`` and ``drc.kicad``: the two that take waivers. The whole
default pipeline cannot exit 0 on this project before change c0077, because the board footprint of an
authored definition has no ``Reference`` until then (``netlist.assignment_compare`` reports its pads).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkrun import check, stage
from _probes import major
from _routed import Routed
from _waivercases import (
    ANCHOR,
    ESCAPE,
    NET_TIE_TOUCHING,
    PITCH,
    PITCH_11,
    PITCH_11_NAME,
    TEST_POINT,
    plant,
    tight,
)

pytestmark = pytest.mark.needs_kicad
STAGES = ("--stages", "copper.clearance,drc.kicad")
VIA = 'design.via("tp", mm(26.3), mm(18), net=nt1_a, diameter=mm(0.6), drill=mm(0.3))\n'
"""A through via in pad 1 of the net tie, on that pad's net: it joins copper on one layer only, which is
``via_dangling`` in KiCad's DRC, and it is 0.3 mm from pad 2."""
TWIN = 'design.waive("kicad.drc.clearance", "U1-*", "*", reason="fixed by the pitch", name="pitch-kicad")\n'
"""KiCad's entries for the copper that the three copper waivers accept."""


def codes(env: dict[str, object], severity: str) -> list[str]:
    return sorted(i["code"] for i in env["issues"] if i["severity"] == severity)  # type: ignore[index, union-attr]


def test_waivers_accept_the_findings_and_report_a_stale_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    routed = Routed(tmp_path, monkeypatch, target=major(), confirm=False)
    plant(routed, NET_TIE_TOUCHING, VIA)
    tight(routed, PITCH, PITCH_11, ESCAPE, TWIN, TEST_POINT)
    # the stitching vias of the example join copper on one layer too: without them the test point is
    # the only via that the waiver's ``*`` can name
    text = routed.script.read_text(encoding="utf-8")
    routed.script.write_text(text[: text.index(ANCHOR)], encoding="utf-8")
    code, env, err = routed.build("--confirm")
    assert code == 0, (env.get("issues"), err)
    assert '(net_tie_pad_groups "1, 2")' in routed.board.read_text(encoding="utf-8")

    code, env, _, stderr = check(routed.out, *STAGES)
    assert code == 0, (codes(env, "error"), stderr)
    assert codes(env, "error") == []
    issues = env["issues"]
    waived = [i for i in issues if "(waived by " in i["message"]]
    assert {i["severity"] for i in waived} == {"info"}
    by_code = {code: [i for i in waived if i["code"] == code] for code in {i["code"] for i in waived}}
    assert sorted(by_code) == ["copper.clearance", "kicad.drc.clearance", "kicad.drc.via-dangling"]
    assert len(by_code["copper.clearance"]) == 4 and len(by_code["kicad.drc.via-dangling"]) == 1
    assert by_code["kicad.drc.via-dangling"][0]["message"].endswith("(waived by tp: test point)")
    assert not [i for i in issues if i["code"] == "copper.short"]  # the tied pads are not judged
    assert stage(env, "copper.clearance")["summary"]["net_tie_pairs"] == 1
    waivers = env["result"]["waivers"]
    assert waivers["declared"] == 5 and waivers["unmatched"] == []
    assert waivers["matched"] == {PITCH_11_NAME: 1, "escape": 2, "pitch": 1, "tp": 1}
    assert waivers["unjudged"] == {"pitch-kicad": "not-repeatable"}
    assert not [i for i in issues if i["code"] == "check.waiver-unmatched"]

    routed.edit_script(VIA, "")
    code, env, err = routed.build("--confirm")
    assert code == 0, (env.get("issues"), err)
    code, env, _, stderr = check(routed.out, *STAGES)
    assert code == 0, (codes(env, "error"), stderr)
    (stale,) = [i for i in env["issues"] if i["code"] == "check.waiver-unmatched"]
    assert (stale["severity"], stale["where"]) == ("warning", "tp")
    assert env["result"]["waivers"]["unmatched"] == ["tp"]
    assert not [i for i in env["issues"] if i["code"] == "kicad.drc.via-dangling"]
