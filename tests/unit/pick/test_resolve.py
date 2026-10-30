# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Resolution of query parts against the lock (change c0254, "Picks resolved by the build", "Changed
queries", "Pick package")."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from _picks import family, rows

from fenolite.dsl import capacitor, farad, volt
from fenolite.pick.lockpicks import PickEntry
from fenolite.pick.resolve import resolve

ROOT = Path(__file__).resolve().parents[3]
CAPS = rows(
    family(
        "Proj:C_0805_X7R_25V",
        kind="capacitor",
        case="0805",
        series="E6",
        low="1u",
        high="10u",
        tolerance="10%",
        extra='rating = "25V"\ndielectric = "X7R"\n',
    )  # fmt: skip
)
QUERY = capacitor(farad("10u"), rating=volt(25), case="0805", dielectric="X7R")


def _locked() -> dict[str, PickEntry]:
    first = resolve({"C_in": QUERY}, {}, CAPS)
    assert [found.code for found in first.issues] == ["pick.new"]
    return dict(first.entries)


def test_equal_text_and_hash_keep_the_device() -> None:
    locked = _locked()
    again = resolve({"C_in": QUERY}, locked, CAPS)
    assert again.issues == () and dict(again.entries) == locked and again.changes == ()
    assert again.picks[0].state == "ok" and again.picks[0].entry == locked["C_in"]


def test_a_changed_query_is_not_a_silent_swap() -> None:
    locked = _locked()
    found = resolve(
        {"C_in": capacitor(farad("10u"), rating=volt(50), case="0805", dielectric="X7R")}, locked, CAPS
    )
    assert found.refused and found.picks[0].state == "stale"
    stale = found.issues[0]
    assert (
        stale.code == "pick.stale" and "C_in" in stale.message and "Proj:C_0805_X7R_25V@10u" in stale.message
    )
    assert "rating>=50V" in stale.message and stale.hint == "fenolite pick --update C_in"
    assert dict(found.entries) == locked


def test_a_cosmetic_edit_keeps_the_part() -> None:
    locked = _locked()
    found = resolve(
        {"C_in": capacitor(farad("10 uF"), rating=volt("25.0"), case="0805", dielectric="X7R")}, locked, CAPS
    )
    assert found.changes == () and found.issues == ()


def test_a_query_that_still_matches_keeps_the_device() -> None:
    locked = _locked()
    looser = capacitor(farad("10u"), rating=volt(16), case="0805", dielectric="X7R")
    found = resolve({"C_in": looser}, locked, CAPS)
    assert [i.code for i in found.issues] == ["pick.query-changed"]
    assert (
        found.entries["C_in"].device == locked["C_in"].device and found.entries["C_in"].query == looser.text()
    )


def test_a_better_match_does_not_replace_a_lock() -> None:
    locked = _locked()
    better = rows(
        family(
            "Proj:C_0805_X7R_25V_20pct",
            kind="capacitor",
            case="0805",
            series="E6",
            low="10u",
            high="10u",
            tolerance="20%",
            extra='rating = "25V"\ndielectric = "X7R"\n',
        )  # fmt: skip
    )
    found = resolve({"C_in": QUERY}, locked, (*better, *CAPS))
    assert found.changes == () and found.entries["C_in"] == locked["C_in"]
    updated = resolve({"C_in": QUERY}, locked, (*better, *CAPS), update=frozenset({"C_in"}))
    assert updated.entries["C_in"].device == "Proj:C_0805_X7R_25V_20pct@10u"
    assert updated.changes == (
        ("C_in", "Proj:C_0805_X7R_25V@10u", "Proj:C_0805_X7R_25V_20pct@10u", "updated"),
    )


def test_row_changed_and_row_missing() -> None:
    locked = _locked()
    changed = rows(
        family(
            "Proj:C_0805_X7R_25V",
            kind="capacitor",
            case="0805",
            series="E6",
            low="1u",
            high="10u",
            tolerance="10%",
            extra='rating = "35V"\ndielectric = "X7R"\n',
        )  # fmt: skip
    )
    found = resolve({"C_in": QUERY}, locked, changed)
    assert [i.code for i in found.issues] == ["pick.row-changed"] and found.picks[0].state == "row-changed"
    gone = resolve({"C_in": QUERY}, locked, ())
    assert [i.code for i in gone.issues] == ["pick.row-missing"] and gone.refused


def test_deterministic_picks() -> None:
    script = ROOT / "examples" / "picks" / "divider.py"
    program = (
        "import json, sys\n"
        "from pathlib import Path\n"
        "from fenolite.cli._script import run_design_script\n"
        "from fenolite.cli._picks import query_parts\n"
        "from fenolite.dsl.lock import lock_text, make_lock\n"
        "from fenolite.pick.lockpicks import tables\n"
        "from fenolite.pick.resolve import resolve\n"
        "from fenolite.pick.rows import all_rows\n"
        "path = Path(sys.argv[1])\n"
        "design = run_design_script(path).design\n"
        "found = resolve(query_parts(design), {}, all_rows(path.parent))\n"
        "print(json.dumps([lock_text(make_lock('d', {'picks': tables(found.entries)})), [i.message "
        "for i in found.issues]]))\n"
    )
    outputs = []
    for seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        done = subprocess.run(  # noqa: S603 - the test's own interpreter on the test's own program
            [sys.executable, "-c", program, str(script)], capture_output=True, text=True, env=env, check=True
        )
        outputs.append(json.loads(done.stdout))
    assert outputs[0] == outputs[1]
    assert (
        "Fenolite:R_0603_E96_1pct@61k9" in outputs[0][0] and "Fenolite:R_0603_E96_1pct@13k7" in outputs[0][0]
    )
