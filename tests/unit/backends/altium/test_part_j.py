# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part J of the maintainer's check (``docs/evidence/altium-edit.md``, "Part J: edit
sessions"; change c0241, task 1.1; the rows ``H-A-EDIT-*`` and ``H-A-INTEG-*``).

``phase_a(folder)`` writes phase A of the kit into ``folder``:

- ``board/``: ``tests/data/altium_edit/edit.py`` built with ``--target altium`` and the pour mode
  ``outline`` (the project, its PCB document, PCB library, schematic, schematic library and output job),
  the documents that the maintainer opens, edits one change at a time and saves in cases J1 to J21;
- ``expected.md``: every item that the cases name, read back from ``board/edit.PcbDoc`` with Fenolite's own
  reader, in millimetres from the board's lower-left corner, Y up;
- ``README.md``: the steps J1 to J22 in Brazilian Portuguese
  (``tests/data/altium_edit/kit/README-phase-a.md``), and ``PART-J.md``: Part J of the evidence page, in
  English;
- ``SHA256SUMS``: the SHA-256 of every other file.

With ``FENOLITE_ALTIUM_PART_J=<folder outside the repository>`` the kit is written there:
``FENOLITE_ALTIUM_PART_J=~/fenolite-altium-checks/session-7/J-edit uv run pytest
tests/unit/backends/altium/test_part_j.py -k phase_a``. Without it the kit is written under the test's own
folder. No file that Altium wrote is in the repository, and nothing here edits a document: phase A has no
write code of the edit session (task 1.1 of c0241).
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
from fractions import Fraction
from pathlib import Path

import fenolite.cli.main as cli_main
from fenolite.backends.altium.pcbrecords import LAYER_NAMES
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord, TextRecord, TrackRecord, ViaRecord

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "tests" / "data" / "altium_edit"
SCRIPT = DATA / "edit.py"
README = DATA / "kit" / "README-phase-a.md"
HANDOVER = os.environ.get("FENOLITE_ALTIUM_PART_J")
FLAGS = ("--seed", "241", "--timestamp", "2026-10-29T00:00:00Z", "--altium-pour", "outline")
OFFSET_UNITS = 10_000_000
"""The board's lower-left corner in a built document: (1000 mil, 1000 mil) in units of 1/10 000 mil."""
PHASE_A = 22


def _part_j() -> str:
    page = (ROOT / "docs" / "evidence" / "altium-edit.md").read_text(encoding="utf-8")
    start = page.index("## Part J: edit sessions")
    end = page.index("\n## ", start + 3)
    return page[start:end].rstrip() + "\n"


def _mm(units: float | Fraction, offset: int = 0) -> str:
    """Units of 1/10 000 mil as millimetres, three decimals; ``offset`` is taken away first."""
    return f"{float((Fraction(units) - offset) * Fraction(254, 100) / 1_000_000):.3f}"


def _xy(x: float | Fraction, y: float | Fraction) -> str:
    return f"({_mm(x, OFFSET_UNITS)}, {_mm(y, OFFSET_UNITS)})"


def _net(doc: PcbDocument, index: int | None) -> str:
    return "no net" if index is None else f"`{doc.nets[index].name}`"


def expected_lines(data: bytes) -> list[str]:
    """The items of ``edit.PcbDoc`` that the cases name, as the maintainer reads them in Altium."""
    doc = read_pcbdoc(data)
    out = [
        "## Components",
        "",
        "| designator | side | X, Y mm | rotation | footprint |",
        "|---|---|---|---|---|",
    ]
    for comp in doc.components:
        assert comp.x is not None and comp.y is not None
        out.append(
            f"| `{comp.source_designator}` | {comp.layer} | {_xy(comp.x, comp.y)} | {comp.rotation:.0f}° "
            f"| `{comp.pattern}` |"
        )
    out += [
        "",
        "## Tracks and lines outside components",
        "",
        "| net | layer | start mm | end mm | width mm |",
    ]
    out.append("|---|---|---|---|---|")
    for track in doc.tracks:
        if isinstance(track, TrackRecord) and track.prefix.component is None:
            out.append(
                f"| {_net(doc, track.prefix.net)} | {LAYER_NAMES[track.prefix.layer]} "
                f"| {_xy(track.x1, track.y1)} | {_xy(track.x2, track.y2)} | {_mm(track.width)} |"
            )
    out += ["", "## Vias", "", "| net | X, Y mm | diameter mm | hole mm |", "|---|---|---|---|"]
    for via in doc.vias:
        if isinstance(via, ViaRecord):
            out.append(
                f"| {_net(doc, via.prefix.net)} | {_xy(via.x, via.y)} "
                f"| {_mm(via.diameter)} | {_mm(via.hole)} |"
            )
    out += [
        "",
        "## Polygons",
        "",
        "| name | layer | net | pour index | corners mm |",
        "|---|---|---|---|---|",
    ]
    for polygon in doc.polygons:
        xs = [v.x for v in polygon.vertices]
        ys = [v.y for v in polygon.vertices]
        out.append(
            f"| `{polygon.name}` | {polygon.layer} | {_net(doc, polygon.net)} | {polygon.pour_index} "
            f"| {_xy(min(xs), min(ys))} … {_xy(max(xs), max(ys))} |"
        )
    out += ["", "## Free texts and regions", "", "| item | layer | place mm |", "|---|---|---|"]
    for text in doc.texts:
        if isinstance(text, TextRecord) and text.prefix.component is None:
            out.append(
                f"| text `{text.short_text}` | {LAYER_NAMES[text.prefix.layer]} | {_xy(text.x, text.y)} |"
            )
    for region in doc.regions:
        if isinstance(region, RegionRecord) and region.prefix.polygon is None:
            xs = [v.x for v in region.outline]
            ys = [v.y for v in region.outline]
            v7 = dict(region.properties.fields).get("V7_LAYER", "")
            out.append(
                f"| filled region (`V7_LAYER={v7}`) | {LAYER_NAMES[region.prefix.layer]} "
                f"| {_xy(min(xs), min(ys))} … {_xy(max(xs), max(ys))} |"
            )
    out += ["", "## Rules", "", "| name | kind |", "|---|---|"]
    out += [f"| `{rule.name}` | {rule.rule_kind} |" for rule in doc.rules]
    return out


