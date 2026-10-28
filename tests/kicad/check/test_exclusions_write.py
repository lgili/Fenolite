# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check BOARD --exclude CODE:ITEM_A:ITEM_B --reason TEXT`` against the running ``kicad-cli``
(change c0209; capability kicad-oracle, "DRC exclusions written"; ``H-K-DRC-EXCLUSION``).

One bench, written for the running major: two tracks of ``SIG`` 1 mm apart (one unconnected item, whose
marker sits at the end of the ratsnest line and not at either reported position), two 0.25 mm tracks 0.1
mm apart (a clearance), pad 1 of ``R1`` and of ``R2`` on ``J`` with no track (an unconnected pad pair),
and a lone via (an entry of one item).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from functools import cache
from pathlib import Path
from typing import Any

import _rulebench as rb
import pytest
from _checkrun import check, cli_path, stage
from _probes import major, runner

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.exclusions import mirrored_keys
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point

pytestmark = pytest.mark.needs_kicad

BOARD, PROJECT = "bench.kicad_pcb", "bench.kicad_pro"
REASON = "joined by the test fixture"
LOW_UUID = "00000001-0000-4000-8000-0000000c0209"
"""A uuid that sorts before every uuid of the bench."""


@cache
def bench() -> rb.Bench:
    made = rb.Builder()
    y = made.row()
    made.track("t1", "SIG", y, x0=10_000_000, x1=15_000_123)
    made.track("t2", "SIG", y, x0=16_000_457, x1=20_000_000)
    made.pair("close", "A", "B", gap=100_000)
    y = made.row()
    made.part("r1", "R1", Point(12 * rb.MM, y), target=major(), nets={"1": "J"})
    made.part("r2", "R2", Point(18 * rb.MM, y), target=major(), nets={"1": "J"})
    made.via("via", "TP", Point(30_123_456, y))
    return made.build()


def board_text() -> str:
    return write_board(bench().design, target=major()).text


def folder(root: Path, *, project: str | None = "{}\n", text: str | None = None) -> Path:
    (root / BOARD).write_text(text if text is not None else board_text(), encoding="utf-8")
    if project is not None:
        (root / PROJECT).write_text(project, encoding="utf-8")
    return root


def exclude(root: Path, spec: str, *protocol: str, reason: str = REASON) -> tuple[int, dict[str, Any], str]:
    command = [sys.executable, "-m", "fenolite", "check", str(root / BOARD), "--kicad-cli", cli_path(),
               "--exclude", spec, "--reason", reason, *protocol, "--json"]  # fmt: skip
    run = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=900, check=False)
    envelope: dict[str, Any] = json.loads(run.stdout) if run.stdout.strip() else {}
    return run.returncode, envelope, run.stderr


def stored(root: Path) -> list[Any]:
    data = json.loads((root / PROJECT).read_text(encoding="utf-8"))
    return data["board"]["design_settings"]["drc_exclusions"]


def drc(root: Path, project: str | None = None, text: str | None = None) -> DrcReport:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp)
        (copy / BOARD).write_text(text if text is not None else (root / BOARD).read_text("utf-8"), "utf-8")
        (copy / PROJECT).write_text(project if project is not None else (root / PROJECT).read_text("utf-8"))
        found = runner().drc(copy / BOARD, files={PROJECT: copy / PROJECT}).report
    assert found is not None
    return found


def entries(report: DrcReport, kind: str, *uuids: str) -> list[DrcViolation]:
    wanted = set(uuids)
    return [
        v
        for v in (*report.violations, *report.unconnected_items)
        if v.type == kind and {item.uuid for item in v.items} == wanted
    ]


def test_accepted_unconnected_item(tmp_path: Path) -> None:
    """Scenario "An accepted unconnected item": the exclusion is written in both orders at the marker
    position, the finding is excluded with the reason, and the check lists the exclusion as live."""
    root = folder(tmp_path)
    (t1,), (t2,) = bench().uuids("t1"), bench().uuids("t2")
    code, env, stderr = exclude(root, f"kicad.drc.unconnected-items:{t2}:{t1}", "--confirm")
    assert code == 0, stderr
    row = env["result"]["exclusion"]
    assert row["position"] == {"x": 15_000_123, "y": rb.FIRST_ROW}  # the end of t1, not a reported position
    keys = list(mirrored_keys("unconnected_items", Point(15_000_123, rb.FIRST_ROW), t1, t2))
    assert row["keys"] == keys and stored(root) == [[key, REASON] for key in keys]
    assert env["receipt"]["written"][0]["path"] == PROJECT
    (entry,) = entries(drc(root), "unconnected_items", t1, t2)
    assert entry.excluded and entry.comment == REASON
    _, env, _, stderr = check(root, "--stages", "drc.kicad")
    assert env, stderr
    summary = stage(env, "drc.kicad")["summary"]
    assert summary["exclusions"] == {"stored": 2, "live": 2, "stale": 0, "unjudged": 0}
    (accepted,) = summary["accepted"]
    assert accepted["type"] == "unconnected_items" and accepted["state"] == "live"
    assert accepted["comment"] == REASON and set(accepted["items"]) == {t1, t2}
    (finding,) = [i for i in env["issues"] if i["code"] == "kicad.drc.unconnected-items"
                  and i["message"].endswith(f"(excluded in the project: {REASON})")]  # fmt: skip
    assert finding["severity"] == "info"


