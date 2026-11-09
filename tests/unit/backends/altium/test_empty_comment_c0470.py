# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A part without a value and without a symbol keeps no value through a PCB document (change c0470)."""

from __future__ import annotations

import dataclasses

from _altium import blink_pcbdoc_spec

from fenolite.backends.altium.adapter.board import _texts_of  # pyright: ignore[reportPrivateUsage]
from fenolite.backends.altium.lower import written_comment
from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.model.circuit import Component


def test_a_part_of_the_board_only_writes_no_comment() -> None:
    assert written_comment(Component(id="c1", ref="X1")) == ("", False)
    assert written_comment(Component(id="c2", ref="R1", lib_symbol_ref="Lib:R")) == ("R", False)
    assert written_comment(Component(id="c3", ref="R2", value="10k", lib_symbol_ref="Lib:R")) == (
        "10k",
        False,
    )


def test_an_empty_comment_reads_back_empty() -> None:
    spec, _ = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    first = spec.components[0]
    spec = dataclasses.replace(
        spec, components=(dataclasses.replace(first, comment=""), *spec.components[1:])
    )
    texts = _texts_of(read_pcbdoc(write_pcbdoc(spec, filename="t.PcbDoc")))
    assert (first.ref, "") in texts.values()
