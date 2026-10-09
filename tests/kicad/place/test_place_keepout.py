# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas that forbid footprints, as KiCad's DRC judges them (change c0113; hypothesis
``H-K-PLACE-KEEPOUT``; capability kicad-oracle, "Placement keep-outs are probed").

Each of the 18 cases of ``_keepoutcases`` is one probe ``place-keepout-<case>``; ``place-keepout-agree``
says whether ``placement.legality.check`` gives ``place.keepout`` for exactly the cases the DRC reports. The
hermetic test runs the same comparison against the expected outcomes, without ``kicad-cli``.

Stop rule: an outcome other than the expected one is written into the register row, and the predicate of
"Placement legality" follows the recorded outcomes.
"""

from __future__ import annotations

import _keepoutcases as kc
import pytest

from fenolite.placement import legality


@pytest.mark.needs_kicad
@pytest.mark.parametrize("case", sorted(kc.CASES))
def test_case(case: str) -> None:
    from _probes import run

    found = kc.verdict(case)
    assert found is not None, "pcb drc wrote no report"
    assert found.canary, "rules file not loaded: the canary violation is absent from the DRC report"
    assert not found.control, "the control part is named by an items_not_allowed violation"
    assert run(f"place-keepout-{case}") == kc.CASES[case].expected


@pytest.mark.needs_kicad
def test_agree() -> None:
    from _probes import run

    assert run("place-keepout-agree") == "equal"


@pytest.mark.parametrize("target", [9, 10])
def test_hermetic_agreement(target: int) -> None:
    """Without ``kicad-cli``: the legality check reports ``place.keepout`` for exactly the six cases whose
    expected outcome is ``present``, and the pad hull of a part without a courtyard as a warning."""
    verdicts = {name: kc.legality_verdict(name, target) for name in kc.CASES}
    assert {name for name, (keepout, _) in verdicts.items() if keepout} == kc.PRESENT
    assert len(kc.PRESENT) == 6 and len(kc.CASES) == 18
    assert {name for name, (_, bare) in verdicts.items() if bare} == {"nocrt-in", "nocrt-pad", "nocrt-mid"}


def test_hermetic_cases_are_the_register_row() -> None:
    assert kc.PRESENT == {"in", "crt-only", "over-10um", "bot-back", "bot-both", "tht-front"}
    assert legality.KEEPOUT_EVIDENCE.hypotheses == ("H-K-PLACE-KEEPOUT",)
