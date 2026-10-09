# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via protection passes the oracle (capability kicad-oracle, "Via protection passes the oracle"; change
c0112; hypotheses H-K-VIAPROT-FORMS, H-K-VIAPROT-MASK, H-K-VIAPROT-NINE, H-K-VIAPROT-UPGRADE and
H-K-VIAPROT-OUTPUTS).

The facts benches set the protection children by token edit and ask KiCad what it plots and exports; the
reader's meaning (``via_protection.effective`` of what ``read_board`` gives) is compared with the mask
plots. The written bench sets the same cases through the model. Stop rule: a ``different`` outcome of
``via-prot-resave`` or ``via-prot-mask`` stops the part that writes or reads that form, and the register
row records what KiCad showed.
"""

from __future__ import annotations

import pytest
from _probes import major, run, runner
from _viabench import (
    DEFAULTS,
    NINE_CASES,
    NINE_FORMS,
    NINE_SETUPS,
    TEN_CASES,
    expected,
    facts_text,
    loads,
    mask_openings,
    model_openings,
    written_text,
)

from fenolite.backends.kicad.versions import LossyWriteError

pytestmark = pytest.mark.needs_kicad


def test_mask_follows_the_effective_tenting() -> None:
    """``via-prot-mask``: every via of the facts benches of the running major is open exactly where the
    effective tenting of its read protection is false."""
    assert run("via-prot-mask") == "equal"


def _nine_only() -> None:
    if major() >= 10:
        pytest.skip("a fact of KiCad 9: the running kicad-cli is newer")


def test_mask_of_one_named_side_on_nine() -> None:
    """On 9.0.9 the via with ``(tenting front)`` under the default ``front back`` is open on ``B.Mask``."""
    _nine_only()
    text = facts_text(NINE_FORMS, NINE_SETUPS["both"], 9)
    found = mask_openings(runner(), text, len(NINE_FORMS))
    assert found is not None
    assert found[NINE_FORMS.index("(tenting front)")] == (False, True)
    assert found == expected(text)


def test_nine_refuses_the_10_forms() -> None:
    """``via-prot-load-nine``: ``pcb drc`` gives exit 3 on a target-9 bench that holds a ``plugging``
    child."""
    _nine_only()
    assert run("via-prot-load-nine") == "reject"


@pytest.mark.kicad_min_major(10)
def test_upgrade_reads_9_children_its_own_way() -> None:
    """``via-prot-upgrade``: 10.0.6 plots the unnamed sides of ``front``, ``back``, ``none`` and the empty
    child of a 9.0 board as tented under the default ``front back``. The test passes on the recorded
    outcome only."""
    assert run("via-prot-upgrade") == "different"


@pytest.mark.kicad_min_major(10)
def test_outputs_hold_the_vias_that_carry_a_feature() -> None:
    """``via-prot-outputs``: each drill side file and each coating or hole-fill layer of IPC-2581 holds
    exactly the vias whose own value is ``True``."""
    assert run("via-prot-outputs") == "equal"


@pytest.mark.kicad_min_major(10)
def test_default_outputs_add_no_via() -> None:
    """``via-prot-default-outputs``: a board default of ``True`` for all eight fields adds no via to any
    of those files and layers, which is what ``kicad.via.protection-not-exported`` says."""
    assert run("via-prot-default-outputs") == "absent"


@pytest.mark.kicad_min_major(10)
def test_resave_keeps_the_written_children() -> None:
    """``via-prot-resave``: ``pcb upgrade --force`` of the written target-10 bench keeps the protection
    children of every via and of ``setup``."""
    assert run("via-prot-resave") == "equal"


@pytest.mark.kicad_min_major(10)
def test_resave_keeps_the_order_of_added_children() -> None:
    """``via-prot-order``: a protection added through the model to a read via that holds ``locked`` and
    ``free`` is written after them, and ``pcb upgrade --force`` keeps the order of the children."""
    assert run("via-prot-order") == "equal"


@pytest.mark.parametrize("default", sorted(DEFAULTS))
def test_written_bench_loads_and_plots_as_the_model_means(default: str) -> None:
    """The written bench of the running major loads, and every via's openings equal
    ``via_protection.effective`` of the model."""
    running = major()
    cases = NINE_CASES if running < 10 else TEN_CASES
    text = written_text(cases, DEFAULTS[default], running)
    assert loads(runner(), text) == 0
    found = mask_openings(runner(), text, len(cases))
    assert found == model_openings(cases, DEFAULTS[default])
    assert found == expected(text)


def test_written_bench_for_target_9_refuses_the_10_features() -> None:
    """Without ``kicad-cli``: the target-10 cases hold a ``True`` covering, plugging, capping or filling,
    which a KiCad 9 board cannot hold."""
    with pytest.raises(LossyWriteError) as caught:
        written_text(TEN_CASES, None, 9)
    assert caught.value.droppable is False
    assert {i.code for i in caught.value.issues} == {"kicad.board.via-protection-too-new"}
