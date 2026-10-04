# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the running ``kicad-cli`` does with a via whose copper touches a track of another net
(``H-K-VIA-RENET``; capability kicad-oracle, "Via re-net probe"; change c0029).

``tests/kicad/test_probe_results.py`` pins every outcome per version. Nothing in Fenolite depends on them:
``check_copper`` reports the short before any tool reads the board
(``tests/unit/checks/test_copper.py -k renet_bench``).
"""

from __future__ import annotations

import _benches
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_padded_via_is_loaded_on_the_track_net() -> None:
    """The reported case: the track's net owns a pad, the via's net owns none. The via is exported under
    the track's net, no short names it, and a 10.0 re-save writes it on that net."""
    assert run("copper-renet-export") == "present"
    assert run("copper-renet-drc") == "absent"
    if major() >= 10:
        assert run("copper-renet-resave") == "present"


def test_tied_via_keeps_its_net() -> None:
    """Both nets own a pad: the via stays on its net. On 9.0.9 a ``shorting_items`` violation names it. On
    10.0.6 that violation is given in about half of the runs of one unchanged board (8 of 16 on
    2026-10-04), so its outcome is not pinned there: KiCad's DRC is not a reliable guard against this
    short, which is why Fenolite checks copper itself."""
    assert run("copper-renet-tied-export") == "absent"
    if major() < 10:
        assert run("copper-renet-tied-drc") == "present"


@pytest.mark.parametrize("name", ["dangling", "anchored"])
def test_copper_without_pads_is_merged_into_one_net(name: str) -> None:
    """No pad in the cluster: the tool reports no short and describes the via and the track with one net
    name. Which of the two names it takes differs from run to run, so it is not pinned."""
    assert run(f"copper-renet-{name}-drc") == "absent"
    assert run(f"copper-renet-{name}-merged") == "present"


def test_merged_copper_is_saved_on_one_net() -> None:
    if major() < 10:
        pytest.skip("pcb upgrade exists on kicad-cli 10 only")
    assert run("copper-renet-dangling-resave") == "present"


@pytest.mark.parametrize("name", _benches.RENET_BENCHES)
def test_drc_types_naming_the_via(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    """The DRC types that name the via are supporting data of ``docs/formats/kicad/copper.md``: ``-s`` prints
    them with the via's exported net and the nets the report describes."""
    types = _benches.renet_types(name)
    assert _benches.renet_report(name) is not None
    assert "via_dangling" in types or _benches.SHORT in types or _benches.CLEARANCE in types
    nets = {label: sorted(found) for label, found in sorted(_benches.described_nets(name).items())}
    with capsys.disabled():
        print(
            f"\n{name}: via exported under {_benches.renet_export_nets(name)}; DRC types {types}; nets {nets}"
        )
