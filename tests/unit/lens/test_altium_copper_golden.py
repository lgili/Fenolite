# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The routed sample's bisection variants (capability altium-build, "Routed sample and author report";
change c0038).

Every variant of ``tests/_altium_copper.variants()`` must build without an error and read back with the
test reader. With ``FENOLITE_ALTIUM_VARIANTS=<folder>`` the variants are also written there, one folder
each, for the maintainer to open in Altium Designer; the folder must lie outside the repository, so no
variant is ever committed.
"""

from __future__ import annotations

import os
import tempfile
from functools import cache
from pathlib import Path

from _altium_copper import NAME, Variant, routed_build, variants
from _altium_pcb_read import read_pcbdoc

ROOT = Path(__file__).resolve().parents[2].parent
VARIANTS_DIR = os.environ.get("FENOLITE_ALTIUM_VARIANTS")
FILES = tuple(f"{NAME}.{suffix}" for suffix in ("PcbDoc", "PcbLib", "PrjPcb", "SchDoc", "SchLib"))


def build_variant(variant: Variant) -> dict[str, bytes]:
    """The project files of one variant (without the ``.fenolite/`` cache); no issue may be an error."""
    with tempfile.TemporaryDirectory() as folder:
        output = routed_build(Path(folder), variant.model, copper=variant.copper, **variant.build)
    errors = [found for found in output.issues if found.severity == "error"]
    assert not errors, errors
    return {name: data for name, data in output.files.items() if not name.startswith(".fenolite/")}


@cache
def variant_files() -> dict[str, dict[str, bytes]]:
    return {name: build_variant(variant) for name, variant in variants().items()}


def test_variants_build_and_read_back() -> None:
    """Scenario "Variants stay outside the repository": every variant holds its five files, and
    ``FENOLITE_ALTIUM_VARIANTS`` writes them to a folder that is not in the repository."""
    built = variant_files()
    assert list(built)[:5] == ["c0", "c1", "c2", "c3", "c4"] and "p0" in built
    for name, files in built.items():
        assert set(FILES) <= set(files), name
        document = read_pcbdoc(files[f"{NAME}.PcbDoc"])
        assert len(document.components) == 3, name
    assert built["c0"][f"{NAME}.PcbDoc"] != built["c1"][f"{NAME}.PcbDoc"]
    if VARIANTS_DIR:
        target = Path(VARIANTS_DIR).resolve()
        assert ROOT.resolve() not in (target, *target.parents), "the variants folder is inside the repository"
        for name, files in built.items():
            folder = target / name
            folder.mkdir(parents=True, exist_ok=True)
            for file_name in FILES:
                (folder / file_name).write_bytes(files[file_name])


def test_variants_add_one_feature_each() -> None:
    built = variant_files()
    c0, c1, c2 = (read_pcbdoc(built[name][f"{NAME}.PcbDoc"]) for name in ("c0", "c1", "c2"))
    assert (len(c0.free_tracks), len(c0.free_arcs), len(c0.vias)) == (3, 1, 0)
    assert (len(c1.free_tracks), len(c1.free_arcs), len(c1.vias)) == (3, 1, 3)
    assert {t.prefix.layer for t in c0.free_tracks} == {1, 32}
    assert c0.copper_chain == c1.copper_chain == [1, 32] and c2.copper_chain == [1, 2, 3, 32]
    assert sorted(t.prefix.layer for t in c2.free_tracks) == [1, 1, 2, 3, 32] and len(c2.vias) == 3
    c3 = read_pcbdoc(built["c3"][f"{NAME}.PcbDoc"])
    c4 = read_pcbdoc(built["c4"][f"{NAME}.PcbDoc"])
    assert c3.classes == [] and [(c.name, c.members) for c in c4.classes] == [("PWR", ["GND", "VIN"])]
    assert c2.polygons == [] and [(p.layer, p.name) for p in c3.polygons] == [
        ("MID1", "GND_L02_P000"),
        ("BOTTOM", "GND_L04_P001"),
    ]
