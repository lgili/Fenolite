# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A KiCad schematic as a side of ``equivalent``, against ``kicad-cli`` (capability design-equivalence,
"Schematic sides", "Schematic side netlist" and "Fitted flag of a schematic side"; hypothesis
``H-K-EQ-SCHSIDE``; change c0158).

For the projects ``build`` writes, the circuit read through Fenolite's own netlist equals the circuit read
through ``kicad-cli sch export netlist``, and the export marks a do-not-populate symbol with a ``property``
named ``dnp``. A hand-drawn schematic, outside the own netlist's grammar, is read through the tool: the
authored hierarchy of ``tests/data/kicad/schematic`` and, with the corpus, demo projects of the running
major's tag, each compared with its own board at levels 1 and 2.
"""

from __future__ import annotations

from pathlib import Path

import _eqsides
import _paritycorpus
import _probes
import pytest

from fenolite.api import equivalent
from fenolite.api.sides import EXPORT_EVIDENCE, read_side
from fenolite.backends.kicad import parity_inputs
from fenolite.core.evidence import Level

pytestmark = pytest.mark.needs_kicad
DATA = Path(__file__).resolve().parents[2] / "data" / "kicad" / "schematic"
DEMOS = {10: ("complex_hierarchy", "kit-dev-coldfire-xilinx_5213", "video"),
         9: ("flat_hierarchy", "pic_programmer", "carte_test")}  # fmt: skip
"""Three demo projects of each tag (``_paritycorpus.TAG_OF_MAJOR``) whose sheets the own netlist refuses."""


@pytest.mark.parametrize("name", _eqsides.GENERATED)
def test_generated_circuits_are_equal(name: str) -> None:
    found, marked = _eqsides.generated(name)
    print(
        f"{name}: {len(found)} difference(s) between the own netlist and kicad-cli's; marked {sorted(marked)}"
    )
    assert found == [] and marked == frozenset()


def test_dnp_field() -> None:
    ref, marked, own_marked = _eqsides.marked_blink()
    print(f"kicad-cli {_probes.version()}: {ref} marked by the property {_eqsides.FIELD!r}: {sorted(marked)}")
    assert marked == own_marked == frozenset({ref})


def test_probe() -> None:
    outcome = _probes.run("equiv-schside")
    print(f"equiv-schside: {outcome} on kicad-cli {_probes.version()}")
    assert outcome == "equal"


def test_authored_hierarchy_through_kicad_cli() -> None:
    """The authored hierarchy fails the grammar check, so the side reads ``kicad-cli``'s export."""
    folder = DATA / ("hier" if _probes.major() >= 10 else "hier_v9")
    top = folder / "top.kicad_sch"
    assert parity_inputs.grammar_issues(parity_inputs.read_sheets(top))
    side = read_side(top)
    assert side.netlist_source == "schematic" and side.evidence == EXPORT_EVIDENCE
    assert side.design.circuit.components and side.design.board is None
    found = equivalent(top, top)
    assert (
        found.report is not None and found.equivalent and [lv.level for lv in found.report.levels] == [1, 2]
    )


@pytest.mark.needs_corpus
def test_demo_schematics_against_their_boards(tmp_path: Path) -> None:
    """Scenario "Hand-drawn schematic through kicad-cli"."""
    major = _probes.major()
    tag = _paritycorpus.TAG_OF_MAJOR[major]
    found, _ = _paritycorpus.demo_projects(tmp_path, tag, newest=_paritycorpus.newest_schematic(major))
    projects = {project.name: project for project in found}
    wanted = DEMOS[major]
    missing = sorted(set(wanted) - set(projects))
    if missing:
        pytest.skip(f"demo projects not cached: {missing}")
    for name in wanted:
        project = projects[name]
        assert parity_inputs.grammar_issues(parity_inputs.read_sheets(project.schematic)), name
        result = equivalent(project.schematic, project.board)
        assert result.report is not None, name
        assert [lv.level for lv in result.report.levels] == [1, 2], name
        assert result.a.netlist_source == "schematic" and result.a.components > 0, name
        assert result.evidence.level is not Level.UNVERIFIED
        kinds: dict[str, int] = {}
        for difference in result.report.differences:
            kinds[difference.kind] = kinds.get(difference.kind, 0) + 1
        print(
            f"{name} ({tag}): {result.a.components} components, {result.a.power_symbols} power symbols; "
            f"board {result.b.components if result.b else 0}; differences {dict(sorted(kinds.items()))}"
        )
