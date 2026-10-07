# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/kicad_libs_fetch.py --models`` with both requests replaced (capability
kicad-library-resolution, "3D model fetch"; change c0116). No test touches the network: ``head`` and
``download`` of the tool are replaced, and the "model" bytes are authored here."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from importlib import resources
from pathlib import Path
from types import ModuleType

import pytest
from _models import model_board, official

from fenolite.backends.kicad import libcache

ROOT = Path(__file__).resolve().parents[2]
TAG = "10.0.6"
RELS = ("Fenolite.3dshapes/Box_2x1.step", "Fenolite.3dshapes/Box 4x2.wrl")
BYTES = {RELS[0]: b"ISO-10303-21; authored box\n", RELS[1]: b"#VRML V2.0 utf8 authored box\n"}


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "kicad_libs_fetch_models", ROOT / "tools" / "kicad_libs_fetch.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool() -> ModuleType:
    return _load_tool()


def _board(tmp_path: Path, *paths: str) -> Path:
    board = tmp_path / "b.kicad_pcb"
    board.write_text(model_board({f"U{i + 1}": [path] for i, path in enumerate(paths)}), encoding="utf-8")
    return board


def _pin() -> libcache.ModelPin:
    return next(pin for pin in libcache.load_model_pins() if pin.tag == TAG)


