# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Created layer tables of every even count of copper layers from 2 to 32 on the running ``kicad-cli``
(capability kicad-oracle, "Created layer tables are probed on both majors"; hypothesis H-K-PCB-LAYERS;
change c0100, counts 10 to 32 since change c0277).

The created test board gets the table of n copper layers and is loaded (``pcb drc``), exported (one
Gerber per copper layer) and, on 10.0, re-saved (``pcb upgrade --force``). The table of 3 is the negative
control; the table of one copper layer records its outcome (H-K-PCB-ONE-COPPER). ``test_same_table`` is
hermetic: the probes judge the table that the writer creates.
"""

from __future__ import annotations

import _layertables as lt
import pytest

from fenolite.backends.kicad.layers import CREATED_COPPER_COUNTS, created_layers
from fenolite.backends.kicad.pcb import read_board

TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.parametrize("copper", CREATED_COPPER_COUNTS)
def test_same_table(copper: int) -> None:
    """Scenario "Probe tables follow the writer" (no ``kicad-cli``)."""
    assert lt.COUNTS == CREATED_COPPER_COUNTS
    assert lt.table(copper) == created_layers(copper)
    for target in lt.TARGETS:
        back = read_board(lt.text(copper, target))
        assert back.board is not None
        assert lt.copper_rows(back.board.layers) == lt.copper_rows(created_layers(copper))


def test_odd_table_is_the_rule_for_three() -> None:
    """The negative control is what the row rule gives for three layers, which Fenolite refuses to create."""
    names = [row[1] for row in lt.rows(lt.ODD) if row[1].endswith(".Cu")]
    assert names == ["F.Cu", "In1.Cu", "B.Cu"] and lt.rows(lt.ODD)[1] == (4, "In1.Cu", "signal", None)
    with pytest.raises(ValueError, match="an even count from 2 to 32"):
        created_layers(lt.ODD)


@pytest.mark.needs_kicad
@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("copper", lt.COUNTS)
def test_table_loads_and_exports(copper: int, target: int) -> None:
    from _probes import run

    result = lt.table_run(copper, target)
    names = tuple(sorted(row[1] for row in lt.rows(copper) if row[1].endswith(".Cu")))
    print(f"n={copper} t{target}: loaded {result.loaded}, copper Gerbers {result.gerbers}")
    assert run(f"pcb-layers-{copper}-t{target}") == "load"
    assert result.gerbers == names and len(names) == copper
    assert run(f"pcb-layers-gerbers-{copper}-t{target}") == "equal"


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("target", lt.TARGETS)
@pytest.mark.parametrize("copper", lt.COUNTS)
def test_table_survives_a_resave(copper: int, target: int) -> None:
    """``pcb upgrade --force`` exists on 10.0 only (S-0037)."""
    from _probes import run

    result = lt.table_run(copper, target)
    assert result.resaved == lt.copper_rows(created_layers(copper))
    assert run(f"pcb-layers-resave-{copper}-t{target}") == "equal"


@pytest.mark.needs_kicad
@pytest.mark.parametrize("target", TARGETS)
def test_odd_table_is_refused(target: int) -> None:
    from _probes import run

    result = lt.table_run(lt.ODD, target)
    assert not result.loaded and result.gerbers == ()
    assert run(f"pcb-layers-odd-t{target}") == "reject"


@pytest.mark.needs_kicad
@pytest.mark.parametrize("target", TARGETS)
def test_one_copper_table(target: int) -> None:
    """H-K-PCB-ONE-COPPER (change c0277): KiCad 9.0.9 and 10.0.6 refuse a table whose only copper row is
    ``F.Cu`` ("1 is not a valid layer count"), so 1 is not a count of ``CREATED_COPPER_COUNTS``."""
    from _probes import run

    result = lt.table_run(lt.ONE, target)
    print(f"n=1 t{target}: loaded {result.loaded}")
    assert not result.loaded and 1 not in CREATED_COPPER_COUNTS
    assert run(f"pcb-layers-1-t{target}") == "reject"