def build_board(out: Path) -> None:
    """``edit.py`` built for Altium into ``out`` through the command line, without the build's cache."""
    args = ["build", str(SCRIPT), "--out", str(out), "--target", "altium", *FLAGS, "--confirm", "--json"]
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--no-backup"])
    assert code == 0, (json.loads(stdout.getvalue() or "{}").get("issues"), stderr.getvalue())
    cache = out / ".fenolite"
    if cache.exists():  # the build's cache is Fenolite's, not part of the kit
        for path in sorted(cache.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
        cache.rmdir()


def sha256_sums(folder: Path) -> dict[str, str]:
    """The SHA-256 of every file under ``folder`` but ``SHA256SUMS``, by its relative path in POSIX order."""
    files = {
        p.relative_to(folder).as_posix(): p
        for p in folder.rglob("*")
        if p.is_file() and p.name != "SHA256SUMS"
    }
    return {name: hashlib.sha256(files[name].read_bytes()).hexdigest() for name in sorted(files)}


def phase_a(folder: Path) -> dict[str, str]:
    """Write phase A of the kit into ``folder``; the SHA-256 of every file by its relative path."""
    board = folder / "board"
    if board.exists():
        for path in sorted(board.rglob("*"), reverse=True):
            path.unlink() if path.is_file() else path.rmdir()
    build_board(board)
    head = ["# Part J: expected values of `board/edit.PcbDoc`", ""]
    body = expected_lines((board / "edit.PcbDoc").read_bytes())
    (folder / "expected.md").write_text("\n".join([*head, *body, ""]), encoding="utf-8")
    (folder / "README.md").write_text(README.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "PART-J.md").write_text(_part_j(), encoding="utf-8")
    sums = sha256_sums(folder)
    (folder / "SHA256SUMS").write_text("".join(f"{d}  {n}\n" for n, d in sums.items()), encoding="utf-8")
    return sums


def test_phase_a_kit(tmp_path: Path) -> None:
    """Phase A: the authored project, the expected values, the steps in both languages and the sums."""
    folder = Path(HANDOVER).expanduser() if HANDOVER else tmp_path / "J-edit"
    if HANDOVER:
        assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    folder.mkdir(parents=True, exist_ok=True)
    sums = phase_a(folder)
    for suffix in ("PrjPcb", "PcbDoc", "PcbLib", "SchDoc", "SchLib", "OutJob"):
        assert f"board/edit.{suffix}" in sums, suffix
    assert {"README.md", "PART-J.md", "expected.md"} <= set(sums)
    assert not any(".fenolite" in name for name in sums)
    lines = (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert lines == [f"{d}  {n}" for n, d in sums.items()]
    doc = read_pcbdoc((folder / "board" / "edit.PcbDoc").read_bytes())
    assert not [i for i in doc.issues if i.severity == "error"]
    assert [p.name for p in doc.polygons] == ["GND", "VIN"] and [p.pour_index for p in doc.polygons] == [0, 1]
    assert not [r for r in doc.regions if isinstance(r, RegionRecord) and r.prefix.polygon is not None]
    expected = (folder / "expected.md").read_text(encoding="utf-8")
    assert "| `GND` | Top Layer | (10.000, 5.000) | (20.000, 5.000) | 0.250 |" in expected
    assert "text `FENOLITE EDIT`" in expected and "Mechanical 13" in expected and "`V7_LAYER=" in expected
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert [int(n) for n in re.findall(r"\*\*J(\d+)\*\*", readme)] == list(range(1, PHASE_A + 1))
    for path in folder.rglob("*"):
        if path.is_file() and path.suffix in (".PrjPcb", ".OutJob", ".md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            assert not re.search(r"(?:[A-Za-z]:\\|/home/|/tmp/|/Users/)", text), path.name


def test_phase_a_steps_match_the_evidence_page() -> None:
    """The Portuguese steps name the same cases, files, values and menus as the English cases."""
    readme = " ".join(README.read_text(encoding="utf-8").split())
    part = " ".join(_part_j().split())
    for case in range(1, PHASE_A + 1):
        assert f"**J{case}**" in readme and f"**J{case}**" in part, case
    names = set(re.findall(r"`(J\d\d-[a-z0-9-]+\.\w+)`", part))
    assert len(names) == 21 and names == set(re.findall(r"`(J\d\d-[a-z0-9-]+\.\w+)`", readme))
    for word in (
        "board/edit.PcbDoc", "edit.PrjPcb", "edit.SchDoc", "edit.PcbLib", "expected.md", "FENOLITE EDIT",
        "Mini_R_0603", "Mechanical 15", "Clearance", "Repour All", "File » Save As", "History",
        "Project Outputs", "fenolite kit verify", "SHA256SUMS",
    ):  # fmt: skip
        assert word in readme, word
        assert word in part, word
