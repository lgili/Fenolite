# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The source's ``Board6`` settings and mechanical layer names come back from KiCad (change c0464).

The sources are authored: the committed two-layer KiCad board, a line on ``F.CrtYd`` added, written as an
Altium document with one clearance rule of 0.025 mm, and its ``Board6`` edited to a metric document with
Altium's mechanical layer type names, a hole-shape hash pair and a Situs strategy name.
"""

from __future__ import annotations

import dataclasses
import re
import struct
from pathlib import Path

from fenolite.api import run
from fenolite.backends.altium import docboard, lower
from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import TrackRecord
from fenolite.backends.kicad import boardcarrier, fpitems
from fenolite.convert import altium_storages as storages
from fenolite.convert import convert_project, pads
from fenolite.convert.sources import read_source

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
STAMP = "2026-11-06T00:00:00Z"
LINE = '(gr_line (start 12 12) (end 22 12) (stroke (width 0.1) (type solid)) (layer "F.CrtYd") (uuid "c0464000-0000-4000-8000-000000000001"))'  # noqa: E501
NAMES = (
    "Board", "Board Shape", "Dimensions", "Fab Notes", "Top Assembly", "Bottom Assembly", "Top 3D Body",
    "Bottom 3D Body", "Top Component Center", "Bottom Component Center", "Top Component Outline",
    "Bottom Component Outline", "Top Designator", "Bottom Designator", "Top Courtyard", "Bottom Courtyard",
)  # fmt: skip
"""Authored names after Altium's mechanical layer types, Mechanical 1 to 16."""
GAP = "0.9843mil"
"""0.025 mm as an Altium rule writes it."""


def _clearance() -> tuple[int, tuple[tuple[str, str], ...]]:
    return (0, (
        ("RULEKIND", "Clearance"), ("NETSCOPE", "DifferentNets"), ("LAYERKIND", "SameLayer"),
        ("SCOPE1EXPRESSION", "All"), ("SCOPE2EXPRESSION", "All"), ("NAME", "Fine Gap"), ("ENABLED", "TRUE"),
        ("PRIORITY", "1"), ("COMMENT", "authored"), ("UNIQUEID", "AUTH1CLEA"),
        ("DEFINEDBYLOGICALDOCUMENT", "FALSE"), ("GAP", GAP), ("GENERICCLEARANCE", GAP),
        ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"), ("OBJECTCLEARANCES", ""),
    ))  # fmt: skip


def _board6(data: bytes) -> str:
    return data[4:].rstrip(b"\x00").decode("latin-1")


def _fields(text: str) -> dict[str, str]:
    return dict(re.findall(r"\|([^=|\r]+)=([^|\r]*)", text))


def _edited(text: str) -> str:
    """The writer's ``Board6`` text made metric, its mechanical layers named, its solder masks black in the
    3D view settings (the writer's are green), and the hash pair after
    ``HOLESHAPEHASHSIZE`` and the strategy name after the last place marker, as Altium writes them."""
    text = text.replace("|DISPLAYUNIT=1|", "|DISPLAYUNIT=0|").replace(
        "|GR0_DISPLAYUNIT=1|", "|GR0_DISPLAYUNIT=0|"
    )
    for n, name in enumerate(NAMES, start=1):
        text = re.sub(rf"\|LAYER{56 + n}NAME=[^|\r]*", f"|LAYER{56 + n}NAME={name}", text)
    text = re.sub(r"(\|HOLESHAPEHASHSIZE=[^|\r]*)", r"\1|HASHKEY00=1|HASHVALUE00=12", text, count=1)
    text = re.sub(r"CFG3D\.(TOP|BOT)SOLDERMASKCOLOR=\d+", r"CFG3D.\1SOLDERMASKCOLOR=0", text)  # black
    situs = r"\1|SITUSSTRATEGYNAME=Default 2 Layer Board"
    return re.sub(r"(\|PLACEMARKERY\d+=[^|\r]*)(?!.*\|PLACEMARKERY)", situs, text, count=1, flags=re.S)


