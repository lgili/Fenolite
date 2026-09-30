# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The residue scan engine on planted trees (generated here, never committed)."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import _scanmod
import pytest

scan = _scanmod.load()
TOKEN = "Zyxquorp Industries"  # a made-up private token for the tests
# Planted paths are assembled at run time so that this file itself stays free of residue.
USERS = "/" + "Users"
HOME = "/" + "home"


@pytest.fixture(autouse=True)
def _no_private_lists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for var in ("FENOLITE_RESIDUE_TOKENS", "FENOLITE_RESIDUE_TOKENS_FILE", "FENOLITE_RESIDUE_BLOBS_FILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _tree(root: Path, files: dict[str, bytes]) -> Path:
    for rel, data in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def _run(capsys: pytest.CaptureFixture[str], root: Path) -> tuple[int, str]:
    code = scan.main(["--root", str(root)])
    return code, capsys.readouterr().out


def test_clean_tree(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path / "t", {"src/a.py": b"x = 1\n", "docs/b.md": b"# ok\n"})
    code, out = _run(capsys, root)
    assert code == 0
    assert "private gate: skipped" in out and "2 file(s) scanned" in out


def test_structural_hit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path / "t", {"examples/x/notes.md": f"see {USERS}/alice/boards/x\n".encode()})
    code, out = _run(capsys, root)
    assert code == 5
    assert "examples/x/notes.md:4:abs-user-path" in out


def test_numeric_codes_only_in_data_paths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _tree(tmp_path / "t", {"src/a.py": b"N = 123456789\n", "examples/bom.csv": b"R1,123456789\n"})
    code, out = _run(capsys, root)
    assert code == 5
    assert "examples/bom.csv:3:numeric-code" in out and "src/a.py" not in out


def test_private_token_never_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                     monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setenv("FENOLITE_RESIDUE_TOKENS", TOKEN)
    root = _tree(tmp_path / "t", {"docs/x.md": f"Made by {TOKEN.upper()}.\n".encode()})
    code, out = _run(capsys, root)
    assert code == 5
    assert "docs/x.md:8:private-token-1" in out
    assert TOKEN.lower() not in out.lower() and "private gate: on" in out


def test_utf16_content(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FENOLITE_RESIDUE_TOKENS", TOKEN)
    root = _tree(tmp_path / "t", {"tests/data/x.bin": b"\x00\x01" + TOKEN.encode("utf-16le") + b"\x00\x00"})
    code, out = _run(capsys, root)
    assert code == 5 and "tests/data/x.bin:2:private-token-1" in out


def test_regex_token(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FENOLITE_RESIDUE_TOKENS", r"re:\bQX-\d{3}\b")
    root = _tree(tmp_path / "t", {"docs/x.md": b"code QX-042 here\n"})
    code, out = _run(capsys, root)
    assert code == 5 and "docs/x.md:5:private-token-1" in out


def test_zip_member(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pkg/data.txt", f"path {HOME}/bob/x\n", compress_type=zipfile.ZIP_DEFLATED)
    root = _tree(tmp_path / "t", {"dist/pkg-0.1-py3-none-any.whl": buffer.getvalue()})
    hits, _ = scan.scan(root, scan.load_config(), [("dist/pkg-0.1-py3-none-any.whl", buffer.getvalue())])
    assert [h.line() for h in hits] == ["dist/pkg-0.1-py3-none-any.whl!pkg/data.txt:5:abs-user-path"]
    code, out = _run(capsys, root)  # the tree walker also picks up dist/*.whl
    assert code == 5 and "!pkg/data.txt:5:abs-user-path" in out


def test_blob_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = b"a non-public template, byte for byte\n"
    blobs = tmp_path / "blobs.sha256"
    blobs.write_text(f"{hashlib.sha256(data).hexdigest()} private-blob-0001\n")
    monkeypatch.setenv("FENOLITE_RESIDUE_BLOBS_FILE", str(blobs))
    root = _tree(tmp_path / "t", {"examples/frame.bin": data})
    code, out = _run(capsys, root)
    assert code == 5 and "examples/frame.bin:0:known-blob" in out


def test_waiver(tmp_path: Path) -> None:
    config = scan.load_config()
    config.waivers.append(("examples/bom.csv", "numeric-code"))
    hits, count = scan.scan(tmp_path, config, [("examples/bom.csv", b"R1,123456789\n")])
    assert hits == [] and count == 1


def test_exclusions(tmp_path: Path) -> None:
    config = scan.load_config()
    hits, count = scan.scan(tmp_path, config, [("uv.lock", f"{USERS}/alice/\n".encode())])
    assert hits == [] and count == 0


def test_staged_mode_reads_the_index(tmp_path: Path) -> None:
    import subprocess

    root = tmp_path / "repo"
    root.mkdir()
    git = ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([*git, "init", "-q"], check=True)
    (root / "a.md").write_text(f"see {USERS}/carol/x\n")
    subprocess.run([*git, "add", "a.md"], check=True)
    (root / "a.md").write_text("clean now\n")  # the index still holds the leaked version
    hits, _ = scan.scan(root, scan.load_config(), scan.staged_files(root))
    assert [h.pattern for h in hits] == ["abs-user-path"]
