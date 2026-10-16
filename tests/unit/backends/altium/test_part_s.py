# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part S of the maintainer's check (``docs/evidence/altium-pcb.md``, "Part S: slots and
cut-outs"; change c0168, task 5.1; ``H-A-SLOT-KIT``).

``part_s(folder)`` writes the kit into ``folder``:

- ``regions/``: ``tests/data/slots/altium.py`` built for Altium with ``pcbdoc.CUTOUT_REGIONS`` true, the
  form the gate would write: three board cut-out regions and four free hole pads (cases S1, S3, S4, S7).
- ``clearance/``: the same with two test points 0.2 mm from the milled slot ``S2`` and the drilled slot
  ``D2``, a ``GND`` pour and the rules Board Outline Clearance 0.5 mm and Hole To Hole Clearance 0.25 mm
  (cases S2, S5, S6).
- ``gate-off/``: the fixture built as a release builds it today, with the gate off, and ``build-report.json``,
  the ``altium.not-lowered`` infos that name each cut-out (case S8).
- ``expected.md``: the values the cases compare, read back from the written files with Fenolite's own
  reader, and ``README.md``, the steps; ``SHA256SUMS``, the SHA-256 of every file.

With ``FENOLITE_ALTIUM_PART_S=<folder outside the repository>`` the kit is written there:
``FENOLITE_ALTIUM_PART_S=~/fenolite-altium-checks/session-4/S-slots uv run pytest
tests/unit/backends/altium/test_part_s.py``. Without it the kit is written under the test's own folder. The
merged L needs the ``geo`` extra. No file that Altium wrote is in the repository.
"""

from __future__ import annotations

import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

import _altium_slotcases as cases
import pytest

from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, RegionRecord

ROOT = Path(__file__).resolve().parents[4]
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_S")
FOLDERS = ("regions", "clearance", "gate-off")
OFFSET_UNITS = 10_000_000
"""The board's lower-left corner in a built document: (1000 mil, 1000 mil) in units of 1/10 000 mil."""


def _mm(units: float) -> str:
    """Units of 1/10 000 mil as millimetres from the board's lower-left corner, three decimals."""
    return f"{float(Fraction(units) * Fraction(254, 100) / 1_000_000):.3f}"


def _write(folder: Path, files: dict[str, bytes]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in sorted(files.items()):
        if name.startswith(".fenolite/"):
            continue  # the build's cache is Fenolite's, not part of the kit
        (folder / name).write_bytes(data)


def expected_lines(data: bytes) -> list[str]:
    """The free slot pads, round free pads and board cut-out regions of a document, as the steps read them:
    millimetres from the board's lower-left corner, Y up."""
    doc = read_pcbdoc(data)
    lines = ["| item | X mm | Y mm | size | rotation |", "|---|---|---|---|---|"]
    for pad in doc.pads:
        if not isinstance(pad, PadRecord) or pad.prefix.component is not None:
            continue
        x, y = _mm(pad.x - OFFSET_UNITS), _mm(pad.y - OFFSET_UNITS)
        if pad.hole_shape == 2 and pad.slot_length:
            size = f"slot {_mm(pad.slot_length)} × {_mm(pad.hole)} mm, hole shape Slot"
        else:
            size = f"round hole {_mm(pad.hole)} mm"
        kind = "plated" if pad.plated else "not plated"
        lines.append(f"| free pad, {kind} | {x} | {y} | {size} | {pad.rotation:.3f}° |")
    for region in doc.regions:
        if not isinstance(region, RegionRecord):
            continue
        keys = dict(region.properties.fields)
        if keys.get("ISBOARDCUTOUT") != "TRUE":
            continue
        xs = [float(v.x) for v in region.outline]
        ys = [float(v.y) for v in region.outline]
        across = f"{_mm(min(xs) - OFFSET_UNITS)} … {_mm(max(xs) - OFFSET_UNITS)}"
        up = f"{_mm(min(ys) - OFFSET_UNITS)} … {_mm(max(ys) - OFFSET_UNITS)}"
        lines.append(f"| board cut-out region, {len(region.outline)} vertices | {across} | {up} | | |")
    return lines


def part_s(folder: Path) -> dict[str, str]:
    """Write the kit into ``folder``; the SHA-256 of every file by its path relative to ``folder``."""
    regions = cases.fixture_build(gate=True)
    clearance = cases.fixture_build(gate=True, edit=cases.clearance_variant)
    gate_off = cases.fixture_build(gate=False)
    _write(folder / "regions", dict(regions.files))
    _write(folder / "clearance", dict(clearance.files))
    _write(folder / "gate-off", dict(gate_off.files))
    report = [
        {"code": i.code, "severity": i.severity, "where": i.where, "message": i.message}
        for i in gate_off.issues
        if i.code == "altium.not-lowered" and i.where.startswith(("slot/", "cutout/"))
    ]
    (folder / "gate-off" / "build-report.json").write_text(
        json.dumps({"pcb": gate_off.summary["pcb"], "cutouts": report}, indent=2) + "\n", encoding="utf-8"
    )
    expected = ["# Part S: expected values", ""]
    for name, output in (("regions", regions), ("clearance", clearance), ("gate-off", gate_off)):
        expected += [f"## `{name}/slots.PcbDoc`", "", *expected_lines(output.files["slots.PcbDoc"]), ""]
    expected += [
        "The test points of `clearance/`: `TP1` at X 38.000, Y 28.300 mm (0.2 mm below the edge of the",
        "milled slot S2), `TP2` at X 36.000, Y 14.700 mm (0.2 mm above the edge of the drilled slot D2),",
        "both 1 mm round on the Top Layer, net `GND`.",
        "",
    ]
    (folder / "expected.md").write_text("\n".join(expected), encoding="utf-8")
    readme = (ROOT / "docs" / "evidence" / "altium-pcb.md").read_text(encoding="utf-8")
    start = readme.index("## Part S: slots and cut-outs")
    end = readme.index("\n## ", start + 3)
    (folder / "README.md").write_text(readme[start:end].rstrip() + "\n", encoding="utf-8")
    sums: dict[str, str] = {}
    for path in sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        sums[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (folder / "SHA256SUMS").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in sums.items()), encoding="utf-8"
    )
    return sums