def _applies(root: Path, keys: list[str], text: str, kind: str, *uuids: str) -> bool:
    project = json.dumps({"board": {"design_settings": {"drc_exclusions": [[k, "x"] for k in keys]}}})
    (entry,) = entries(drc(root, project, text), kind, *uuids)
    return entry.excluded


def test_unconnected_key_applies_in_either_order(tmp_path: Path) -> None:
    """At the marker position, a key of a missing connection applies in either order of its two uuids,
    whatever uuid sorts first; the report lists the tracks in board order."""
    (t1,), (t2,) = bench().uuids("t1"), bench().uuids("t2")
    at = Point(15_000_123, rb.FIRST_ROW)
    for second, text in ((t2, board_text()), (LOW_UUID, board_text().replace(t2, LOW_UUID))):
        (entry,) = entries(drc(tmp_path, "{}", text), "unconnected_items", t1, second)
        assert [item.uuid for item in entry.items] == [t1, second]
        for key in mirrored_keys("unconnected_items", at, t1, second):
            assert _applies(tmp_path, [key], text, "unconnected_items", t1, second), key


def test_clearance_key_keeps_the_report_order(tmp_path: Path) -> None:
    """A clearance key applies only in the report's order at the first item's position; with the second
    track's uuid made the lowest, the report names it first and only the key from its position applies."""
    (a,), (b,) = bench().uuids("close_a"), bench().uuids("close_b")
    for first, second, text in ((a, b, board_text()), (LOW_UUID, a, board_text().replace(b, LOW_UUID))):
        (entry,) = entries(drc(tmp_path, "{}", text), "clearance", first, second)
        assert [item.uuid for item in entry.items] == [first, second]
        at = entry.items[0].position
        other = entry.items[1].position
        applied = {
            (where, order): _applies(tmp_path, [key], text, "clearance", first, second)
            for where, point in (("first", at), ("second", other))
            for order, key in zip(
                ("report", "other"), mirrored_keys("clearance", point, first, second), strict=True
            )
        }
        assert applied == {("first", "report"): True, ("first", "other"): False,
                           ("second", "report"): False, ("second", "other"): False}  # fmt: skip


def test_pad_pair_by_name_and_clearance(tmp_path: Path) -> None:
    """Items named as the finding's ``where`` prints them: an unconnected pad pair and a clearance pair."""
    root = folder(tmp_path)
    code, env, stderr = exclude(root, "unconnected_items:R1-1:R2-1", "--confirm")
    assert code == 0, stderr
    pads = (*bench().uuids("r1:1"), *bench().uuids("r2:1"))
    (entry,) = entries(drc(root), "unconnected_items", *pads)
    assert entry.excluded and entry.comment == REASON
    (a,), (b,) = bench().uuids("close_a"), bench().uuids("close_b")
    code, env, stderr = exclude(root, f"clearance:{b}:{a}", "--confirm", reason="accepted gap")
    assert code == 0, stderr
    (pair,) = entries(drc(root), "clearance", a, b)
    assert pair.excluded and pair.comment == "accepted gap"
    assert len(stored(root)) == 4
    code, env, _ = exclude(root, f"clearance:{a}:{b}", "--confirm", reason="accepted gap")
    assert code == 0 and env["receipt"] is None
    assert [i["code"] for i in env["issues"]] == ["check.exclusion-present"]


def test_one_item_entry(tmp_path: Path) -> None:
    root = folder(tmp_path, project=None)
    (via,) = bench().uuids("via")
    code, env, stderr = exclude(root, f"kicad.drc.via-dangling:{via}", "--confirm")
    assert code == 0, stderr
    assert len(env["result"]["exclusion"]["keys"]) == 1 and len(stored(root)) == 1
    (entry,) = entries(drc(root), "via_dangling", via)
    assert entry.excluded and entry.comment == REASON


def test_unmatched_and_dry_run_write_nothing(tmp_path: Path) -> None:
    root = folder(tmp_path)
    (t1,), (via,) = bench().uuids("t1"), bench().uuids("via")
    code, env, _ = exclude(root, f"clearance:{t1}:{via}", "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["check.exclusion-unmatched"]
    code, env, _ = exclude(root, f"via_dangling:{via}", "--dry-run")
    assert code == 0 and env["result"]["plan"][0]["path"] == PROJECT
    assert (root / PROJECT).read_text(encoding="utf-8") == "{}\n"
