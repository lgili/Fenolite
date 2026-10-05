# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stack-up file read (capability altium-project-reader, "Stack-up file read")."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.backends.altium.read.stackup import StackEntry, read_stackup
from fenolite.backends.altium.read.textfile import BOM
from fenolite.core.errors import FormatError

DATA = Path(__file__).resolve().parents[4] / "data" / "altium" / "read"


def test_two_copper_layers() -> None:
    """Scenario "Two copper layers"."""
    data = (DATA / "two_layer.stackup").read_bytes()
    stack = read_stackup(data, file="two_layer.stackup")
    assert stack.to_bytes() == data and stack.issues == () and stack.version == "1"
    assert [layer.index for layer in stack.layers] == [1, 2, 3]
    assert [layer.kind for layer in stack.layers] == ["copper", "dielectric", "copper"]
    assert [layer.thickness for layer in stack.layers] == [35_000, 1_500_000, 35_560]
    assert stack.layers[1].epsilon_r == "4.8" and isinstance(stack.layers[1].epsilon_r, str)
    assert stack.layers[0] == StackEntry(1, "Top Layer", 16777217, "copper", 35_000, None, "", "", 1)
    assert stack.layers[1] == StackEntry(
        2, "Dielectric 1", 17039361, "dielectric", 1_500_000, 1, "4.8", "FR-4", None
    )
    assert stack.layers[2].component_placement == 2
    assert stack.record.keys()[0] == "STACKUPVERSION" and stack.record.get("DISPLAYUNIT") == "2"
    assert stack.form.lines[0].end == b""


def test_not_a_stackup_file() -> None:
    """Scenario "Not a stack-up file"."""
    with pytest.raises(FormatError, match="STACKUPVERSION") as caught:
        read_stackup((DATA / "jobs.OutJob").read_bytes(), file="jobs.OutJob")
    assert caught.value.file == "jobs.OutJob"


def test_byte_order_mark_and_trailing_separator() -> None:
    data = BOM + b"|STACKUPVERSION=1|LAYER_V8_0NAME=L1|LAYER_V8_0COPTHICK=1.4mil|"
    stack = read_stackup(data)
    assert stack.to_bytes() == data and stack.form.bom == BOM
    assert [(e.name, e.thickness) for e in stack.layers] == [("L1", 35_560)]


def test_solder_mask_is_a_dielectric_entry() -> None:
    data = b"|STACKUPVERSION=1|LAYER_V8_2NAME=Top Solder|LAYER_V8_2DIELTYPE=3|LAYER_V8_2DIELHEIGHT=0.4mil"
    (mask,) = read_stackup(data).layers
    assert mask.kind == "dielectric" and mask.dielectric_type == 3 and mask.thickness == 10_160


def test_unreadable_length() -> None:
    data = (
        b"|STACKUPVERSION=1|LAYER_V8_0NAME=A|LAYER_V8_0COPTHICK=thick|LAYER_V8_1NAME=B|LAYER_V8_1DIELHEIGHT=1"
    )
    stack = read_stackup(data, file="s.stackup")
    assert [(e.kind, e.thickness) for e in stack.layers] == [("copper", None), ("dielectric", None)]
    assert [(i.code, i.severity) for i in stack.issues] == [
        ("altium.stackup.length-unreadable", "warning")
    ] * 2


def test_more_than_one_generation() -> None:
    data = (
        b"|STACKUPVERSION=1|LAYER_V7_0NAME=Old|LAYER_V7_0COPTHICK=1mil"
        b"|LAYER_V9_1NAME=New|LAYER_V9_1COPTHICK=2mil|LAYER_V9_1_{AB}CONTEXT=1|LAYER_V9_1$LSM$Weight=1oz"
    )
    stack = read_stackup(data)
    assert [(e.index, e.name, e.thickness) for e in stack.layers] == [(1, "New", 50_800)]
    assert [i.code for i in stack.issues] == ["altium.stackup.unknown-form"]
    assert stack.record.get("LAYER_V9_1$LSM$Weight") == "1oz"


def test_entries_in_ascending_position_and_untyped_keys_kept() -> None:
    data = (
        b"|STACKUPVERSION=2|LAYER_V8_10NAME=Bottom|LAYER_V8_10COPTHICK=1mil|LAYER_V8_2NAME=Top"
        b"|LAYER_V8_2COPTHICK=1mil|LAYER_V8_3NAME=Overlay|VIASPAN_V8_0NAME=Thru|LAYER_V8_2LAYERID=x"
    )
    stack = read_stackup(data)
    assert stack.version == "2" and [e.index for e in stack.layers] == [2, 10]
    assert stack.layers[0].layer_id is None and stack.record.get("VIASPAN_V8_0NAME") == "Thru"


def test_compound_file_refused() -> None:
    with pytest.raises(FormatError, match="compound"):
        read_stackup(bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 8)
