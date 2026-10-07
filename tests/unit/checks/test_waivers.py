# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Waivers in the check (capability verification-loop, "Waivers in the check"; change c0114).

The matching, the effect on an issue and the judged and unjudged waivers are tested on ``checks.waivers``
and on the stages with fakes. The command scenarios build the routed blink with a tighter class and run
``fenolite check`` on the built project, for both targets; no tool runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _altium_drc import build_altium, cli, coded, stages
from _coppercheck import Copper, mm
from _routed import Routed
from _waivercases import ESCAPE, ESCAPE_STRICT, PITCH, PITCH_11, PITCH_11_NAME, TEST_POINT, tight
from fakes import FakeOracle, FakeRulesValidator, outcome, project, report, validation, violation

from fenolite.checks import run_checks
from fenolite.checks.codes import ISSUE_CODES, issue
from fenolite.checks.copper import STAGE, check_copper, waived_issues
from fenolite.checks.drc import drc_stage
from fenolite.checks.waivers import (
    COPPER_CODES,
    NOT_REPEATABLE,
    STAGE_NOT_RUN,
    UNMATCHED,
    UNREPEATABLE_TYPES,
    Candidate,
    WaiverOutcome,
    apply_waivers,
    combine,
    copper_waivers,
    drc_waivers,
    judge,
    waiver_matches,
)
from fenolite.core.coords import Point
from fenolite.model.design import Design
from fenolite.model.findings import Waiver

REASON = "fixed by the mating connector"


def waiver(code: str, *items: str, name: str = "w", min_gap: int | None = None) -> Waiver:
    return Waiver(name=name, code=code, items=items, reason=REASON, min_gap=min_gap)


# --- matching -------------------------------------------------------------------------------------


def test_matching_items_in_either_order() -> None:
    """Scenario "Items match in either order"."""
    pitch = waiver("copper.clearance", "J1-3", "J1-4")
    assert waiver_matches(pitch, "copper.clearance", ("J1-4", "J1-3")) is True
    assert waiver_matches(pitch, "copper.clearance", ("J1-3", "J1-4")) is True
    assert waiver_matches(pitch, "copper.clearance", ("J1-3",)) is False
    assert waiver_matches(pitch, "copper.clearance", ("J1-3", "J1-5")) is False
    assert waiver_matches(pitch, "copper.short", ("J1-3", "J1-4")) is False


def test_matching_is_one_to_one_and_by_glob() -> None:
    both = waiver("copper.clearance", "J1-*", "*", min_gap=100_000)
    assert waiver_matches(both, "copper.clearance", ("/kicad_pcb/segment[4]", "J1-3"), 100_000)
    assert not waiver_matches(both, "copper.clearance", ("R1-1", "R2-1"), 100_000)
    twice = waiver("copper.short", "A", "A")
    assert waiver_matches(twice, "copper.short", ("A", "A")) and not waiver_matches(
        twice, "copper.short", ("A", "B")
    )
    case = waiver("kicad.drc.via-dangling", "@12.[05],3")
    assert waiver_matches(case, "kicad.drc.via-dangling", ("@12.5,3",))
    assert not waiver_matches(waiver("kicad.drc.x", "r1"), "kicad.drc.x", ("R1",))  # case matters
    # a locator holds brackets, which a glob reads as a set: the same text names it too
    track = waiver("copper.clearance", "/kicad_pcb/segment[12]", "J1-3")
    assert waiver_matches(track, "copper.clearance", ("J1-3", "/kicad_pcb/segment[12]"))
    assert not waiver_matches(track, "copper.clearance", ("J1-3", "/kicad_pcb/segment[13]"))


def test_matching_min_gap() -> None:
    bound = waiver("copper.clearance", "J1-3", "*", min_gap=150_000)
    assert not waiver_matches(bound, "copper.clearance", ("J1-3", "t"), 120_000)
    assert waiver_matches(bound, "copper.clearance", ("J1-3", "t"), 150_000)
    assert waiver_matches(bound, "copper.clearance", ("J1-3", "t"), 160_000)
    assert not waiver_matches(bound, "copper.clearance", ("J1-3", "t"))  # a finding without a gap


# --- the effect on an issue -----------------------------------------------------------------------


