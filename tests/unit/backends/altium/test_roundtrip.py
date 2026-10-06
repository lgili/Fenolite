# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The round-trip levels RT-A0 and RT-A1 of Altium files (capability altium-verification, "Round-trip level
RT-A0" and "Round-trip level RT-A1"; change c0044), on every Altium file under ``tests/data/altium/`` and on
authored files."""

from __future__ import annotations

import ast
import dataclasses
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from _altium_sch_build import SHEET, schdoc
from _cfb_build import build

from fenolite.backends.altium import cfb as compound_writer
from fenolite.backends.altium import roundtrip
from fenolite.backends.altium.backend import READ_KINDS
from fenolite.backends.altium.docset import SUFFIX_KINDS, kind_of
from fenolite.backends.altium.read import cfb, pcb, pcblib, sch
from fenolite.backends.altium.read.sch import framing
from fenolite.backends.altium.roundtrip import (
    CODECS,
    COMPOUND_KINDS,
    EVIDENCE_RT_A0,
    EVIDENCE_RT_A1,
    EVIDENCE_RT_A2,
    PROJECT_READ_EVIDENCE,
    RT_A2_SCOPE,
    STAGE_EVIDENCE,
    StreamCodec,
    rt_a0,
    rt_a1,
)
from fenolite.checks.diff import KIND_CLASSES, NEVER
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "tests" / "data" / "altium"
BLINK = DATA / "blink"
OWN = sorted(p for p in DATA.rglob("*") if p.is_file() and p.suffix.lower() in SUFFIX_KINDS)
COMPOUND = [p for p in OWN if kind_of(p) in COMPOUND_KINDS]


def _id(path: Path) -> str:
    return path.relative_to(DATA).as_posix()


def test_own_files_cover_the_six_kinds() -> None:
    assert {kind_of(path) for path in OWN} == set(READ_KINDS) == set(CODECS)
    assert len(COMPOUND) >= 10


@pytest.mark.parametrize("path", COMPOUND, ids=_id)
def test_rt_a0_own(path: Path) -> None:
    data = path.read_bytes()
    verdict = rt_a0(data, kind=kind_of(path), file=path.name)
    assert verdict.level == "RT-A0" and verdict.judged and verdict.passed
    assert verdict.streams == len(cfb.open_compound(data).streams()) > 0
    assert verdict.different == () and verdict.difference == "" and verdict.reason == ""
    assert verdict.evidence == EVIDENCE_RT_A0


def _without(path: str) -> Any:
    """``write_compound`` that drops the stream at ``path``."""
    real = compound_writer.write_compound

    def strip(entries: Sequence[Any], prefix: str) -> tuple[Any, ...]:
        out: list[Any] = []
        for entry in entries:
            if isinstance(entry, compound_writer.Storage):
                out.append(
                    compound_writer.Storage(entry.name, strip(entry.entries, f"{prefix}{entry.name}/"))
                )
            elif f"{prefix}{entry[0]}" != path:
                out.append(entry)
        return tuple(out)

    return lambda entries: real(strip(entries, ""))


def test_rt_a0_lost_stream_is_located(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(compound_writer, "write_compound", _without("Nets6/Data"))
    path = BLINK / "blink.PcbDoc"
    verdict = rt_a0(path.read_bytes(), kind="altium_pcbdoc", file=path.name)
    assert verdict.judged and not verdict.passed
    assert verdict.different == ("Nets6/Data",) and verdict.difference == "Nets6/Data"


def test_rt_a0_changed_bytes_and_lost_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    real = compound_writer.write_compound
    data = build([{"path": "A/Data", "data": b"abc"}, {"path": "B/Data", "data": b"def"}]).data

    def changed(entries: Sequence[Any]) -> bytes:
        first = entries[0]
        assert isinstance(first, compound_writer.Storage)
        return real([compound_writer.Storage("A", (("Data", b"abX"),))])

    monkeypatch.setattr(compound_writer, "write_compound", changed)
    verdict = rt_a0(bytes(data), kind="altium_pcblib")
    assert verdict.different == ("A/Data", "B", "B/Data") and verdict.difference == "A/Data"
    assert verdict.streams == 2 and not verdict.passed


def test_rt_a0_file_past_the_writers_limit() -> None:
    """A file whose FAT needs 240 sectors: the writer writes no DIFAT sector."""
    built = build(
        [{"path": "Data", "data": bytes(range(256)) * 2 * 30_460}, {"path": "S/Small", "data": b"x"}]
    )
    header = cfb.open_compound(bytes(built.data)).header
    assert header.fat_sectors == 240 and header.difat_sectors >= 1
    verdict = rt_a0(bytes(built.data), kind="altium_pcbdoc")
    assert (verdict.judged, verdict.passed, verdict.reason) == (False, False, "too-large")
    assert verdict.streams == 2


def test_rt_a0_writer_refused() -> None:
    built = build([{"path": "Data", "data": b"x"}, {"path": "Empty", "kind": "storage"}])
    verdict = rt_a0(bytes(built.data), kind="altium_schlib")
    assert (verdict.judged, verdict.reason) == (False, "writer-refused")


@pytest.mark.parametrize(
    ("name", "kind"),
    [("blink/blink.PrjPcb", "altium_prjpcb"), ("sample/altium_sample.SchDoc", "altium_schdoc_ascii")],
)
def test_rt_a0_text_file(name: str, kind: str) -> None:
    verdict = rt_a0((DATA / name).read_bytes(), kind=kind)
    assert (verdict.judged, verdict.passed, verdict.reason, verdict.streams) == (
        False,
        False,
        "not-a-container",
        0,
    )


def test_rt_a0_reader_error_and_unknown_kind() -> None:
    data = (BLINK / "blink.PcbDoc").read_bytes()
    with pytest.raises(cfb.CompoundError):
        rt_a0(data[:100], kind="altium_pcbdoc", file="cut.PcbDoc")
    with pytest.raises(ValueError, match="kicad_pcb"):
        rt_a0(data, kind="kicad_pcb")
    with pytest.raises(ValueError, match="kicad_pcb"):
        rt_a1(data, kind="kicad_pcb")


@pytest.mark.parametrize("path", OWN, ids=_id)
def test_rt_a1_own(path: Path) -> None:
    kind = kind_of(path)
    verdict = rt_a1(path.read_bytes(), kind=kind, file=path.name)
    assert verdict.level == "RT-A1" and verdict.judged and verdict.passed
    assert verdict.bytes_equal == verdict.streams >= 1 and verdict.records >= 1
    assert verdict.different == () and verdict.difference == ""
    assert verdict.evidence == EVIDENCE_RT_A1[kind]


def test_rt_a1_counts_of_the_blink_board() -> None:
    data = (BLINK / "blink.PcbDoc").read_bytes()
    verdict = rt_a1(data, kind="altium_pcbdoc")
    document = pcb.read_pcbdoc(data)
    assert verdict.streams == len(document.parts)
    assert verdict.opaque_count >= len(cfb.open_compound(data).streams()) - verdict.streams
    library = (BLINK / "blink.PcbLib").read_bytes()
    assert rt_a1(library, kind="altium_pcblib").streams == len(pcblib.read_pcblib(library).footprints)


def _drop_last_field(stream: bytes, record: int) -> bytes:
    frames = list(framing.deframe(stream, where="FileHeader"))
    payload = frames[record].payload
    assert payload.endswith(b"\0") and payload.count(b"|") > 2
    cut = payload[: payload.rindex(b"|")] + b"\0"
    return framing.enframe([*frames[:record], (frames[record].kind, cut), *frames[record + 1 :]])


def test_rt_a1_encoder_that_changes_a_record(monkeypatch: pytest.MonkeyPatch) -> None:
    real = CODECS["altium_schdoc_binary"]

    def encode(document: Any, path: str) -> bytes:
        data = real.encode(document, path)
        return _drop_last_field(data, 3) if path == "FileHeader" else data

    patched = dict(CODECS) | {"altium_schdoc_binary": dataclasses.replace(real, encode=encode)}
    monkeypatch.setattr(roundtrip, "CODECS", patched)
    path = DATA / "sample" / "binary" / "altium_sample.SchDoc"
    verdict = rt_a1(path.read_bytes(), kind="altium_schdoc_binary", file=path.name)
    assert verdict.judged and not verdict.passed
    assert verdict.different == ("FileHeader",) and verdict.difference == "FileHeader#3"
    assert verdict.bytes_equal == verdict.streams - 1


def test_rt_a1_encoder_that_drops_a_record(monkeypatch: pytest.MonkeyPatch) -> None:
    real = CODECS["altium_schdoc_binary"]

    def encode(document: Any, path: str) -> bytes:
        data = real.encode(document, path)
        if path != "FileHeader":
            return data
        return framing.enframe(framing.deframe(data, where=path)[:-1])

    patched = dict(CODECS) | {"altium_schdoc_binary": dataclasses.replace(real, encode=encode)}
    monkeypatch.setattr(roundtrip, "CODECS", patched)
    path = DATA / "sample" / "binary" / "altium_sample.SchDoc"
    verdict = rt_a1(path.read_bytes(), kind="altium_schdoc_binary")
    assert verdict.different == ("FileHeader",) and verdict.difference == "FileHeader"


def _line_codec(encode: Any) -> StreamCodec:
    """A fake codec of a text kind: its records are the lines without their line ends."""
    return StreamCodec(
        read=lambda data, file: data,
        streams=lambda reading: ("text",),
        encode=encode,
        records=lambda reading, path: tuple(reading.split()),
        opaque=lambda reading: 0,
    )


def test_rt_a1_encoder_that_only_changes_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Equal records with other bytes is a pass, and the stream is not counted in ``bytes_equal``."""
    codec = _line_codec(lambda reading, path: reading.replace(b"\n", b"\r\n"))
    monkeypatch.setattr(roundtrip, "CODECS", dict(CODECS) | {"altium_prjpcb": codec})
    verdict = rt_a1(b"[Design]\nVersion=1.0\n", kind="altium_prjpcb")
    assert verdict.passed and verdict.streams == 1 and verdict.bytes_equal == verdict.streams - 1
    assert verdict.records == 2


