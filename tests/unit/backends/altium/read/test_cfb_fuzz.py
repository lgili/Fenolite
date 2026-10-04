# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic property checks over mutations of authored containers."""

from __future__ import annotations

from _cfb_build import build
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.backends.altium.read.cfb import CompoundError, open_compound

_BASE = build(
    [
        {"path": "A/Small", "data": b"s" * 65},
        {"path": "A/Large", "data": b"l" * 4096},
        {"path": "Root", "data": b"r" * 5000},
    ]
).data


@settings(max_examples=120, derandomize=True, deadline=None)
@given(
    operation=st.sampled_from(("flip", "cut", "extend")),
    index=st.integers(min_value=0, max_value=len(_BASE) - 1),
    value=st.integers(min_value=0, max_value=255),
    tail=st.binary(max_size=32),
)
def test_mutated_inputs_return_a_container_or_a_located_error(
    operation: str, index: int, value: int, tail: bytes
) -> None:
    data = bytearray(_BASE)
    if operation == "flip":
        data[index] ^= value
    elif operation == "cut":
        del data[max(0, len(data) - index % 100) :]
    else:
        data.extend(tail)
    try:
        found = open_compound(bytes(data))
    except CompoundError:
        return
    streams = found.as_dict()
    assert sum(map(len, streams.values())) <= len(data)