def candidate(code: str, *names: str, gap: int | None = None, severity: str = "error") -> Candidate:
    made = issue(code, f"finding of {code}", severity=severity, where=", ".join(names))  # type: ignore[arg-type]
    return Candidate(made, names, gap)


def test_effect_on_the_issue() -> None:
    first = waiver("copper.clearance", "A", "B", name="b-second")
    second = waiver("copper.clearance", "*", "B", name="a-first", min_gap=1)
    kept = candidate("copper.clearance", "C", "D", gap=5)
    issues, counts = apply_waivers([first, second], [candidate("copper.clearance", "B", "A", gap=5), kept])
    assert issues[0].code == "copper.clearance" and issues[0].where == "B, A"
    assert issues[0].severity == "info"
    assert issues[0].message == f"finding of copper.clearance (waived by a-first: {REASON})"
    assert issues[1] is kept.issue  # no waiver matches: unchanged, and nothing is removed
    assert counts == {"a-first": 1, "b-second": 1}  # every waiver that matches counts the finding


def test_effect_keeps_a_warning_finding_listed() -> None:
    overlap = candidate("copper.zone-overlap", "z1", "z2", severity="warning")
    (found,), counts = apply_waivers([waiver("copper.zone-overlap", "z?", "z?")], [overlap])
    assert found.severity == "info" and counts == {"w": 1}
    for code in COPPER_CODES:
        assert "info" in ISSUE_CODES[code]


def test_families() -> None:
    mixed = [waiver("copper.short", "a", "b", name="c"), waiver("kicad.drc.via-dangling", "*", name="d")]
    assert [w.name for w in copper_waivers(mixed)] == ["c"]
    assert [w.name for w in drc_waivers(mixed, "kicad")] == ["d"] and drc_waivers(mixed, "fake") == ()


# --- judged and unjudged waivers ------------------------------------------------------------------


def test_judge_matched_unmatched_and_unrepeatable() -> None:
    waivers = [
        waiver("fake.drc.silk-overlap", "*", name="silk"),
        waiver("fake.drc.clearance", "*", "*", name="clr"),
        waiver("fake.drc.via-dangling", "*", name="via"),
    ]
    verdict, issues = judge(waivers, {"via": 2, "clr": 1}, unrepeatable={"fake.drc.clearance"})
    assert verdict == WaiverOutcome(3, {"via": 2}, ("silk",), {"clr": NOT_REPEATABLE})
    (stale,) = issues
    assert (stale.code, stale.severity, stale.where) == (UNMATCHED, "warning", "silk")
    assert "fake.drc.silk-overlap" in stale.message and "gone or its items were renamed" in stale.message
    assert verdict.to_json() == {
        "declared": 3,
        "matched": {"via": 2},
        "unmatched": ["silk"],
        "unjudged": {"clr": "not-repeatable"},
    }


def test_combine_marks_the_waivers_no_stage_listed() -> None:
    waivers = [waiver("copper.short", "a", "b", name="s"), waiver("kicad.drc.x", "*", name="x")]
    one = {"matched": {"s": 1}, "unmatched": [], "unjudged": {}}
    assert combine(waivers, [one, None, "skipped"]).to_json() == {
        "declared": 2,
        "matched": {"s": 1},
        "unmatched": [],
        "unjudged": {"x": STAGE_NOT_RUN},
    }
    assert combine((), []).to_json() == {"declared": 0, "matched": {}, "unmatched": [], "unjudged": {}}


# --- the copper stage -----------------------------------------------------------------------------


def near_tracks(edge_gap: int) -> Design:
    made = Copper()
    made.netclass("Default", mm(0.2))
    made.track("A", Point(0, 0), Point(mm(10), 0), locator="segment[0]")
    made.track("B", Point(0, 250_000 + edge_gap), Point(mm(10), 250_000 + edge_gap), locator="segment[1]")
    return made.build()


def copper_run(design: Design, *waivers: Waiver, stages_: tuple[str, ...] = (STAGE,)):  # noqa: ANN201
    validator = FakeRulesValidator(result=validation(design))
    return run_checks(
        project=project(),
        stages=stages_,
        model=None,
        built=True,
        validator=validator,
        oracle=None,
        waivers=waivers,
    )


