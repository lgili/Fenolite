# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The documents of an Altium input (capability altium-verification, "Altium document sets"; change
c0044)."""

from __future__ import annotations

import builtins
import shutil
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.altium.backend import READ_KINDS
from fenolite.backends.altium.docset import COMPOUND_SIGNATURE, ROLES, SUFFIX_KINDS, document_set, kind_of
from fenolite.backends.altium.read import cfb

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "altium"
BLINK = DATA / "blink"


def _blink(tmp_path: Path) -> Path:
    return Path(shutil.copytree(BLINK, tmp_path / "blink"))


def test_blink_project() -> None:
    found = document_set(BLINK / "blink.PrjPcb")
    assert (found.root, found.project, found.board) == (BLINK, "blink.PrjPcb", "blink.PcbDoc")
    assert [(d.name, d.role) for d in found.documents] == [
        ("blink.PcbDoc", "pcb"),
        ("blink.PcbLib", "footprint-library"),
        ("blink.PrjPcb", "project"),
        ("blink.SchDoc", "schematic"),
        ("blink.SchLib", "symbol-library"),
    ]
    assert found.missing == ()
    assert document_set(BLINK) == found


def test_roles_cover_the_read_kinds() -> None:
    assert set(ROLES) == set(READ_KINDS)
    assert {kind for kinds in SUFFIX_KINDS.values() for kind in kinds} == set(READ_KINDS)
    assert COMPOUND_SIGNATURE == cfb.SIGNATURE


def test_ascii_and_binary_schematics() -> None:
    ascii_set = document_set(DATA / "sample" / "altium_sample.SchDoc")
    binary_set = document_set(DATA / "sample" / "binary" / "altium_sample.SchDoc")
    assert [d.kind for d in ascii_set.documents] == ["altium_schdoc_ascii"]
    assert [d.kind for d in binary_set.documents] == ["altium_schdoc_binary"]
    assert ascii_set.project is None and ascii_set.board is None
    assert ascii_set.root == DATA / "sample"


def test_one_document_alone() -> None:
    board = document_set(BLINK / "blink.PcbDoc")
    assert (board.project, board.board) == (None, "blink.PcbDoc")
    assert [(d.name, d.kind, d.role) for d in board.documents] == [("blink.PcbDoc", "altium_pcbdoc", "pcb")]
    library = document_set(BLINK / "blink.PcbLib")
    assert library.board is None and library.documents[0].role == "footprint-library"


def test_listed_document_absent(tmp_path: Path) -> None:
    root = _blink(tmp_path)
    (root / "blink.PcbLib").unlink()
    found = document_set(root / "blink.PrjPcb")
    assert found.missing == ("blink.PcbLib",) and len(found.documents) == 4


def test_listed_paths(tmp_path: Path) -> None:
    """Backslashes are separators; a path outside the folder or of another suffix is left out; a name that
    differs in letter case is the one on disk; a document listed twice is one document."""
    root = tmp_path / "p"
    (root / "sub").mkdir(parents=True)
    (tmp_path / "outside.SchDoc").write_bytes(b"|HEADER=x")
    (root / "sub" / "Sheet.SchDoc").write_bytes(b"|HEADER=x")
    (root / "notes.txt").write_text("x")
    listed = ["sub\\sheet.schdoc", "sub/Sheet.SchDoc", "..\\outside.SchDoc", "C:\\x\\y.PcbDoc", "notes.txt",
              "/abs/z.PcbDoc", "gone\\b.PcbDoc"]  # fmt: skip
    body = "[Design]\nVersion=1.0\n" + "".join(
        f"\n[Document{n}]\nDocumentPath={path}\n" for n, path in enumerate(listed, 1)
    )
    (root / "p.PrjPcb").write_text(body)
    found = document_set(root)
    assert [d.name for d in found.documents] == ["p.PrjPcb", "sub/Sheet.SchDoc"]
    assert found.documents[1].kind == "altium_schdoc_ascii"
    assert found.missing == ("gone/b.PcbDoc",) and found.board is None


def test_board_choice(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    for name in ("a.PcbDoc", "MAIN.PcbDoc", "z.PcbDoc"):
        (root / name).write_bytes(COMPOUND_SIGNATURE)
    body = "".join(
        f"[Document{n}]\nDocumentPath={name}\n" for n, name in enumerate(("z.PcbDoc", "a.PcbDoc"), 1)
    )
    (root / "main.PrjPcb").write_text(body)
    assert document_set(root).board == "a.PcbDoc"
    (root / "main.PrjPcb").write_text(body + "[Document3]\nDocumentPath=MAIN.PcbDoc\n")
    assert document_set(root).board == "MAIN.PcbDoc"


def test_folder_with_two_project_files(tmp_path: Path) -> None:
    for name in ("a.PrjPcb", "b.PrjPcb"):
        (tmp_path / name).write_text("[Design]\n")
    with pytest.raises(ValueError, match=r"a\.PrjPcb, b\.PrjPcb"):
        document_set(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="holds 0 project files"):
        document_set(empty)


def test_missing_path_and_other_suffix(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        document_set(tmp_path / "gone.PcbDoc")
    other = tmp_path / "x.kicad_pcb"
    other.write_text("(kicad_pcb)")
    with pytest.raises(ValueError, match="not an Altium"):
        document_set(other)
    with pytest.raises(ValueError, match="not an Altium"):
        kind_of(other)


def test_reads_eight_bytes_and_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = _blink(tmp_path)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    real_open = builtins.open
    seen: list[tuple[str, int]] = []

    class Counting:
        def __init__(self, handle: Any, name: str) -> None:
            self.handle, self.name = handle, name

        def read(self, size: int = -1) -> bytes:
            data: bytes = self.handle.read(size)
            seen.append((self.name, len(data)))
            return data

        def __enter__(self) -> Counting:
            return self

        def __exit__(self, *args: object) -> None:
            self.handle.close()

        def __getattr__(self, item: str) -> Any:
            return getattr(self.handle, item)

    def counting(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        assert "w" not in mode and "a" not in mode and "+" not in mode, mode
        handle = real_open(file, mode, *args, **kwargs)
        return Counting(handle, Path(str(file)).name) if "b" in mode else handle

    monkeypatch.setattr(builtins, "open", counting)
    monkeypatch.setattr("io.open", counting)
    document_set(root / "blink.PrjPcb")
    assert all(size <= 8 for name, size in seen if name != "blink.PrjPcb"), seen
    assert ("blink.SchDoc", 8) in seen
    monkeypatch.undo()
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
