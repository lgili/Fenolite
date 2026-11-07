# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Literal formatted prefixes are not bus group delimiters (c0343)."""

import pytest

from fenolite.model.drawn_connect import bus_group_parts, expand

PREFIXES = ("BUS_{A}", "BUS^{A}", "~{BUS}", "BUS_{A}^{B}~{C}", "BUS_{A^{B}}")


@pytest.mark.parametrize("prefix", PREFIXES)
def test_formatted_prefix_keeps_exact_names_and_cardinality(prefix: str) -> None:
    assert bus_group_parts(f"{prefix}{{D[0..3]}}") == (prefix, ("D[0..3]",))
    assert expand(f"{prefix}{{D[0..3]}}", {}) == tuple(f"{prefix}.D{index}" for index in range(4))
    assert expand(f"{prefix}[0..3]", {}) == tuple(f"{prefix}{index}" for index in range(4))
    assert expand(f"{prefix}{{PAIR}}", {"PAIR": ("D0", "D1")}) == (f"{prefix}.D0", f"{prefix}.D1")
    assert bus_group_parts(prefix) is None


@pytest.mark.parametrize(
    "text",
    [
        "BUS_{A",
        "BUS_{A}{D[0..3]",
        "BUS_{A}}{D0}",
        "BUS_{A{B}}{D0}",
        "BUS_{A}{INNER{D0} D1}",
        "BUS_{A}{D0}tail",
        "~{READY}",
        "CHANNEL.~{READY}",
    ],
)
def test_malformed_and_unsupported_nested_groups_do_not_invent_members(text: str) -> None:
    assert bus_group_parts(text) is None
    assert expand(text, {}) is None
