# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The routed sample's golden files, bisection variants and protocol (capability altium-build, "Routed
sample and author report"; change c0038).

A fresh Altium build of the routed sample (``tests/_altium_copper.py``) must give the five files under
``tests/data/altium/routed/`` byte for byte; ``FENOLITE_GOLDEN_WRITE=1`` rewrites them, and the SHA-256
values of Part C of ``docs/evidence/altium-pcb.md`` are then updated (``-k protocol`` checks them).

Every variant of ``tests/_altium_copper.variants()`` must build without an error and read back with the
test reader. With ``FENOLITE_ALTIUM_VARIANTS=<folder>`` the variants are also written there, one folder
each, for the maintainer to open in Altium Designer; the folder must lie outside the repository, so no
variant is ever committed.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from functools import cache
from pathlib import Path

import pytest
from _altium_copper import (
    ARC,
    NAME,
    TRACKS,
    VIA_DIAMETER,
    VIA_DRILL,
    VIAS,
    ZONE,
    Variant,
    routed_build,
    variants,
)
from _altium_pcb_read import read_pcbdoc

ROOT = Path(__file__).resolve().parents[2].parent
VARIANTS_DIR = os.environ.get("FENOLITE_ALTIUM_VARIANTS")
ROUTED_DIR = ROOT / "tests" / "data" / "altium" / "routed"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-pcb.md"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"
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
    assert list(built) == ["c0", "c1", "c2", "c3", "c4", "c5", "p0"]
    for name, files in built.items():
        assert set(FILES) <= set(files), name
        document = read_pcbdoc(files[f"{NAME}.PcbDoc"])
        assert len(document.components) == 3, name
    assert built["c0"][f"{NAME}.PcbDoc"] != built["c1"][f"{NAME}.PcbDoc"]
    if not WRITE:
        assert built["c5"][f"{NAME}.PcbDoc"] == (ROUTED_DIR / f"{NAME}.PcbDoc").read_bytes()
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


# --- golden files and protocol (task 8.3) -------------------------------------------------------------


def test_golden_routed_files() -> None:
    """Scenario "Golden routed files": a fresh build equals the five committed files."""
    files = variant_files()["c5"]
    if WRITE:
        ROUTED_DIR.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (ROUTED_DIR / name).write_bytes(files[name])
        pytest.skip("routed golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert sorted(p.name for p in ROUTED_DIR.iterdir()) == sorted(FILES)
    for name in FILES:
        assert (ROUTED_DIR / name).read_bytes() == files[name], f"{name} differs from a fresh build"


def test_golden_sample_files_keep_their_bytes() -> None:
    """Every file of ``tests/data/altium/sample/`` keeps its bytes (no change against the index)."""
    proc = subprocess.run(
        ["git", "diff", "--exit-code", "--quiet", "--", "tests/data/altium/sample/"],
        cwd=ROOT, capture_output=True, check=False,
    )  # fmt: skip
    if proc.returncode not in (0, 1):
        pytest.skip("not a git checkout")
    assert proc.returncode == 0, "tests/data/altium/sample/ changed"


def _mm(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _at(point: tuple[float, float]) -> str:
    return f"({_mm(point[0])}, {_mm(point[1])})"


def copper_rows() -> list[str]:
    """The copper table of Part C as the sample's data gives it: (kind, layer, net, geometry in mm, size)."""
    rows = [
        f"| track | {layer} | {net} | {_at(a)} → {_at(b)} | {_mm(width / 1e6)} |"
        for _key, layer, net, a, b, width in TRACKS
    ]
    _key, layer, net, start, mid, end, width = ARC
    rows.append(f"| arc | {layer} | {net} | {_at(start)} → {_at(mid)} → {_at(end)} | {_mm(width / 1e6)} |")
    size = f"{_mm(VIA_DIAMETER / 1e6)} / {_mm(VIA_DRILL / 1e6)}"
    rows += [f"| via | F.Cu–B.Cu | {net} | {_at(xy)} | {size} |" for _key, net, xy in VIAS]
    _key, net, layers, outline = ZONE
    corners = ", ".join(_at(p) for p in outline)
    rows += [f"| polygon | {layer} | {net} | {corners} | unpoured |" for layer in layers]
    return rows


def test_protocol_names_the_routed_bytes() -> None:
    """Scenario "Protocol names the routed bytes": Part C names the SHA-256 of every committed routed file
    and of ``p0/routed.PcbDoc``, and its copper table equals the sample's copper."""
    text = PROTOCOL.read_text(encoding="utf-8")
    assert text.count("## Part C") == 1
    part = text[text.index("## Part C") :]
    part = part[: part.index("\n## ", 5)]
    digests = dict(
        re.findall(r"^\| `tests/data/altium/routed/([^`]+)` \| `([0-9a-f]{64})` \|", part, flags=re.MULTILINE)
    )
    assert sorted(digests) == sorted(FILES)
    for name, digest in digests.items():
        assert hashlib.sha256((ROUTED_DIR / name).read_bytes()).hexdigest() == digest, name
    (plane,) = re.findall(r"^\| `p0/routed.PcbDoc` \| `([0-9a-f]{64})` \|", part, flags=re.MULTILINE)
    assert hashlib.sha256(variant_files()["p0"][f"{NAME}.PcbDoc"]).hexdigest() == plane
    table = [line for line in part.splitlines() if re.match(r"^\| (track|arc|via|polygon) \| ", line)]
    assert table == copper_rows()
    for step in ("**C1**", "**C2**", "**C3**", "**C4**", "**C5**", "**C6**"):
        assert step in part, step
    for row in ("TRACK", "VIA", "STACK", "REPOUR", "CLASS", "RULES", "VIEWER", "PLANE"):
        assert f"H-A-PCB-CU-{row}" in part, row


def test_copper_rows_equal_the_model() -> None:
    """The table's rows are the model's copper: the counts of the routed model."""
    from _altium_copper import routed_model

    board = routed_model().board
    assert board is not None
    rows = copper_rows()
    counts = {
        kind: sum(row.startswith(f"| {kind} |") for row in rows)
        for kind in ("track", "arc", "via", "polygon")
    }
    polygons = sum(len(zone.layers) for zone in board.zones)
    assert counts == {
        "track": len(board.tracks),
        "arc": len(board.arcs),
        "via": len(board.vias),
        "polygon": polygons,
    }
