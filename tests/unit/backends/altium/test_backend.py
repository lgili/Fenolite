# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium backend (capability altium-import, "Altium backend"; change c0043): detection, the six read
kinds, issue order, skipped documents and capabilities."""

from __future__ import annotations

import builtins
import hashlib
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends import registry
from fenolite.backends.altium import adapter
from fenolite.backends.altium.backend import CAPABILITIES, READ_KINDS, AltiumBackend
from fenolite.backends.base import Backend
from fenolite.core.errors import FormatError, Issue
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.model.library import Library

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "altium"
BLINK = DATA / "blink"


def test_detection_by_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("detect opened a file")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    backend = AltiumBackend()
    names = (
        "a.PcbDoc",
        "a.pcbdoc",
        "a.SCHLIB",
        "a.PrjPcb",
        "a.SchDot",
        "a.kicad_pcb",
        "a.SchDoc",
        "a.PcbLib",
    )
    assert [backend.detect(Path(name)) for name in names] == [
        True,
        True,
        True,
        True,
        False,
        False,
        True,
        True,
    ]


def test_protocol_and_capabilities() -> None:
    backend = AltiumBackend()
    typed: Backend = backend  # the protocol is checked by pyright
    assert typed.name == "altium"
    assert backend.capabilities() is CAPABILITIES
    assert CAPABILITIES.read_kinds == READ_KINDS == (
        "altium_pcbdoc", "altium_pcblib", "altium_prjpcb", "altium_schdoc_ascii", "altium_schdoc_binary",
        "altium_schlib",
    )  # fmt: skip
    assert (
        CAPABILITIES.write_kinds == () and CAPABILITIES.targets == () and CAPABILITIES.default_target is None
    )
    assert CAPABILITIES.downgrade == "unsupported" and CAPABILITIES.operations == ("detect", "read")
    assert CAPABILITIES.evidence == adapter.EVIDENCE
    assert registry.get("altium").name == "altium"
    with pytest.raises(ValueError, match="not an Altium"):
        backend.read(Path("a.kicad_pcb"))


def test_board_read_and_issue_order() -> None:
    issues: list[Issue] = []
    result = AltiumBackend().read(BLINK / "blink.PcbDoc", issues=issues)
    design = result.design
    assert result.evidence == adapter.EVIDENCE and design.board is not None
    assert sorted(design.by_ref) == ["D1", "R1", "U1"]
    assert {pin.etype for c in design.circuit.components for pin in c.pins} == {"unspecified"}
    validation = design.validate()
    assert tuple(result.issues) == (*issues, *validation)
    assert all(i.code.startswith("altium.") for i in issues) and all(
        i.code.startswith("model.") for i in validation
    )


def test_schematic_alone_in_both_forms() -> None:
    ascii_form = AltiumBackend().read(DATA / "sample" / "altium_sample.SchDoc").design
    binary = AltiumBackend().read(DATA / "sample" / "binary" / "altium_sample.SchDoc").design
    assert ascii_form.board is None and binary.board is None and ascii_form.rules is None

    def plain(design: Design) -> str:
        text = canonical.dumps(design.circuit)
        lines = [line for line in text.splitlines() if "file_sha256" not in line and '"locator"' not in line]
        return "\n".join(lines)

    assert plain(ascii_form) == plain(binary)
    assert ascii_form.header.name == "altium_sample"
    assert ascii_form.header.native_ids == {"altium": "altium_schdoc"}


def test_project_read_names_each_file() -> None:
    result = AltiumBackend().read(BLINK / "blink.PrjPcb")
    design = result.design
    assert design.header.name == "blink" and design.board is not None
    r1 = design.by_ref["R1"]
    assert r1.provenance is not None and r1.provenance.file == "blink.SchDoc"
    assert r1.provenance.file_sha256 == hashlib.sha256((BLINK / "blink.SchDoc").read_bytes()).hexdigest()
    (footprint,) = [fp for fp in design.board.footprints if fp.component_id == r1.id]
    assert footprint.provenance is not None and footprint.provenance.file == "blink.PcbDoc"
    assert (
        footprint.provenance.file_sha256 == hashlib.sha256((BLINK / "blink.PcbDoc").read_bytes()).hexdigest()
    )
    assert [
        fp.component_id in {c.id for c in design.circuit.components} for fp in design.board.footprints
    ] == [True] * 3
    codes = {i.code for i in result.issues}
    assert (
        "altium.import.linked-by-designator" not in codes and "altium.import.pcb-only-component" not in codes
    )
    assert [i for i in result.issues if i.severity == "error"] == []


def test_libraries() -> None:
    footprints = AltiumBackend().read(BLINK / "blink.PcbLib").content
    symbols = AltiumBackend().read(BLINK / "blink.SchLib").content
    assert isinstance(footprints, Library) and isinstance(symbols, Library)
    assert footprints.name == "blink" and len(footprints.footprints) == 3 and footprints.symbols == ()
    assert symbols.name == "blink" and len(symbols.symbols) == 3 and symbols.footprints == ()
    with pytest.raises(TypeError):
        _ = AltiumBackend().read(BLINK / "blink.PcbLib").design


def copy_blink(folder: Path, extra: str = "") -> Path:
    folder.mkdir(parents=True)
    for item in BLINK.iterdir():
        (folder / item.name).write_bytes(item.read_bytes())
    project = folder / "blink.PrjPcb"
    if extra:
        project.write_bytes(project.read_bytes() + extra.encode("ascii"))
    return project


def test_skipped_documents(tmp_path: Path) -> None:
    extra = "\r\n".join(
        [
            "", "[Document8]", "DocumentPath=..\\outside\\x.SchDoc", "",
            "[Document9]", "DocumentPath=missing.SchDoc", "",
        ]
    )  # fmt: skip
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "x.SchDoc").write_bytes((BLINK / "blink.SchDoc").read_bytes())
    plain = AltiumBackend().read(copy_blink(tmp_path / "plain"))
    result = AltiumBackend().read(copy_blink(tmp_path / "more", extra))
    skipped = [i for i in result.issues if i.code == "altium.import.document-skipped"]
    assert [i.severity for i in skipped] == ["warning", "warning"]
    assert ["outside-root" in skipped[0].message, "missing" in skipped[1].message] == [True, True]
    rest = [i for i in result.issues if i.code != "altium.import.document-skipped"]
    assert rest == list(plain.issues)

    def parts(design: Design) -> str:
        return canonical.dumps(design.circuit) + canonical.dumps(design.board)

    assert parts(result.design) == parts(plain.design)


def test_unreadable_document_and_nothing_to_read(tmp_path: Path) -> None:
    project = copy_blink(tmp_path / "bad")
    (project.parent / "blink.SchDoc").write_bytes(b"not a schematic")
    result = AltiumBackend().read(project)
    (skipped,) = [i for i in result.issues if i.code == "altium.import.document-skipped"]
    assert "unreadable" in skipped.message and result.design.board is not None
    assert sorted(result.design.by_ref) == ["D1", "R1", "U1"]  # synthesised from the board
    (project.parent / "blink.PcbDoc").unlink()
    with pytest.raises(FormatError, match="no readable sheet"):
        AltiumBackend().read(project)


def test_reader_errors_of_the_file_itself_are_raised(tmp_path: Path) -> None:
    for name in ("a.PcbDoc", "a.SchDoc", "a.PcbLib", "a.SchLib"):
        path = tmp_path / name
        path.write_bytes(b"garbage")
        with pytest.raises(FormatError):
            AltiumBackend().read(path)
    with pytest.raises(FileNotFoundError):
        AltiumBackend().read(tmp_path / "none.PrjPcb")