def _source(folder: Path) -> Path:
    board = folder / "board" / BOARD.name
    board.parent.mkdir(parents=True)
    text = BOARD.read_text("utf-8").rstrip()
    board.write_text(text[: text.rindex(")")] + "  " + LINE + "\n)\n", encoding="utf-8")
    design = read_source(board).design
    design = pads.project(fpitems.with_graphic_nets(fpitems.with_footprint_items(design).design))
    written = lower.write_design(
        dataclasses.replace(design, rules=None),
        allow_lossy=True,
        source_rules=(_clearance(),),
        full_drill=True,
    )
    streams: dict[str, bytes] = {}
    for name, data in written.files.items():
        if name.endswith(".PcbDoc"):
            streams = open_compound(data).as_dict()
    text = _edited(_board6(streams["Board6/Data"])).encode("latin-1") + b"\x00"
    streams["Board6/Data"] = struct.pack("<I", len(text)) + text
    path = folder / "source" / "two_layer.PcbDoc"
    path.parent.mkdir(parents=True)
    path.write_bytes(write_compound(storage_from_paths(streams)))
    return path


def _written(path: Path) -> tuple[str, list[dict[str, str]]]:
    data = path.read_bytes()
    rules = [dict((k, v or "") for k, v in rule.record.fields) for rule in read_pcbdoc(data).rules]
    return _board6(open_compound(data).as_dict()["Board6/Data"]), rules


def _free_mechanical(path: Path) -> list[int]:
    """The layers of the tracks on mechanical layers that belong to no component, sorted."""
    tracks = read_pcbdoc(path.read_bytes()).tracks
    return sorted(
        t.prefix.layer
        for t in tracks
        if isinstance(t, TrackRecord) and 57 <= t.prefix.layer <= 72 and t.prefix.component is None
    )


def _go(folder: Path, *args: str) -> None:
    planned = run(*args, "--dry-run", cwd=folder, timestamp=STAMP)
    assert planned.exit_code == 0, planned.error
    done = run(*args, "--confirm", "--plan", str(planned.result["plan_id"]), cwd=folder, timestamp=STAMP)
    assert done.exit_code == 0, done.error


def _flow_a(folder: Path) -> Path:
    """``import --to python``, ``build`` and ``convert --to altium`` of the authored source."""
    source = _source(folder)
    _go(folder, "import", str(source), "--to", "python", "--out", "py", "--licence", "CC0-1.0", "--copyright",
        "2026 Fenolite contributors", "--allow-lossy")  # fmt: skip
    _go(folder, "build", str(folder / "py" / "design.py"), "--out", "b")
    (built,) = (folder / "b").glob("*.kicad_pcb")
    _go(folder, "convert", str(built), "--to", "altium", "--out", "alt", "--allow-lossy")
    (document,) = (folder / "alt").glob("*.PcbDoc")
    return document


def test_the_conversion_carries_the_settings(tmp_path: Path) -> None:
    """The conversion to KiCad carries ``Board6.Settings``: the settings in order, each run after its
    anchor, no owned key, and the sixteen mechanical names last."""
    conversion = convert_project(read_source(_source(tmp_path)), to="kicad", allow_lossy=True)
    text = conversion.files[conversion.read_back].decode("utf-8")
    found = storages.unpacked(boardcarrier.carried(text)["Fenolite.Altium." + storages.SETTINGS])
    assert found is not None
    fields = storages.settings_fields(found.data)
    assert struct.unpack("<I", found.header)[0] == len(fields)
    keys = [key for key, _ in fields]
    assert ("DISPLAYUNIT", "0") in fields and ("GR0_DISPLAYUNIT", "0") in fields
    assert keys.index("HASHKEY00") == keys.index("HOLESHAPEHASHSIZE") + 1
    assert fields[keys.index("SITUSSTRATEGYNAME") - 1][0] == docboard.ANCHOR
    assert not [k for k in keys if docboard.OWNED_KEY.fullmatch(k) and not re.fullmatch(r"LAYER\d+NAME", k)]
    assert storages.mechanical_names(fields) == {56 + n: name for n, name in enumerate(NAMES, start=1)}