def test_rt_a1_unreadable_encoding_and_unwritable_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(data: bytes, file: str) -> bytes:
        if data.startswith(b"bad"):
            raise FormatError("not a project", file=file)
        return data

    codec = dataclasses.replace(_line_codec(lambda reading, path: b"bad"), read=refuse)
    monkeypatch.setattr(roundtrip, "CODECS", dict(CODECS) | {"altium_prjpcb": codec})
    verdict = rt_a1(b"a\nb\n", kind="altium_prjpcb")
    assert not verdict.passed and verdict.different == ("text",) and verdict.difference == "text"
    with pytest.raises(FormatError):
        rt_a1(b"bad", kind="altium_prjpcb")
    # A compound file whose encoded stream differs and that the writer cannot write is not judged.
    real = CODECS["altium_schdoc_binary"]
    changed = dataclasses.replace(
        real, encode=lambda document, path: real.encode(document, path) + b"\0\0\0\0"
    )
    monkeypatch.setattr(roundtrip, "CODECS", dict(CODECS) | {"altium_schdoc_binary": changed})

    def too_large(entries: Any) -> bytes:
        raise compound_writer.CompoundTooLarge("too large")

    monkeypatch.setattr(compound_writer, "write_compound", too_large)
    data = (DATA / "sample" / "binary" / "altium_sample.SchDoc").read_bytes()
    verdict = rt_a1(data, kind="altium_schdoc_binary")
    assert (verdict.judged, verdict.reason, verdict.bytes_equal) == (False, "too-large", 0)


