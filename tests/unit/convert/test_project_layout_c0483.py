# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The source's project layout through a conversion and an import (change c0483; capability
design-conversion): sheet file names, document folders, document order and the documents Fenolite does not
model, whose bytes travel beside the KiCad project or the Python script.

The source is authored here: the hierarchy example built for Altium by Fenolite (``_drawings.hier_board``),
its documents moved into folders and extra documents of made-up bytes listed in its project file."""

from __future__ import annotations

from pathlib import Path

import pytest
from _drawings import hier_board
from _importcode import STAMP

from fenolite.api import run
from fenolite.backends.altium.prjpcb import (
    CARRIED_FOLDER,
    carried_kind,
    documents_of,
    documents_text,
    laid_out,
)
from fenolite.backends.altium.read.project import read_project

EXTRA = {
    "PCB/second.PcbDoc": b"second board\x00",
    "PCB/board.PCBDwf": b"draftsman\x00\x01",
    "SCH/a.Harness": b"harness\r\n",
    "LIB/parts.IntLib": b"intlib\x00",
}


def _paths(project: Path) -> list[str]:
    return [d.posix for d in read_project(project.read_bytes(), file=project.name).documents]


@pytest.fixture(scope="module")
def source(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The authored hierarchy with its sheets in ``SCH/``, its board in ``PCB/``, four extra documents and a
    ``.PrjPcbStructure`` beside the project."""
    folder = tmp_path_factory.mktemp("layout") / "src"
    project = hier_board(folder)
    text = project.read_bytes().decode("ascii")
    for file in sorted(folder.iterdir()):
        sub = {".SchDoc": "SCH", ".PcbDoc": "PCB"}.get(file.suffix)
        if sub is not None:
            (folder / sub).mkdir(exist_ok=True)
            file.rename(folder / sub / file.name)
            text = text.replace(f"={file.name}\r\n", f"={sub}\\{file.name}\r\n")
    count = text.count("[Document")
    for index, (path, data) in enumerate(EXTRA.items(), start=count + 1):
        (folder / path).parent.mkdir(exist_ok=True)
        (folder / path).write_bytes(data)
        section = f"[Document{index}]\r\nDocumentPath={path.replace('/', chr(92))}\r\n\r\n"
        text = text.replace("[PrjClassGen]", section + "[PrjClassGen]")
    project.write_bytes(text.encode("ascii"))
    project.with_suffix(".PrjPcbStructure").write_bytes(b"structure\r\n")
    return project


def _check_layout(written: Path, source: Path, *, name: str) -> None:
    expected = [
        f"PCB/{name}.PcbDoc" if path == f"PCB/{source.stem}.PcbDoc" else path for path in _paths(source)
    ]
    assert _paths(written)[: len(expected)] == expected
    for path in _paths(written):
        assert (written.parent / path).is_file(), path
    for path, data in EXTRA.items():
        assert (written.parent / path).read_bytes() == data
    structure = written.with_suffix(".PrjPcbStructure")
    assert structure.read_bytes() == source.with_suffix(".PrjPcbStructure").read_bytes()
    assert not list(written.parent.glob("*_drawn_*.SchDoc"))


