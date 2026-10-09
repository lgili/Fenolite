# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stack-up job file parity (capability kicad-oracle, "Stack-up job file parity"; change c0101;
hypotheses H-K-STACKUP-JOB, H-K-STACKUP-COMPLETE, H-K-STACKUP-DEFAULT and H-K-STACKUP-RESAVE).

KiCad reads the stack-up node Fenolite writes and ignores the nodes that ``project_stackup`` calls
incomplete: the proof is the Gerber job file that ``kicad-cli pcb export gerbers`` writes beside the
Gerbers. Stop rule: a probe that records another outcome stops the part of the change that relies on it,
and the register row records what KiCad showed. The benches exist for the copper counts of
``_stackbench.COUNTS``: 2, 4, 6 and 8 (c0100).
"""

from __future__ import annotations

import pytest
from _probes import major, run
from _stackbench import COUNTS, INCOMPLETE, USED, case_text, reader_verdict

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("count", COUNTS)
def test_job_states_the_written_stackup(count: int) -> None:
    """One entry per row and sheet with its thickness, material and colour, the constants exactly under
    ``impedance_controlled``, and the board thickness, finish and flag of ``GeneralSpecs``."""
    assert run(f"pcb-stackup-job-{count}") == "equal"


def test_job_of_the_built_stackup_blink() -> None:
    """``build-stackup-job``: the stack-up blink and its six-layer variant, built for the running major
    and exported."""
    assert run("build-stackup-job") == "equal"


@pytest.mark.parametrize("case", INCOMPLETE)
def test_incomplete_nodes_are_ignored(case: str) -> None:
    """KiCad states no thickness for the node, and the reader gives no stack-up and
    ``kicad.board.stackup-unused``: the reader's rule and KiCad are compared on the same file."""
    assert run(f"pcb-stackup-incomplete-{case}") == "absent"
    assert reader_verdict(case_text(case, major())) == (False, ["kicad.board.stackup-unused"])


@pytest.mark.parametrize("case", USED)
def test_complete_nodes_in_another_form_are_used(case: str) -> None:
    """Silkscreen after mask on the top side, and a table and a node without paste: KiCad states the
    thicknesses, and the reader gives a stack-up."""
    assert run(f"pcb-stackup-{case}") == "present"
    assert reader_verdict(case_text(case, major())) == (True, [])


@pytest.mark.parametrize("count", COUNTS)
def test_default_of_a_board_without_a_node(count: int) -> None:
    """Copper 0.035 mm, masks 0.01 mm, equal FR4 dielectrics that fill ``general`` thickness, finish
    ``None``."""
    assert run(f"pcb-stackup-default-{count}") == "equal"


@pytest.mark.kicad_min_major(10)
def test_resave_keeps_the_written_nodes() -> None:
    """``pcb upgrade --force`` keeps every node the benches write and ``general`` (9.0.9 has no
    ``pcb upgrade``); a dielectric sheet without a material or a constant takes KiCad's defaults."""
    assert run("pcb-stackup-resave") == "equal"


@pytest.mark.kicad_min_major(10)
def test_resave_defaults() -> None:
    """Rows without values come back with 0.035 mm, 0.01 mm, and ``FR4``, 4.5, 0.02 and type ``core``; a
    node without its tail gets ``(copper_finish "None") (dielectric_constraints no)``."""
    assert run("pcb-stackup-resave-defaults") == "equal"


@pytest.mark.kicad_min_major(10)
def test_ipc_thickness_is_the_sum_of_the_rows() -> None:
    """``pcb export ipc2581`` states the sum of the rows where ``general`` thickness differs from it."""
    assert run("pcb-stackup-ipc-thickness") == "equal"
