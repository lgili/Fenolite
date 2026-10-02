# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Built projects pass the build oracle (capability kicad-oracle, "Built projects pass the build oracle";
hypotheses H-K-BUILD-TRIAD, -CLASS, -LIBTABLE and -PATHPROP; change c0011)."""

from __future__ import annotations

import _buildcases as bc
import pytest
from _build_judge import assert_loaded, baseline_outcome
from _frame import pos_problems, read_pos
from _probes import major, run, runner

from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.parametrize("target", TARGETS)
def test_blink_builds_clean(target: int, tmp_path) -> None:  # noqa: ANN001
    output = bc.built(target)
    files = bc._files(output)  # noqa: SLF001
    assert bc.loads(files, "blink.kicad_pcb")
    tops = bc._folder(files, tmp_path)  # noqa: SLF001
    extra = {k: v for k, v in tops.items() if k != "blink.kicad_pcb"}
    rows = read_pos(runner().export_pos_csv(tmp_path / "blink.kicad_pcb", files=extra))
    assert pos_problems(output.design, rows) == []
    plain, _ = bc.clean(target)
    assert baseline_outcome(plain.report, excepted=bc.BASELINE_EXCEPTIONS) == "absent"
    outcome = run(f"build-canary-t{target}")
    assert_loaded(outcome, "canary")
    assert outcome == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_violated_class(target: int) -> None:
    assert run(f"build-class-t{target}") == "present"


@pytest.mark.parametrize("target", TARGETS)
def test_vendored_table(target: int) -> None:
    outcome = bc.vendored_table(target)
    print(f"KiCad {major()}: vendored table, target {target}: {outcome}")
    if major() >= 10:
        assert outcome == "equal"


@pytest.mark.kicad_min_major(10)
def test_path_property() -> None:
    output = bc.built(10)
    text = bc.upgraded(bc._files(output), "blink.kicad_pcb")  # noqa: SLF001
    back = read_board(text)
    assert {c.ref: c.properties.get(PATH_PROPERTY) for c in back.circuit.components} == {
        "U1": "U1",
        "R1": "R1",
        "D1": "D1",
    }
    for fp in parse(text).nodes("footprint"):
        (prop,) = [p for p in fp.nodes("property") if p.atoms()[0].value == PATH_PROPERTY]
        assert prop.find("hide") is not None
