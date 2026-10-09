# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tolerant schematic write of a circuit that was read (capability altium-schematic-writer, "Tolerant
texts of a read circuit" and "One net per pin of a read circuit"; change c0160).

The circuits are read from Fenolite's own Altium sample ``blink`` and KiCad board ``two_layer``, changed in
the model, written with ``lower.write_design`` and the schematic is read back with the Altium backend.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.altium import lower
from fenolite.backends.altium.ascii import UNHELD, read_text_problem, record_bytes
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.model.circuit import PinRef
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[4]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc"
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
OHM = "1 kΩ"


def _with_value(design: Design, ref: str, value: str) -> Design:
    components = tuple(
        dataclasses.replace(c, value=value) if c.ref == ref else c for c in design.circuit.components
    )
    return dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, components=components))


def _schematic(written: lower.ProjectWrite, folder: Path) -> Design:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in written.files.items():
        (folder / name).write_bytes(data)
    (document,) = [name for name in written.files if name.endswith(".SchDoc")]
    return AltiumBackend().read(folder / document).design


def _value(design: Design, ref: str) -> str:
    return next(c.value for c in design.circuit.components if c.ref == ref)


def test_text_outside_the_code_page(tmp_path: Path) -> None:
    """Scenario "Text outside the code page": the comment is written with its ``%UTF8%`` twin, and the
    reader gives it back from the twin."""
    design = _with_value(AltiumBackend().read(BLINK).design, "R1", OHM)
    written = lower.write_design(design, allow_lossy=True)
    assert "schematic" not in {i.where for i in written.issues if i.code == lower.NOT_LOWERED}
    data = written.files["blink.SchDoc"]
    assert OHM.encode("utf-8") in data and b"1 k" + UNHELD.encode("ascii") in data
    assert _value(_schematic(written, tmp_path), "R1") == OHM


def test_record_bytes_of_a_character_outside_the_code_page() -> None:
    """The plain value holds ``?`` for each character outside Windows-1252; the twin holds the text."""
    assert record_bytes((("TEXT", OHM),)) == b"|%UTF8%TEXT=1 k\xce\xa9|TEXT=1 k?"
    for bad in ((("TEXT", "a|b"),), (("TEXT", "a\nb"),)):
        with pytest.raises(ValueError):
            record_bytes(bad)


def test_read_text_problem() -> None:
    """A read comment may start with ``=`` or a space; the ASCII form still refuses what is not 7-bit."""
    assert read_text_problem("=Value") is None and read_text_problem(" =Value") is None
    assert read_text_problem(OHM, form="binary") is None
    reason = read_text_problem(OHM, form="ascii")
    assert reason is not None and "U+03A9" in reason
    assert read_text_problem("a|b", form="binary") is not None
    assert read_text_problem("a\nb", form="binary") is not None


def test_comment_reference_read_from_altium(tmp_path: Path) -> None:
    """A comment that starts with ``=`` and was read from an Altium document is written as read."""
    design = _with_value(AltiumBackend().read(BLINK).design, "R1", "=Value")
    written = lower.write_design(design, allow_lossy=True)
    assert "comment" not in written.inputs.changed
    assert _value(_schematic(written, tmp_path), "R1") == "=Value"


def test_comment_reference_read_from_kicad(tmp_path: Path) -> None:
    """One read from a KiCad file is written with a leading space and counted ``changed``."""
    design = _with_value(KicadBackend().read(TWO_LAYER).design, "R1", "=Value")
    written = lower.write_design(design, allow_lossy=True)
    r1 = next(c for c in design.circuit.components if c.ref == "R1")
    assert written.inputs.changed["comment"] == {lower.COMMENT_REASON: (r1.id,)}
    assert _value(_schematic(written, tmp_path), "R1").strip(" ") == "=Value"


def test_pin_on_two_nets(tmp_path: Path) -> None:
    """Scenario "Pin on two nets": the pin stays on the net with more pins, and the other membership is
    counted lost under ``pin-net``."""
    design = AltiumBackend().read(BLINK).design
    nets = sorted(design.circuit.nets, key=lambda net: (-len(net.members), net.name))
    big, small = nets[0], next(net for net in nets[1:] if net.members)  # with the pin, big holds more
    shared: PinRef = small.members[0]
    changed = tuple(
        dataclasses.replace(net, members=(*net.members, shared)) if net.id == big.id else net
        for net in design.circuit.nets
    )
    design = dataclasses.replace(design, circuit=dataclasses.replace(design.circuit, nets=changed))
    written = lower.write_design(design, allow_lossy=True)
    assert written.inputs.lost["pin-net"] == {lower.PIN_NET_REASON: (small.id,)}
    schematic = _schematic(written, tmp_path)
    refs = {c.id: c.ref for c in design.circuit.components}
    back = {c.ref: c.id for c in schematic.circuit.components}
    key = (back[refs[shared.component_id]], shared.pin)
    holders = [
        net.name for net in schematic.circuit.nets if any((m.component_id, m.pin) == key for m in net.members)
    ]
    assert holders == [big.name]