@pytest.mark.needs_kicad  # the hierarchical KiCad schematic needs kicad-cli for its netlist
def test_conversion_round_trip_keeps_the_layout(source: Path, tmp_path: Path) -> None:
    """Scenario "A round trip through KiCad keeps the project layout"."""
    kicad = run(
        "convert", str(source), "--to", "kicad", "--out", "k", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert kicad.exit_code == 0, kicad.error
    held = tmp_path / "k" / CARRIED_FOLDER
    assert {p.relative_to(held).as_posix() for p in held.rglob("*") if p.is_file()} == {
        *EXTRA,
        f"{source.stem}.OutJob",
        f"{source.stem}.PrjPcbStructure",
    }
    back = run(
        "convert", str(tmp_path / "k" / f"{source.stem}.kicad_pro"), "--to", "altium", "--out", "a",
        "--name", "rt", "--altium-pour", "outline", "--confirm", "--allow-lossy",
        cwd=tmp_path, timestamp=STAMP,
    )  # fmt: skip
    assert back.exit_code in (0, 5), back.error
    _check_layout(tmp_path / "a" / "rt.PrjPcb", source, name="rt")


@pytest.mark.needs_kicad  # the hierarchical KiCad schematic needs kicad-cli for its netlist
def test_import_and_build_keep_the_layout(source: Path, tmp_path: Path) -> None:
    """Scenario "An import built for Altium keeps the project layout"."""
    imported = run(
        "import", str(source), "--to", "python", "--out", "py", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert imported.exit_code == 0, imported.error
    assert (tmp_path / "py" / CARRIED_FOLDER / "PCB" / "board.PCBDwf").read_bytes() == EXTRA[
        "PCB/board.PCBDwf"
    ]
    built = run(
        "build", "design.py", "--target", "altium", "--out", "alt", "--altium-pour", "outline", "--confirm",
        cwd=tmp_path / "py", timestamp=STAMP,
    )  # fmt: skip
    assert built.exit_code == 0, built.error
    project = next((tmp_path / "py" / "alt").glob("*.PrjPcb"))
    _check_layout(project, source, name=project.stem)


def test_documents_text_round_trip_and_unsafe_paths() -> None:
    text = documents_text(["SCH/a.SchDoc", "../x.OutJob", "C:/y.IntLib", "b.PcbDoc"], {"SCH/a.SchDoc": "/"})
    assert documents_of(text) == [("SCH/a.SchDoc", "/"), ("b.PcbDoc", "")]
    assert documents_of("SCH\\a.SchDoc\tk\n/abs.OutJob\t\n") == [("SCH/a.SchDoc", "k")]


def test_carried_kind() -> None:
    paths = ["a.SchDoc", "b.PcbDoc", "c.PcbDoc", "d.SchLib", "e.PcbLib", "f.IntLib", "g.OutJob", "h.Harness"]
    assert carried_kind(paths) == ["c.PcbDoc", "f.IntLib", "g.OutJob", "h.Harness"]


def test_laid_out_moves_carries_and_relists() -> None:
    project = (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=s.SchDoc\r\nClassGenCCAutoEnabled=1\r\n"
        b"\r\n[Document2]\r\nDocumentPath=n.PcbDoc\r\n\r\n[Document3]\r\nDocumentPath=new.SchLib\r\n"
        b"\r\n[PrjClassGen]\r\nNetClassManualEnabled=1\r\n"
    )
    files = {"n.PrjPcb": project, "s.SchDoc": b"S", "n.PcbDoc": b"P", "new.SchLib": b"L"}
    documents = [
        ("SCH/s.SchDoc", "/"),
        ("x.OutJob", ""),
        ("PCB/src.PcbDoc", ""),
        ("gone.IntLib", ""),
        ("n.PrjPcbStructure", ""),
    ]
    out = laid_out(files, documents, {"x.OutJob": b"O", "n.PrjPcbStructure": b"T"}, name="n")
    assert sorted(out) == [
        "PCB/n.PcbDoc",
        "SCH/s.SchDoc",
        "n.PrjPcb",
        "n.PrjPcbStructure",
        "new.SchLib",
        "x.OutJob",
    ]
    assert out["n.PrjPcb"] == (
        b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=SCH\\s.SchDoc\r\nClassGenCCAutoEnabled=1\r\n"
        b"\r\n[Document2]\r\nDocumentPath=x.OutJob\r\n\r\n[Document3]\r\nDocumentPath=PCB\\n.PcbDoc\r\n"
        b"\r\n[Document4]\r\nDocumentPath=new.SchLib\r\n\r\n[PrjClassGen]\r\nNetClassManualEnabled=1\r\n"
    )
    assert laid_out(files, [], {}, name="n") == files
