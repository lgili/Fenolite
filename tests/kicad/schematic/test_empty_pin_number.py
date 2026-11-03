# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual original/target netlist universes and names for authored empty and literal pins (c0353)."""

from __future__ import annotations

import hashlib

import _erc
import pytest
from _empty_pin_number import definition, schematic
from _probes import major, runner

from fenolite.backends.kicad.symembed import embed_symbol

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("source", [9, 10])
@pytest.mark.parametrize("empty_name", [False, True])
def test_native_empty_number_full_universe_and_names(source, empty_name, record_property):
    cli, target = runner(), major()
    # The older executable cannot load a future source. The same original source10 is independently
    # measured by the native10 job; target9 still exports its directly embedded target9 copy here.
    original = schematic(source, empty_name=empty_name)
    embedded = embed_symbol(definition(source, empty_name=empty_name), target=target, show_hidden_power=False)
    lowered = schematic(target, embedded)
    target_graph = _erc.netlist(cli, "tiny.kicad_sch", {"tiny.kicad_sch": lowered})
    expected = {"/AUTH_EMPTY": {("J1", "")}, "/AUTH_CONTROL": {("J1", "2")}}
    assert target_graph == expected
    if source <= target:
        original_graph = _erc.netlist(cli, "tiny.kicad_sch", {"tiny.kicad_sch": original})
        assert original_graph == target_graph
    record_property("native_version", cli.version())
    record_property("source_format_major", source)
    record_property("original_sha256", hashlib.sha256(original.encode()).hexdigest())
    record_property("target_sha256", hashlib.sha256(lowered.encode()).hexdigest())


def test_native_literal_tilde_is_distinct_on_modern_target():
    if major() < 10:
        pytest.skip("literal tilde number is not represented by the older target")
    graph = _erc.netlist(runner(), "tiny.kicad_sch", {"tiny.kicad_sch": schematic(10, number="~")})
    embedded = embed_symbol(definition(10, "~"), target=10)
    lower = _erc.netlist(runner(), "tiny.kicad_sch", {"tiny.kicad_sch": schematic(10, embedded)})
    assert graph == lower == {"/AUTH_EMPTY": {("J1", "~")}, "/AUTH_CONTROL": {("J1", "2")}}
