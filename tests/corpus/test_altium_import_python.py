# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``import --to python`` of every public Altium PCB document (change c0427): each row's exit code, the
codes of its error findings and the kinds it leaves out are pinned. The report holds codes and counts
only: no name of a corpus file is printed.

Rows 01 and 02 fail on causes change c0426 owns (a pad position 1 nm off after rounding; a via whose drill
equals its diameter); row 08 on pad positions of the same rounding and one footprint whose pads differ
from its library form. When those land, their rows here change with them."""

from __future__ import annotations

from pathlib import Path

import pytest
from _corpus import manifest_items, require

from fenolite.api import run

PINNED: dict[str, tuple[int, frozenset[str]]] = {
    "altium-third-party-pcbdoc-01": (5, frozenset({"import.unequal"})),
    "altium-third-party-pcbdoc-02": (5, frozenset({"import.unequal"})),
    "altium-third-party-pcbdoc-03": (0, frozenset()),  # a cut-out across the board edge: a notch
    "altium-third-party-pcbdoc-04": (0, frozenset()),  # a negative silk to silk clearance
    "altium-third-party-pcbdoc-05": (0, frozenset()),
    "altium-third-party-pcbdoc-06": (0, frozenset()),  # a text with a CR LF line break
    "altium-third-party-pcbdoc-07": (0, frozenset()),  # a negative silk to silk clearance
    "altium-third-party-pcbdoc-08": (5, frozenset({"import.unequal"})),  # CR LF texts; heavy
}
ROWS = {item.id: item for item in manifest_items("altium-pcbdoc") if item.id in PINNED}
ROWS |= {item.id: item for item in manifest_items("altium-import") if item.id in PINNED}


def test_every_pinned_row_is_in_the_manifest() -> None:
    assert sorted(ROWS) == sorted(PINNED)


@pytest.mark.parametrize("row", sorted(PINNED))
def test_import_to_python_of_a_public_row(row: str, tmp_path: Path) -> None:
    path = require(ROWS[row])
    reply = run(
        "import", str(path.resolve()), "--to", "python", "--out", "out", "--allow-lossy", "--dry-run",
        cwd=tmp_path,
    )  # fmt: skip
    exit_code, codes = PINNED[row]
    issues = (reply.envelope or {}).get("issues", [])
    found = {issue["code"] for issue in issues if issue["severity"] == "error"}
    assert (reply.exit_code, found) == (exit_code, codes)
    assert reply.result is not None
    assert reply.result["unexpressed"] == []  # nothing is left out
    if exit_code == 0:
        assert reply.result["equivalence"]["equivalent"] is True
