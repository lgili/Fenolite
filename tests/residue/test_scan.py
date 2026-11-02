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


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16le", "cp1252"])
@pytest.mark.parametrize("authority", ["example.invalid", "example.invalid:8443", "[::1]:8443"])
@pytest.mark.parametrize("scheme", ["http", "https"])
def test_web_path_is_not_a_local_path(encoding: str, authority: str, scheme: str) -> None:
    local = f"{HOME}/alice/boards"
    text = f"{scheme}://{authority}{local} see {local}"
    hits = scan.scan_bytes("docs/reference.md", text.encode(encoding), scan.load_config())
    expected = len(text[: text.rindex(local)].encode(encoding))
    assert [(hit.pattern, hit.offset) for hit in hits] == [("abs-user-path", expected)]


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        "file://",
        "file://localhost",
        "C:",
        "https://example.invalid/?path=",
        "https://example.invalid/#path=",
        "https://[invalid/",
        "https://example.invalid:bad/",
        "https:///",
    ],
)
def test_non_web_path_components_still_report(prefix: str) -> None:
    path = f"{USERS}/alice/boards"
    hits = scan.scan_bytes("docs/reference.md", (prefix + path).encode(), scan.load_config())
    assert any(hit.pattern == "abs-user-path" for hit in hits)


def test_private_tokens_are_checked_inside_web_paths() -> None:
    config = scan.load_config(environ={"FENOLITE_RESIDUE_TOKENS": "Zyxquorp"})
    text = f"https://example.invalid{HOME}/alice/Zyxquorp/"
    hits = scan.scan_bytes("docs/reference.md", text.encode(), config)
    assert [hit.pattern for hit in hits] == ["private-token-1"]


def test_known_blob_is_checked_even_when_its_only_path_is_a_url() -> None:
    data = f"https://example.invalid{HOME}/alice/boards".encode()
    config = scan.load_config()
    config.blobs[hashlib.sha256(data).hexdigest()] = "authored-reference"
    hits = scan.scan_bytes("docs/reference.md", data, config)
    assert [hit.pattern for hit in hits] == ["known-blob"]


def test_url_scope_preserves_other_structural_patterns() -> None:
    revision = "v2" + "rQ"
    text = f"https://example.invalid{HOME}/alice/{revision}/"
    hits = scan.scan_bytes("docs/reference.md", text.encode(), scan.load_config())
    assert [hit.pattern for hit in hits] == ["internal-rev"]


def test_web_path_distinction_in_encoded_archive_and_history_label() -> None:
    local = f"{HOME}/alice/boards"
    text = f"https://example.invalid{local} see {local}"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("reference.txt", text.encode("utf-16le"))
    hits = scan.scan_bytes("abcdef012345:fixture.zip", buffer.getvalue(), scan.load_config())
    assert [(hit.path, hit.offset, hit.pattern) for hit in hits] == [
        (
            "abcdef012345:fixture.zip!reference.txt",
            len(text[: text.rindex(local)].encode("utf-16le")),
            "abs-user-path",
        )
    ]


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


GATE_VARIABLES = ("FENOLITE_RESIDUE_TOKENS", "FENOLITE_RESIDUE_TOKENS_FILE", "FENOLITE_RESIDUE_BLOBS_FILE")
GATE_SKIPPED = "private gate: skipped (no private list configured)"


def test_gate_is_skipped_without_a_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run(capsys, _tree(tmp_path / "t", {"a.txt": b"clean\n"}))
    assert code == 0 and out.rstrip().endswith(GATE_SKIPPED)


def test_gate_documented() -> None:
    """docs/provenance.md explains the private gate with the variables the scan reads (capability
    residue-scan, "Private gate is documented")."""
    root = Path(__file__).resolve().parents[2]
    page = (root / "docs" / "provenance.md").read_text(encoding="utf-8")
    source = (root / "tools" / "residue" / "scan.py").read_text(encoding="utf-8")
    heading = "\n## Private residue gate\n"
    assert heading in page
    section = page.split(heading)[1].split("\n## ")[0]
    for variable in GATE_VARIABLES:
        assert f'"{variable}"' in source, variable
        assert f"`{variable}`" in section, variable
    for words in ("private gate: on", GATE_SKIPPED, "--history", "docs/evidence/residue-history.md"):
        assert words in section, words
    assert GATE_SKIPPED.removeprefix("private gate: ") in source
