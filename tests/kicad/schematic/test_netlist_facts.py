# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The parts of ``kicad-cli sch export netlist`` that Fenolite reads, measured on the running major
(capability kicad-oracle, "Schematic netlist through the package runner"; hypothesis
``H-K-NETLIST-SHAPE``; change c0063). The export is read as a plain tree, not with Fenolite's reader."""

from __future__ import annotations

import _netlistcases as cases
import _probes
import pytest

from fenolite.backends.kicad.sexpr import dumps, parse

pytestmark = pytest.mark.needs_kicad
ROOT_HEADS = {"version", "design", "components", "libparts", "libraries", "nets"}
TEN_HEADS = {"groups", "variants"}


def test_shape() -> None:
    """The heads the reader uses exist with the atoms it reads; the root children are those of the major."""
    root = parse(cases.export("blink"))
    heads = {child.name for child in root.nodes()}
    print(f"kicad-cli {_probes.version()}: root children {sorted(heads)}")
    assert heads == ROOT_HEADS | (TEN_HEADS if _probes.major() >= 10 else set())
    outcome = _probes.run("netlist-shape")
    print(f"netlist-shape: {outcome}")
    assert outcome == "equal"


def test_no_power_symbols() -> None:
    """A power flag is neither a component nor a node of a net."""
    outcome = _probes.run("netlist-power-symbols")
    print(f"netlist-power-symbols: {outcome}")
    assert outcome == "absent"


def test_pintypes() -> None:
    """``pintype`` is the electrical type of the pin, with ``+no_connect`` under a flag."""
    for name in ("blink", "units"):
        found, expected = cases.pintypes(name), cases.expected_pintypes(name)
        differing = {key: (found.get(key), expected.get(key)) for key in found.keys() | expected.keys()}
        differing = {key: pair for key, pair in differing.items() if pair[0] != pair[1]}
        flagged = sum(1 for value in found.values() if value.endswith(cases.NO_CONNECT))
        print(f"{name}: {len(found)} pins, {flagged} under a flag, {len(differing)} differing")
        assert not differing, differing
    outcome = _probes.run("netlist-pintype")
    print(f"netlist-pintype: {outcome}")
    assert outcome in ("equal", "different")
    assert outcome == "equal", "compare with pintypes=False on this major and record it (design 8)"


def test_dated_parts_are_outside_what_is_read() -> None:
    """The date and the paths of a run lie in ``design`` and ``libraries`` only."""
    root = parse(cases.export("blink"))
    design = root.find("design")
    assert design is not None and design.find("date") is not None and design.find("source") is not None
    kept = [child for child in root.nodes() if child.name in ("components", "nets")]
    text = "".join(dumps(child) for child in kept)
    source = design.find("source")
    assert source is not None
    assert source.atoms()[0].value not in text