def test_the_merge_keeps_the_writers_owned_keys() -> None:
    """Scenario "The writer's owned keys win": ``ORIGINX`` and ``LOOKAT.X`` stay the writer's, a setting
    takes the carried value, an unknown key goes after its anchor, and a field a line cannot hold is
    skipped."""
    lines = docboard.board_records(
        "x.PcbDoc", [(0, 0), (1000, 0), (1000, 1000)], (0, 0), unique_id="ABCDEFGH"
    )
    settings = [("ORIGINX", "5mil"), ("DISPLAYUNIT", "0"), ("LOOKAT.X", "9"), (docboard.ANCHOR, "DOTGRID"),
                ("NEWKEY", "1"), ("BADKEY", "é")]  # fmt: skip
    merged = docboard.with_settings(lines, settings)
    before = _fields("".join(docboard.format_line(line) for line in lines))
    after: dict[str, str] = {}
    for line in merged:
        after.update(dict(line))
    assert after["DISPLAYUNIT"] == "0"
    assert (after["ORIGINX"], after["LOOKAT.X"]) == (before["ORIGINX"], before["LOOKAT.X"])
    head = [key for key, _ in merged[0]]
    assert head.index("NEWKEY") == head.index("DOTGRID") + 1 and "BADKEY" not in after
    assert docboard.with_settings(lines, []) == [list(line) for line in lines]


def test_flow_a_keeps_a_metric_document_metric(tmp_path: Path) -> None:
    """Scenario "A metric document stays metric": flow A writes ``DISPLAYUNIT=0`` and ``GR0_DISPLAYUNIT=0``
    again, and the 0.025 mm rule keeps its gap."""
    board, rules = _written(_flow_a(tmp_path))
    fields = _fields(board)
    assert (fields["DISPLAYUNIT"], fields["GR0_DISPLAYUNIT"]) == ("0", "0")
    (rule,) = [rule for rule in rules if rule.get("NAME") == "Fine Gap"]
    assert rule["GAP"] == GAP


def test_flow_a_keeps_the_mechanical_names(tmp_path: Path) -> None:
    """Scenario "Altium's mechanical names come back": every ``LAYER<57+k>NAME`` is the source's, and the
    line on Mechanical 15 comes back on Mechanical 15."""
    document = _flow_a(tmp_path)
    board, _rules = _written(document)
    fields = _fields(board)
    assert [fields[f"LAYER{56 + n}NAME"] for n in range(1, 17)] == list(NAMES)
    assert _free_mechanical(document) == _free_mechanical(tmp_path / "source" / "two_layer.PcbDoc")
    assert 71 in _free_mechanical(document)


def test_flow_a_keeps_settings_the_writer_does_not_write(tmp_path: Path) -> None:
    """Scenario "Settings the writer does not write come back in place": the hash pair after
    ``HOLESHAPEHASHSIZE`` and the strategy name after the last place marker, on their lines."""
    board, _rules = _written(_flow_a(tmp_path))
    lines = board.split("\r")
    (hashed,) = [line for line in lines if "|HASHKEY00=" in line]
    assert re.search(r"\|HOLESHAPEHASHSIZE=[^|]*\|HASHKEY00=1\|HASHVALUE00=12", hashed)
    (situs,) = [line for line in lines if "|SITUSSTRATEGYNAME=" in line]
    assert re.search(r"\|PLACEMARKERY\d+=[^|]*\|SITUSSTRATEGYNAME=Default 2 Layer Board", situs)


def test_flow_a_keeps_a_black_solder_mask(tmp_path: Path) -> None:
    """A black mask of the source's 3D view settings (``CFG3D.TOPSOLDERMASKCOLOR=0``, as public row ``-05``
    holds it) comes back black, not the writer's green: the view configurations are settings."""
    board, _rules = _written(_flow_a(tmp_path))
    masks = re.findall(r"CFG3D\.(?:TOP|BOT)SOLDERMASKCOLOR=\d+", _fields(board)["3DCONFIGURATION"])
    assert masks == ["CFG3D.TOPSOLDERMASKCOLOR=0", "CFG3D.BOTSOLDERMASKCOLOR=0"]
