# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence matrix row (capability backend-protocol, "Evidence matrix rows"; change c0067)."""

from __future__ import annotations

import dataclasses

import pytest

from fenolite.backends.base import MATRIX_OPERATIONS, MatrixRow
from fenolite.core.evidence import Evidence, Level

READ = Evidence(Level.INFERRED, hypotheses=("H-K-WKS-CORNER",))
WRITE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-WKS-CORNER", "H-K-PCB-WRITE"))


def test_operations() -> None:
    assert MATRIX_OPERATIONS == ("detect", "read", "write", "roundtrip_exact", "roundtrip_modified")
    fields = [f.name for f in dataclasses.fields(MatrixRow)]
    assert fields == ["backend", "kind", *MATRIX_OPERATIONS, "experimental"]


def test_row_as_json() -> None:
    row = MatrixRow("kicad", "kicad_wks", read=READ, write=WRITE, experimental=("write",))
    assert row.to_json() == {
        "backend": "kicad",
        "kind": "kicad_wks",
        "detect": None,
        "read": "INFERRED",
        "write": "KICAD-VERIFIED",
        "roundtrip_exact": None,
        "roundtrip_modified": None,
        "verified_by": ["H-K-PCB-WRITE", "H-K-WKS-CORNER"],
        "experimental": ["write"],
    }
    assert row.verified_by() == ("H-K-PCB-WRITE", "H-K-WKS-CORNER")
    assert row.cells() == (("read", READ), ("write", WRITE))


def test_json_lists_experimental_in_operation_order_and_names_the_oracle() -> None:
    oracle = Evidence(Level.ORACLE_VERIFIED, "kicad-cli", ("H-K-00",))
    row = MatrixRow("x", "k", detect=oracle, read=READ, write=WRITE, experimental=("write", "detect"))
    assert row.to_json()["experimental"] == ["detect", "write"]
    assert row.to_json()["detect"] == "ORACLE-VERIFIED(kicad-cli)"


@pytest.mark.parametrize(
    ("cells", "word"),
    [
        ({"roundtrip_exact": READ}, "roundtrip_exact needs read"),
        ({"read": READ, "roundtrip_modified": READ}, "roundtrip_modified needs read and write"),
        ({"write": WRITE, "roundtrip_modified": READ}, "roundtrip_modified needs read and write"),
        ({"read": READ, "experimental": ("write",)}, "whose cell is not set"),
        ({"read": READ, "experimental": ("read", "read")}, "twice"),
        ({"read": READ, "experimental": ("fill",)}, "not an operation"),
    ],
)
def test_impossible_rows_are_refused(cells: dict[str, object], word: str) -> None:
    with pytest.raises(ValueError, match=word) as caught:
        MatrixRow("kicad", "kicad_wks", **cells)  # type: ignore[arg-type]
    assert "kicad/kicad_wks" in str(caught.value)
