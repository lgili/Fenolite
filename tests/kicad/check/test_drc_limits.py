# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The limits of KiCad's DRC report per type, and the mark of ``check`` at them (``H-K-DRC-LIMITS``;
capability kicad-oracle, "DRC report limits are probed"; verification-loop, "DRC report limits in check" and
"Check output is deterministic"; change c0141).

``kicad-cli pcb drc`` stops writing a type at 499 entries (``clearance``, the unconnected items) or 199
(every other type measured), and no key of the report says so. The bench is authored (``_limitsbench.py``),
so both oracle jobs run it without the corpus; ``tests/kicad/test_probe_results.py`` pins the ``drc-limit-*``
outcomes per version. ``test_drc_limit.py`` (c0051) proves another claim, the canary's verdict at the
``clearance`` limit.

The expectations are per major, from what each measured. 9.0.9 writes no ``hole_clearance`` entry for the
bench's construct (a pad beside an unplated hole): its probe is ``different`` there, the count is 0 and
``drc.MEASURED_TYPES[9]`` lacks the type. Its report has nine top-level keys, without ``ignored_checks``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _checkrun import check, stage, without_elapsed
from _limitsbench import (
    ABOVE,
    BELOW,
    BELOW_TYPES,
    REPORT_KEYS,
    TYPES,
    counted,
    limits_project,
    reported_types,
)
from _probes import major, run

from fenolite.backends.kicad.canary import CLEARANCE_REPORT_LIMIT
from fenolite.backends.kicad.drc import MEASURED_TYPES, REPORT_LIMITS

pytestmark = pytest.mark.needs_kicad
MARK = {"type": "track_dangling", "reported": 199, "limit": 199}


@pytest.mark.parametrize("type_", TYPES)
def test_probe_limit_per_type(type_: str) -> None:
    counts, _ = counted("above")
    if type_ not in MEASURED_TYPES[major()]:
        # measured, not a limit: this major writes no entry of the type for the bench's construct
        assert run(f"drc-limit-{type_}") == "different"
        assert (major(), type_, counts.get(type_, 0)) == (9, "hole_clearance", 0), counts
        return
    assert run(f"drc-limit-{type_}") == "equal"
    limit = REPORT_LIMITS[major()].limit(type_)
    if type_ == "clearance" and major() == 9:  # 9.0.9 passes the limit by a few (H-K-DRC-LIMIT)
        assert limit <= counts[type_] < ABOVE, counts
    else:
        assert counts[type_] == limit, counts


def test_probe_no_other_type_and_one_table() -> None:
    counts, _ = counted("above")
    # each construct gives its own type and no other; 9.0.9 gives none for the hole_clearance construct
    assert set(counts) == set(reported_types(major())), counts
    assert set(TYPES) - set(reported_types(major())) == ({"hole_clearance"} if major() == 9 else set())
    assert CLEARANCE_REPORT_LIMIT == REPORT_LIMITS[major()].limit("clearance")


def test_probe_a_type_under_its_limit_is_written_in_full() -> None:
    assert run("drc-limit-below") == "equal"
    counts, _ = counted("below")
    assert {type_: counts[type_] for type_ in BELOW_TYPES} == {type_: BELOW for type_ in BELOW_TYPES}, counts


def test_probe_all_track_errors_does_not_lift_the_limit() -> None:
    assert run("drc-limit-all-track-errors") == "equal"
    assert counted("all-track-errors")[0]["track_dangling"] == counted("above")[0]["track_dangling"]


def test_probe_the_report_has_no_key_for_a_cut() -> None:
    assert run("drc-limit-keys") == "equal"
    assert counted("above")[1] == REPORT_KEYS[major()]
    assert set(REPORT_KEYS[10]) - set(REPORT_KEYS[9]) == {"ignored_checks"}


def _marks(found: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = found["issues"]  # type: ignore[assignment]
    return [i for i in issues if i["code"] == "check.report-limit"]


def test_check_marks_the_bench(tmp_path: Path) -> None:
    root = limits_project(tmp_path / "bench", {"track_dangling": ABOVE})
    code, envelope, _, err = check(root, "--stages", "drc.kicad")
    assert envelope, err
    drc = stage(envelope, "drc.kicad")
    assert drc["summary"]["limits"] == [MARK]
    assert drc["summary"]["by_type"] == {"track_dangling": 199}
    marks = _marks(envelope)
    assert [(m["severity"], m["where"]) for m in marks] == [("warning", "kicad.drc.track-dangling")]
    assert "at least 199" in marks[0]["message"]
    # nothing else moves: 199 warnings and the mark leave the stage ok and the canary as it fired
    assert (code, drc["status"], drc["summary"]["canary"]) == (0, "ok", "fired")


def test_check_below_the_limit_is_complete(tmp_path: Path) -> None:
    root = limits_project(tmp_path / "bench", {"track_dangling": BELOW})
    _, envelope, _, err = check(root, "--stages", "drc.kicad")
    assert envelope, err
    drc = stage(envelope, "drc.kicad")
    assert drc["summary"]["limits"] == [] and drc["summary"]["by_type"] == {"track_dangling": BELOW}
    assert _marks(envelope) == []


def test_check_limits_deterministic(tmp_path: Path) -> None:
    root = limits_project(tmp_path / "bench", {"track_dangling": ABOVE})
    first, second = (check(root, "--stages", "drc.kicad") for _ in range(2))
    assert without_elapsed(first[2]) == without_elapsed(second[2])
    assert stage(first[1], "drc.kicad")["summary"]["limits"] == [MARK]
    assert len(_marks(first[1])) == 1