def test_copper_stage_gap_bound_keeps_a_closer_finding() -> None:
    """Scenario "The gap bound keeps a closer finding"."""
    bound = waiver("copper.clearance", "segment[0]", "*", name="bound", min_gap=150_000)
    close = copper_run(near_tracks(120_000), bound)
    (stage,) = close.stages
    assert stage.status == "errors"
    assert [(i.code, i.severity) for i in stage.issues] == [
        (UNMATCHED, "warning"),
        ("copper.clearance", "error"),
    ]
    assert close.waivers == {"declared": 1, "matched": {}, "unmatched": ["bound"], "unjudged": {}}
    far = copper_run(near_tracks(160_000), bound)
    (stage,) = far.stages
    (found,) = stage.issues
    assert stage.status == "ok" and found.severity == "info"  # every error was waived
    assert found.message.endswith(f"(waived by bound: {REASON})") and found.where == "segment[0], segment[1]"
    assert stage.summary["waivers"] == {"matched": {"bound": 1}, "unmatched": [], "unjudged": {}}
    assert stage.summary["clearance"] == 1  # the count of findings does not change
    assert far.waivers["matched"] == {"bound": 1}


def test_copper_stage_reports_a_stale_waiver() -> None:
    """Scenario "A stale waiver is reported"."""
    stale = waiver("copper.short", "R1-1", "R2-1", name="tie")
    report_ = copper_run(near_tracks(mm(1)), stale)
    (found,) = report_.issues
    assert (found.code, found.severity, found.where) == (UNMATCHED, "warning", "tie")
    assert report_.stages[0].status == "ok" and report_.waivers["unmatched"] == ["tie"]


def test_copper_stage_without_waivers_has_no_summary_entry() -> None:
    report_ = copper_run(near_tracks(120_000))
    assert "waivers" not in report_.stages[0].summary
    assert report_.waivers == {"declared": 0, "matched": {}, "unmatched": [], "unjudged": {}}
    design = near_tracks(120_000)
    plain = check_copper(design, pads=None)
    assert waived_issues(plain, ())[0] == plain.issues  # no waiver: the report's own issues


def test_copper_evidence_is_not_changed_by_a_waiver() -> None:
    bound = waiver("copper.clearance", "segment[0]", "segment[1]")
    with_waiver = copper_run(near_tracks(120_000), bound).stages[0]
    without = copper_run(near_tracks(120_000)).stages[0]
    assert with_waiver.evidence == without.evidence


# --- the DRC stage --------------------------------------------------------------------------------


def test_drc_stage_waives_a_finding_by_its_location() -> None:
    drc = report(violation("via_dangling", "warning"), violation("silk_overlap", "warning", uid="u2"))
    dangling = waiver("fake.drc.via-dangling", "@0,0", name="tp")
    result = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True, waivers=[dangling])
    by_code = {found.code: found for found in result.issues}
    assert by_code["fake.drc.via-dangling"].severity == "info"
    assert by_code["fake.drc.via-dangling"].message.endswith(f"(waived by tp: {REASON})")
    assert by_code["fake.drc.silk-overlap"].severity == "warning"
    assert result.summary["waivers"] == {"matched": {"tp": 1}, "unmatched": [], "unjudged": {}}
    assert result.summary["violations"] == 2


def test_drc_stage_unrepeatable_and_unrun_waivers_are_not_judged() -> None:
    """Scenario "Unrepeatable and unrun waivers are not judged"."""
    clearance = waiver("fake.drc.clearance", "*", "*", name="clr")
    silk = waiver("fake.drc.silk-overlap", "*", name="silk")
    oracle = FakeOracle(outcome("fired", drc=report()))
    validator = FakeRulesValidator(result=validation(near_tracks(mm(1))))
    first = run_checks(
        project=project(),
        stages=("drc.kicad",),
        model=None,
        built=True,
        validator=validator,
        oracle=oracle,
        waivers=(clearance, silk),
    )
    assert [(i.code, i.where) for i in first.issues if i.code == UNMATCHED] == [(UNMATCHED, "silk")]
    assert first.waivers == {
        "declared": 2,
        "matched": {},
        "unmatched": ["silk"],
        "unjudged": {"clr": NOT_REPEATABLE},
    }
    second = copper_run(near_tracks(mm(1)), clearance, silk)
    assert not [i for i in second.issues if i.code == UNMATCHED]
    assert second.waivers["unjudged"] == {"clr": STAGE_NOT_RUN, "silk": STAGE_NOT_RUN}