def test_rt_a1_unknown_records_are_counted() -> None:
    data = schdoc([SHEET, "|RECORD=25|TEXT=A", "|RECORD=9999|FOO=1"])
    document = sch.read_schematic(data)
    assert sum(isinstance(r, sch.UnknownRecord) for r in document.records) == 1
    verdict = rt_a1(data, kind="altium_schdoc_binary")
    assert verdict.passed and verdict.opaque_count == 1 and verdict.bytes_equal == verdict.streams
    extra = schdoc([SHEET, "|RECORD=9999|FOO=1"], extra=[("Whole", b"kept")])
    assert rt_a1(extra, kind="altium_schdoc_binary").opaque_count == 2


def test_rt_a1_nan_is_equal_to_itself() -> None:
    nan = float("nan")
    assert roundtrip.first_unequal([(1, nan), {"a": [nan]}], [(1, nan), {"a": [nan]}]) is None
    assert roundtrip.first_unequal([(1, nan)], [(1, 2.0)]) == 0
    assert roundtrip.first_unequal([1, "a"], [1, b"a"]) == 1


def test_evidence_of_the_levels() -> None:
    """``INFERRED`` with the level's hypothesis until the corpus run confirms the row; never above the
    reader's level, and never an oracle label."""
    register = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    assert set(EVIDENCE_RT_A1) == set(CODECS)
    assert register["H-A-RD-PRJ-INI"].level is PROJECT_READ_EVIDENCE.level
    for evidence, row in (
        (EVIDENCE_RT_A0, "H-A-VER-RTA0"),
        *((e, "H-A-VER-RTA1") for e in EVIDENCE_RT_A1.values()),
    ):
        confirmed = register[row].result.startswith("confirmed")
        assert (row in evidence.hypotheses) is not confirmed
        if not confirmed:
            assert evidence.level is Level.INFERRED
        assert evidence.level in (Level.INFERRED, Level.CORPUS_VERIFIED) and evidence.oracle is None
    assert EVIDENCE_RT_A1["altium_schlib"].level is Evidence.combine(sch.EVIDENCE).level


