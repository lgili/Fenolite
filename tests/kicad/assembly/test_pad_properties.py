# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What ``kicad-cli`` does with a pad's fabrication mark (capability kicad-oracle, "Assembly and test pad
properties are probed"; hypotheses ``H-K-PAD-FABPROP`` and ``H-K-PAD-FABPROP-LIB``; change c0118). The
benches are in ``_featurebench``; the probes are recorded for the majors of ``_featurebench.MAJORS``."""

from __future__ import annotations

import typing

import _featurebench as fb
import _probes
import pytest

from fenolite.backends.kicad._fpmap import FAB_PROPERTY_TOKENS
from fenolite.model.board import PadFabProperty

pytestmark = pytest.mark.needs_kicad
VALUES: tuple[PadFabProperty, ...] = typing.get_args(PadFabProperty)


def _recorded() -> None:
    if _probes.major() not in fb.MAJORS:
        pytest.skip(f"the probes of change c0118 are recorded for the majors {fb.MAJORS} only")


@pytest.mark.parametrize("value", VALUES)
def test_mark_in_the_copper_plot(value: PadFabProperty) -> None:
    """``pad-fabprop-<value>``: the board loads, and the copper Gerber flashes the pad with the aperture
    function of ``docs/formats/kicad/board.md``, for the token-edited bench and for the written one."""
    _recorded()
    assert _probes.run(f"pad-fabprop-{value}") == "equal"


def test_the_bench_holds_every_mark() -> None:
    """The cases are not vacuous: one pad per token, eight tokens for target 10 and seven for target 9."""
    assert set(fb.FUNCTIONS) == set(VALUES) == set(FAB_PROPERTY_TOKENS)
    for target, count in ((9, 7), (10, 8)):
        for written in (False, True):
            text = fb.marks_text(target, written=written)
            assert text.count("(property pad_prop_") == count, (target, written)
        assert "pad_prop_" not in fb.marks_text(target, False)
    assert "pad_prop_pressfit" not in fb.marks_text(9)


def test_unmarked_pads_keep_their_function() -> None:
    """The control: without a mark the SMD pads are ``SMDPad,CuDef`` and the through-hole pads
    ``ComponentPad``, so six of the eight functions do come from the mark."""
    _recorded()
    target = max(fb.targets(_probes.runner()))
    found = fb.plot(_probes.runner(), fb.marks_text(target, False), "F.Cu")
    assert found is not None
    assert sorted({f[2] for f in found}) == ["ComponentPad", "SMDPad,CuDef"]


def test_outputs_do_not_change() -> None:
    """``pad-fabprop-outputs``: the position file and the IPC-D-356 records, with and without the marks."""
    _recorded()
    assert _probes.run("pad-fabprop-outputs") == "equal"


def test_padstack_on_surface_pads_only() -> None:
    """``pad-fabprop-padstack``: ``castellated`` and ``mechanical`` are reported on an SMD pad, and not on a
    through-hole pad."""
    _recorded()
    assert _probes.run("pad-fabprop-padstack") == "equal"


def test_resave_keeps_every_mark() -> None:
    """``pad-fabprop-resave``: ``pcb upgrade --force`` of 10.0 keeps the eight marks, each after ``size`` or
    ``drill`` and before ``layers``."""
    if _probes.major() < 10:
        pytest.skip("pcb upgrade is a command of KiCad 10")
    assert _probes.run("pad-fabprop-resave") == "equal"


def test_lib_mismatch_for_a_marked_copy() -> None:
    """``pad-fabprop-lib-mismatch``: a mark on a placed copy whose library pad has none."""
    _recorded()
    assert _probes.run("pad-fabprop-lib-mismatch") == "present"


def test_lib_same_for_authored_definitions() -> None:
    """``pad-fabprop-lib-same``: the vendored footprint file carries the mark of its placed copy."""
    _recorded()
    assert _probes.run("pad-fabprop-lib-same") == "absent"
    files = fb.authored_files(max(fb.targets(_probes.runner())))
    library = {rel: data for rel, data in files.items() if rel.endswith(".kicad_mod") and "Local" in rel}
    texts = [d.decode("utf-8") if isinstance(d, bytes) else d for d in library.values()]
    assert sorted(t.count("(property pad_prop_") for t in texts) == [1, 1]
