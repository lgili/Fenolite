# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original hash pin-name controls, measured before extending the proved vocabulary (c0357)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import _gencases as gen
import _kicad
import pytest

from fenolite.backends.kicad import netnames, sch, schlayout
from fenolite.backends.kicad.cli import NETLIST, KicadCli
from fenolite.backends.kicad.sexpr import parse_bytes

pytestmark = pytest.mark.needs_kicad
HASH_PINS = (("11", "#"), ("12", "RESET#"), ("13", "A/# B"))


@pytest.mark.parametrize("marked", (False, True))
def test_actual_hash_name_spelling_is_identical_open_and_marked(tmp_path: Path, marked: bool) -> None:
    target = int(_kicad.supported_version().split(".")[0])
    definition = gen.probe_symbol("Chars", [("passive", number, name) for number, name in gen.CHAR_PINS])
    inst = gen.Inst("Probe:Chars", "X1", gen.FRAME_ORIGIN, tuple(n for n, _ in gen.CHAR_PINS))
    text = gen.hand_sheet(target, [definition], [inst])
    flags = []
    if marked:
        sheet = sch.read_schematic(text)
        flags = [
            schlayout.pin_point(gen.FRAME_ORIGIN, pin.position, 0, "")
            for pin in sheet.lib_symbols[0].pins
            if pin.number in {number for number, _ in HASH_PINS}
        ]
        assert len(flags) == 3
        text = gen.hand_sheet(target, [definition], [inst], flags=flags)
    source = tmp_path / "probe.kicad_sch"
    source.write_text(text)
    result = KicadCli(Path(_kicad.cli())).export_netlist(source)
    assert result.ok and NETLIST in result.outputs, (result.returncode, result.stderr)
    raw = result.outputs[NETLIST]
    parsed = parse_bytes(raw)
    nets = parsed.find("nets")
    assert nets is not None
    actual = {}
    actual_types = {}
    for net in nets.nodes("net"):
        name = net.find("name")
        assert name is not None
        for node in net.nodes("node"):
            ref, pin = node.find("ref"), node.find("pin")
            assert ref is not None and pin is not None
            key = (ref.atoms()[0].value, pin.atoms()[0].value)
            actual[key] = name.atoms()[0].value
            pintype = node.find("pintype")
            assert pintype is not None
            actual_types[key] = pintype.atoms()[0].value
    expected = {
        ("X1", number): netnames.unconnected_name(
            "X1", unit=1, unit_count=1, pin_name=name, pad_number=number
        )
        for number, name in HASH_PINS
    }
    assert {key: actual[key] for key in expected} == expected
    assert all(actual_types[key] == ("passive+no_connect" if marked else "passive") for key in expected)
    (tmp_path / "native.net").write_bytes(raw)
    (tmp_path / "hash-name-proof.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "marked": marked,
                "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "native_netlist_sha256": hashlib.sha256(raw).hexdigest(),
                "actual_names": {pin: actual[("X1", pin)] for pin, _ in HASH_PINS},
                "all_exact": True,
                "actual_nc_marked_types_verified": True,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