def test_part_s_kit(tmp_path: Path) -> None:
    pytest.importorskip("pyclipper")
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "S-slots"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    sums = part_s(folder)
    for name in FOLDERS:
        assert f"{name}/slots.PcbDoc" in sums and f"{name}/slots.PrjPcb" in sums
    assert {"README.md", "expected.md", "gate-off/build-report.json"} <= set(sums)
    report = json.loads((folder / "gate-off" / "build-report.json").read_text(encoding="utf-8"))
    assert sorted(i["where"] for i in report["cutouts"]) == ["cutout/1", "slot/S1", "slot/S2+slot/S3"]
    regions = read_pcbdoc((folder / "regions" / "slots.PcbDoc").read_bytes())
    assert len([r for r in regions.regions if dict(r.properties.fields).get("ISBOARDCUTOUT") == "TRUE"]) == 3  # type: ignore[union-attr]
    assert not [
        r
        for r in read_pcbdoc((folder / "gate-off" / "slots.PcbDoc").read_bytes()).regions
        if dict(r.properties.fields).get("ISBOARDCUTOUT") == "TRUE"  # type: ignore[union-attr]
    ]
    text = (folder / "README.md").read_text(encoding="utf-8")
    for case in range(1, 9):
        assert f"**S{case}**" in text


SAVED = os.environ.get("FENOLITE_ALTIUM_S7")
"""Kit case S7: the path of ``regions/slots.PcbDoc`` saved by Altium Designer (``File » Save As``)."""


def _holes_and_cutouts(
    data: bytes,
) -> tuple[list[tuple[int, int, int, int | None, int]], list[list[tuple[int, int]]]]:
    import hashlib as digest

    from fenolite.backends.altium.adapter import import_board

    design = import_board(read_pcbdoc(data), file="s.PcbDoc", sha256=digest.sha256(data).hexdigest())
    board = design.board
    assert board is not None
    holes = sorted(
        (h.position.x, h.position.y, h.drill, h.length, h.rotation % 180_000_000 if h.length else 0)
        for h in board.holes
    )
    rings = [
        [(p.x, p.y) for p in g.points]
        for g in board.graphics
        if g.layer == "Edge.Cuts" and g.kind == "polygon"
    ]
    return holes, rings


def test_s7_saved_document_reads_back(tmp_path: Path) -> None:
    """Kit case S7: the document that Altium saved holds the four holes and the three cut-outs of the one
    Fenolite wrote, within 1 µm."""
    if not SAVED:
        pytest.skip("set FENOLITE_ALTIUM_S7 to the path of the document Altium saved (kit case S7)")
    pytest.importorskip("pyclipper")
    written = cases.fixture_build(gate=True).files["slots.PcbDoc"]
    holes, rings = _holes_and_cutouts(written)
    found_holes, found_rings = _holes_and_cutouts(Path(SAVED).expanduser().read_bytes())
    assert len(found_holes) == len(holes) == 4
    for a, b in zip(holes, found_holes, strict=True):
        assert all(abs(x - y) <= 1_000 for x, y in zip(a[:3], b[:3], strict=True))
        assert (a[3] is None) == (b[3] is None) and abs((a[3] or 0) - (b[3] or 0)) <= 1_000
        assert abs(a[4] - b[4]) <= 1_000
    assert len(found_rings) == len(rings) == 3
    for ring in rings:
        assert any(
            all(any(abs(x - u) <= 1_000 and abs(y - v) <= 1_000 for u, v in ring) for x, y in other)
            and all(any(abs(x - u) <= 1_000 and abs(y - v) <= 1_000 for u, v in other) for x, y in ring)
            for other in found_rings
        )