class Server:
    """What stands in for GitLab: the headers of a file and its bytes, and a log of the requests."""

    def __init__(self, files: dict[str, bytes], *, served: dict[str, bytes] | None = None) -> None:
        self.files = files
        self.served = files if served is None else served
        self.requests: list[tuple[str, str]] = []

    def _rel(self, tool: ModuleType, url: str, *, raw: bool) -> str:
        pin = _pin()
        for rel in self.files:
            if url == tool.file_url(pin, rel, raw=raw):
                return rel
        raise AssertionError(f"unexpected URL {url}")

    def install(self, tool: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
        def head(url: str) -> dict[str, str]:
            self.requests.append(("HEAD", url))
            data = self.files[self._rel(tool, url, raw=False)]
            return {tool.SIZE_HEADER: str(len(data)), tool.SHA_HEADER: hashlib.sha256(data).hexdigest()}

        def download(url: str, target: Path, limit: int = 0) -> int:
            self.requests.append(("GET", url))
            data = self.served[self._rel(tool, url, raw=True)]
            target.write_bytes(data)
            return len(data)

        monkeypatch.setattr(tool, "head", head)
        monkeypatch.setattr(tool, "download", download)


def _refuse(tool: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a request was made")

    monkeypatch.setattr(tool, "head", refuse)
    monkeypatch.setattr(tool, "download", refuse)


def test_fetch_and_stamp(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    board = _board(tmp_path, *(official(rel) for rel in RELS))
    server = Server(BYTES)
    server.install(tool, monkeypatch)
    cache = tmp_path / "C"
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert sorted(lines) == sorted(f"{official(rel)}: fetched" for rel in RELS)
    folder = cache / TAG / "kicad-packages3D"
    for rel in RELS:
        assert (folder / rel).read_bytes() == BYTES[rel]
    assert libcache.read_model_stamp(folder) == {rel: hashlib.sha256(BYTES[rel]).hexdigest() for rel in RELS}
    assert [method for method, _ in server.requests] == ["HEAD", "GET", "HEAD", "GET"]
    # the commit of the pin and the URL-encoded path are in every request; no archive is asked for
    assert all(f"?ref={_pin().commit}" in url and "archive" not in url for _, url in server.requests)
    assert any("Box%204x2.wrl" in url for _, url in server.requests)
    assert sorted(p.name for p in (cache / TAG).iterdir()) == ["kicad-packages3D"]

    # cached files are not requested again
    _refuse(tool, monkeypatch)
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 0
    assert sorted(capsys.readouterr().out.splitlines()) == sorted(f"{official(rel)}: cached" for rel in RELS)
    assert tool.main(["--cache", str(cache), "--models", "--verify"]) == 0


def test_a_changed_cached_file_is_fetched_again_and_verify_names_it(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    board = _board(tmp_path, official(RELS[0]))
    server = Server(BYTES)
    server.install(tool, monkeypatch)
    cache = tmp_path / "C"
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 0
    target = cache / TAG / "kicad-packages3D" / RELS[0]
    target.write_bytes(b"edited")
    capsys.readouterr()
    assert tool.main(["--cache", str(cache), "--models", "--verify"]) == 5
    assert f"{TAG}/kicad-packages3D/{RELS[0]}: failed" in capsys.readouterr().out
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 0
    assert capsys.readouterr().out.strip().endswith("fetched") and target.read_bytes() == BYTES[RELS[0]]


def test_digest_mismatch(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    board = _board(tmp_path, official(RELS[0]))
    Server(BYTES, served={RELS[0]: b"other bytes of another length"}).install(tool, monkeypatch)
    cache = tmp_path / "C"
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 5
    assert capsys.readouterr().out.startswith(f"{official(RELS[0])}: failed (")
    folder = cache / TAG / "kicad-packages3D"
    assert not (folder / RELS[0]).exists()
    assert libcache.read_model_stamp(folder) == {}
    assert list((cache / TAG).iterdir()) == []  # no temporary file is left


def test_a_failed_file_leaves_the_older_copy_and_its_stamp(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board = _board(tmp_path, *(official(rel) for rel in RELS))
    Server(BYTES).install(tool, monkeypatch)
    cache = tmp_path / "C"
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 0
    folder = cache / TAG / "kicad-packages3D"
    stamp = libcache.read_model_stamp(folder)
    (folder / RELS[0]).write_bytes(b"edited")  # no longer its stamp entry: it is asked for again
    Server(BYTES, served={**BYTES, RELS[0]: b"wrong"}).install(tool, monkeypatch)
    assert tool.main(["--cache", str(cache), "--models", str(board)]) == 5
    assert (folder / RELS[0]).read_bytes() == b"edited" and libcache.read_model_stamp(folder) == stamp
    assert sorted(p.name for p in (cache / TAG).iterdir()) == ["kicad-packages3D"]


def test_too_large_a_file_is_refused_before_the_download(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert tool.MAX_MODEL_BYTES == 64 * 2**20
    board = _board(tmp_path, official(RELS[0]))
    headers = {tool.SIZE_HEADER: str(tool.MAX_MODEL_BYTES + 1), tool.SHA_HEADER: "a" * 64}
    monkeypatch.setattr(tool, "head", lambda url: headers)
    monkeypatch.setattr(tool, "download", lambda *a, **k: pytest.fail("downloaded"))
    assert tool.main(["--cache", str(tmp_path / "C"), "--models", str(board)]) == 3
    assert "failed" in capsys.readouterr().out
    monkeypatch.setattr(tool, "head", lambda url: {})
    assert tool.main(["--cache", str(tmp_path / "C"), "--models", str(board)]) == 3


def test_models_of_another_library_are_skipped(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = ("${KIPRJMOD}/models/x.step", "${KICAD8_3DMODEL_DIR}/y.step", "${KICAD10_3DMODEL_DIR}/../z.step")
    board = _board(tmp_path, *paths)
    _refuse(tool, monkeypatch)
    assert tool.main(["--cache", str(tmp_path / "C"), "--models", str(board)]) == 0
    assert sorted(capsys.readouterr().out.splitlines()) == sorted(f"{path}: skipped" for path in paths)
    assert not (tmp_path / "C").exists()


def test_footprint_files_are_read_too(
    tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    footprint = tmp_path / "Box.kicad_mod"
    footprint.write_text(f'(footprint "Box" (model "{official(RELS[0])}"))', encoding="utf-8")
    Server(BYTES).install(tool, monkeypatch)
    assert tool.main(["--cache", str(tmp_path / "C"), "--models", str(footprint)]) == 0
    assert capsys.readouterr().out.strip() == f"{official(RELS[0])}: fetched"


def test_usage_errors(tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert tool.main(["--cache", str(tmp_path), "--models"]) == 2
    assert tool.main(["--cache", str(tmp_path), "--models", "x.kicad_pcb", "--repo", "kicad-symbols"]) == 2
    assert tool.main(["--cache", str(tmp_path), "--models", "x.kicad_pcb", "--tag", "1.0.0"]) == 2
    assert tool.main(["--cache", str(tmp_path), "--models", str(tmp_path / "absent.kicad_pcb")]) == 3
    text = resources.files("fenolite.backends.kicad").joinpath("data/libraries.toml").read_text("utf-8")
    pins = tmp_path / "pins.toml"
    pins.write_text(text[: text.index("[[models]]")], encoding="utf-8")
    assert tool.main(["--cache", str(tmp_path), "--pins", str(pins), "--models", "x.kicad_pcb"]) == 2
    assert "pins file" in capsys.readouterr().err