def test_drc_stage_applies_an_unrepeatable_waiver_that_matches() -> None:
    drc = report(violation("clearance"))
    clearance = waiver("fake.drc.clearance", "*", name="clr")
    result = drc_stage(FakeOracle(outcome("fired", drc=drc)), project(), built=True, waivers=[clearance])
    (found,) = result.issues
    assert found.severity == "info" and result.status == "ok"
    assert result.summary["waivers"] == {"matched": {}, "unmatched": [], "unjudged": {"clr": NOT_REPEATABLE}}


def test_drc_stage_without_a_report_judges_no_waiver() -> None:
    silk = waiver("fake.drc.silk-overlap", "*", name="silk")
    result = drc_stage(FakeOracle(outcome(missing=True)), project(), built=True, waivers=[silk])
    assert "waivers" not in result.summary and not [i for i in result.issues if i.code == UNMATCHED]


def test_unrepeatable_types() -> None:
    assert UNREPEATABLE_TYPES == ("clearance", "hole_clearance", "unconnected_items", "shorting_items")


# --- the command, on a built project of each target -----------------------------------------------


def test_command_pads_waived_on_a_built_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Waived clearance between two pads": two pads 0.25 mm apart under a class clearance of
    0.3 mm, accepted by the waiver ``pitch`` of the script."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    tight(routed, PITCH, PITCH_11, ESCAPE)
    code, env, err = routed.build("--confirm")
    assert code == 0, (coded(env, "copper.clearance"), err)
    code, env, _ = cli(routed, "check", str(routed.out), "--stages", "copper.clearance")
    assert code == 0
    found = {i["where"]: i for i in coded(env, "copper.clearance")}
    assert len(found) == 4 and {i["severity"] for i in found.values()} == {"info"}
    assert found["U1-10, U1-9"]["message"].endswith("(waived by pitch: fixed by the package pitch)")
    assert env["result"]["waivers"] == {
        "declared": 3,
        "matched": {PITCH_11_NAME: 1, "escape": 2, "pitch": 1},
        "unmatched": [],
        "unjudged": {},
    }
    assert stages(env)["copper.clearance"]["status"] == "ok"


def test_command_gap_bound_and_stale_waiver(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A bound above the gap keeps the two pad-to-track findings errors: the build refuses, and in warn
    mode ``check`` reports them and the waiver that matched nothing."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    tight(routed, PITCH, PITCH_11, ESCAPE_STRICT)
    code, env, _ = routed.build("--confirm")
    assert code == 5 and len([i for i in coded(env, "copper.clearance") if i["severity"] == "error"]) == 2
    code, env, _ = routed.build("--copper-check", "warn", "--confirm")
    assert code == 0
    code, env, _ = cli(routed, "check", str(routed.out), "--stages", "copper.clearance")
    assert code == 5
    severities = sorted(i["severity"] for i in coded(env, "copper.clearance"))
    assert severities == ["error", "error", "info", "info"]
    (stale,) = coded(env, UNMATCHED)
    assert (stale["severity"], stale["where"]) == ("warning", "escape")
    assert env["result"]["waivers"]["unmatched"] == ["escape"]


def test_command_altium_project_takes_the_same_waivers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "A waiver on a built Altium project": the copper waivers apply as on KiCad, and a DRC
    waiver is listed as ``stage-not-run``, because that pipeline has no DRC stage."""
    routed = Routed(tmp_path, monkeypatch, confirm=False)
    tight(routed, PITCH, PITCH_11, ESCAPE, TEST_POINT)
    code, env, err = build_altium(routed, "--confirm")
    assert code == 0, (env.get("issues"), err)
    code, env, _ = cli(routed, "check", str(routed.out), "--stages", "copper.clearance")
    assert code == 0
    found = {i["where"]: i for i in coded(env, "copper.clearance")}
    assert len(found) == 4 and {i["severity"] for i in found.values()} == {"info"}
    assert found["U1-10, U1-9"]["message"].endswith("(waived by pitch: fixed by the package pitch)")
    waivers = env["result"]["waivers"]
    assert waivers["declared"] == 4 and waivers["matched"]["pitch"] == 1 and waivers["unmatched"] == []
    assert waivers["unjudged"] == {"tp": STAGE_NOT_RUN}
    assert "exclusions" not in stages(env)["copper.clearance"]["summary"]