def _round_trips_section() -> str:
    text = (ROOT / "docs" / "altium.md").read_text(encoding="utf-8")
    start = text.index("## Round trips\n")
    return text[start : text.index("\n## ", start + 1)]


def test_scope_documented() -> None:
    """Scenario "Left-out fields are documented": every field of a scoped kind is in the scope, or the
    section "Round trips" of ``docs/altium.md`` names it in the row of its kind, with a reason."""
    section = _round_trips_section()
    left_out: dict[str, set[str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[2].startswith(REASONS):
            left_out.setdefault(cells[0].strip("`"), set()).update(re.findall(r"`([a-z_]+)`", cells[1]))
    assert set(left_out) <= set(RT_A2_SCOPE.fields)
    for kind, fields in RT_A2_SCOPE.fields.items():
        cls = KIND_CLASSES.get(kind)
        if cls is None:
            assert fields == () and kind == "no_connect"
            continue
        every = {f.name for f in dataclasses.fields(cls)} - NEVER - {"ext"}
        assert set(fields) <= every, kind
        assert every - set(fields) == left_out.get(kind, set()), kind
        assert f"| `{kind}` | " + ", ".join(f"`{name}`" for name in fields) in section, kind


REASONS = ("the writer does not write it", "the writer writes a fixed value", "the reader maps it elsewhere")
MINIMUM = {
    "component": ("ref", "value"),
    "net": ("name", "members"),
    "no_connect": (),
    "footprint": ("position", "rotation", "side"),
    "pad": ("number", "net_id", "position", "size"),
    "track": ("start", "end", "width", "layer", "net_id"),
    "arc": ("start", "mid", "end", "width", "layer", "net_id"),
    "via": ("position", "diameter", "drill", "net_id"),
    "zone": ("outline", "layers", "net_id"),
    "netclass": ("name",),
}


def test_scope_holds_the_required_fields() -> None:
    """The scope never shrinks below the list of "Round-trip level RT-A2"; the tolerance is 2 nm."""
    assert RT_A2_SCOPE.length_tolerance == 2
    for kind, fields in MINIMUM.items():
        assert set(fields) <= set(RT_A2_SCOPE.fields[kind]), kind
    assert set(STAGE_EVIDENCE) == {
        "erc.lite",
        "copper.clearance",  # c0088
        "parity",  # c0088
        "netlist.assignment_compare",
        "roundtrip.rta2",
    }
    assert EVIDENCE_RT_A2.level is Level.INFERRED and STAGE_EVIDENCE["roundtrip.rta2"] is EVIDENCE_RT_A2
    register = {row.id: row for row in load_register(ROOT / "docs" / "hypotheses.md")}
    for evidence in STAGE_EVIDENCE.values():
        (name,) = evidence.hypotheses
        assert not register[name].result.startswith("refuted"), name
        assert evidence.level is register[name].level, name


def test_roundtrip_module_works_on_bytes_only() -> None:
    """``roundtrip`` parses nothing and touches no file: it imports no path, process or binary-layout
    module, and calls no ``open``. Its only project imports are the readers, the compound writer, the
    import's evidence and the neutral types."""
    tree = ast.parse(Path(roundtrip.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            assert name not in {"open", "read_bytes", "write_bytes", "write_text", "exec", "eval"}, name
    assert not imported & {"struct", "pathlib", "os", "subprocess", "io", "math", "tempfile"}
    project = {name for name in imported if name.startswith("fenolite.")}
    assert project == {
        "fenolite.backends.altium",
        "fenolite.backends.altium.read",
        "fenolite.backends.altium.read.pcbprims",
        "fenolite.backends.base",
        "fenolite.core.errors",
        "fenolite.core.evidence",
    }
