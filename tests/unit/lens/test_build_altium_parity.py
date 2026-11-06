# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``build --target altium`` of an imported design writes what ``convert --to altium`` of its source writes
(change c0448; capability altium-build, "PCB library outputs" and "PCB document output").

The source is the authored board ``tests/data/kicad/convert/net_tie_copper.kicad_pcb`` (net tie ``NT1``,
whose ``F.Cu`` line joins its two pads), with pad 1 given a solder-mask margin of 0.05 mm and the
``Edge.Cuts`` rectangle replaced by three lines and one arc. Both documents are read by Fenolite only."""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

from fenolite.api import convert, run
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import PadRecord, TrackRecord

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "convert" / "net_tie_copper.kicad_pcb"
UUID = "6f1c2a40-3b7e-4d51-9a8c-0c34800000"
MANUAL = 2
TOP_LAYER = 1
MASK_UNITS = 19_685  # 0.05 mm in 1/10000 mil


def _source(folder: Path) -> Path:
    text = FIXTURE.read_text(encoding="utf-8")
    pad = '\t\t\t(net 1 "A")\n'
    assert text.count(pad) == 1
    text = text.replace(pad, pad + "\t\t\t(solder_mask_margin 0.05)\n")
    rect = text[text.index("\t(gr_rect") : text.rindex(")")]
    stroke = '(stroke (width 0.1) (type default)) (layer "Edge.Cuts")'
    lines = [("10 5", "30 5"), ("30 5", "30 25"), ("30 25", "10 25")]
    edges = "".join(
        f'\t(gr_line (start {a}) (end {b}) {stroke} (uuid "{UUID}{k}0"))\n' for k, (a, b) in enumerate(lines)
    )
    edges += f'\t(gr_arc (start 10 25) (mid 5 15) (end 10 5) {stroke} (uuid "{UUID}40"))\n'
    source = folder / "kicad" / "tie.kicad_pcb"
    source.parent.mkdir(parents=True)
    source.write_text(text.replace(rect, edges), encoding="utf-8")
    return source


def _write(files: Mapping[str, bytes], folder: Path) -> None:
    for name, data in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)


def _confirmed(cwd: Path, *args: str) -> Mapping[str, Any]:
    planned = run(*args, "--dry-run", "--json", cwd=cwd)
    assert planned.exit_code == 0 and planned.result is not None, planned.error
    done = run(*args, "--confirm", "--plan", str(planned.result["plan_id"]), "--json", cwd=cwd)
    assert done.exit_code == 0 and done.envelope is not None, done.error
    return done.envelope


@pytest.fixture(scope="module")
def documents(tmp_path_factory: pytest.TempPathFactory) -> tuple[PcbDocument, PcbDocument, Mapping[str, Any]]:
    work = tmp_path_factory.mktemp("parity")
    source = _source(work)
    _write(convert(source, to="altium", allow_lossy=True).conversion.files, work / "converted")
    _confirmed(work, "import", str(source), "--to", "python", "--out", "out", "--allow-lossy")
    envelope = _confirmed(work / "out", "build", "design.py", "--out", "built", "--target", "altium")
    (converted,) = (work / "converted").glob("*.PcbDoc")
    (built,) = (work / "out" / "built").glob("*.PcbDoc")
    return read_pcbdoc(converted.read_bytes()), read_pcbdoc(built.read_bytes()), envelope


def _tie(doc: PcbDocument) -> tuple[str | None, list[tuple[int, int | None]]]:
    (component,) = doc.components
    tracks = [(t.prefix.layer, t.prefix.component) for t in doc.tracks if isinstance(t, TrackRecord)]
    return component.record.get("COMPONENTKIND"), tracks


def _pads(doc: PcbDocument) -> list[tuple[str, int, int]]:
    pads = [pad for pad in doc.pads if isinstance(pad, PadRecord)]
    return sorted((pad.name, pad.solder_mode, pad.solder_expansion) for pad in pads)


def _outline(doc: PcbDocument) -> list[tuple[int, Fraction, Fraction, Fraction]]:
    first = doc.board.outline[0]
    return [(v.kind, v.x - first.x, v.y - first.y, v.radius) for v in doc.board.outline]


def test_the_build_writes_the_net_tie_and_reports_no_loss_of_it(
    documents: tuple[PcbDocument, PcbDocument, Mapping[str, Any]],
) -> None:
    """Scenario "A net tie with copper and pads with a mask margin are written"."""
    _, built, envelope = documents
    issues: list[dict[str, str]] = envelope["issues"]
    named = [i["code"] for i in issues if "NetTie" in i.get("where", "") + i.get("message", "")]
    assert "altium.footprint-unsupported" not in named
    assert not [i for i in issues if i["code"] == "altium.pcbdoc-not-written"]
    dropped = " ".join(i["message"] for i in issues if i["code"] == "altium.primitive-dropped")
    assert "solder mask margin" not in dropped and "copper layer" not in dropped
    assert _tie(built) == ("4", [(TOP_LAYER, 0)])
    assert ("1", MANUAL, MASK_UNITS) in _pads(built)


def test_build_and_conversion_agree(documents: tuple[PcbDocument, PcbDocument, Mapping[str, Any]]) -> None:
    """Scenario "Build and conversion write one outline", with the net tie and the pad masks."""
    converted, built, _ = documents
    assert _tie(built) == _tie(converted)
    assert _pads(built) == _pads(converted)
    outline = _outline(built)
    assert outline == _outline(converted)
    assert [v[0] for v in outline] == [0, 0, 0, 1, 0]  # one arc vertex, the closing vertex a line
