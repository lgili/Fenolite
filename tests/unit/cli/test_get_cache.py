# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite get``: the offline cache, the trust chain and the network rules (capability cli-contract, "Get
network and cache rules", "Get list and search"; change c0279; ADR-0008). Hermetic: the network is patched
to raise, and the downloads of the confirmed runs are served from a local release folder."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from _checkcli import run
from _libdemo import DEMO, cache_files, files_of, no_network, project, write_release

from fenolite.cli import cmd_get, fetch
from fenolite.cli.cmd_get import KnownRelease, asset_url, known_releases


@pytest.fixture
def release(tmp_path: Path) -> Path:
    folder = tmp_path / "release"
    write_release(DEMO, folder)
    return folder


@pytest.fixture
def tried(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return no_network(monkeypatch)


def _known(monkeypatch: pytest.MonkeyPatch, release: Path) -> str:
    data = (release / "index.json").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    template, _ = cmd_get._table()
    monkeypatch.setattr(cmd_get, "_table", lambda: (template, (KnownRelease("1.0.0", len(data), digest),)))
    return digest


def _serve(monkeypatch: pytest.MonkeyPatch, release: Path) -> list[str]:
    """``download_url`` serves the assets of ``release``; the list holds every requested address."""
    asked: list[str] = []

    def serve(url: str, size: int) -> bytes:
        asked.append(url)
        return (release / url.rsplit("/", 1)[1]).read_bytes()[: size + 1]

    monkeypatch.setattr(fetch, "download_url", serve)
    return asked


def test_table_rows_are_well_formed() -> None:
    """``cli/data/library.toml``: each known release pins an index by size and SHA-256 (none yet: the first
    release of fenolite-library adds its row)."""
    for row in known_releases():
        assert row.index_bytes > 0 and len(row.index_sha256) == 64
    assert (
        asset_url("1.0.0", "index.json")
        == "https://github.com/lgili/fenolite-library/releases/download/v1.0.0/index.json"
    )


def test_dry_run_makes_no_request(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    """Scenario "Dry run makes no request"."""
    digest = _known(monkeypatch, release)
    work = project(tmp_path / "work")
    code, envelope, _, _ = run(
        monkeypatch,
        work,
        "get",
        "device",
        "Demo:EXB",
        "--release",
        "1.0.0",
        "--index-sha256",
        digest,
        "--dry-run",
    )
    assert code == 0, envelope
    assert tried == [] and cache_files() == {}
    plan = envelope["result"]["plan"]
    index = next(row for row in plan if row["path"].endswith("1.0.0/index.json"))
    assert index["kind"] == "library-cache" and index["sha256"] == digest
    assert index["bytes"] == len((release / "index.json").read_bytes())
    assert envelope["result"]["stage"] == "index"


def test_confirm_downloads_each_asset_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    _known(monkeypatch, release)
    asked = _serve(monkeypatch, release)
    work = project(tmp_path / "work")
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--release", "1.0.0", "--confirm"
    )
    assert code == 0, envelope
    assert sorted(a.rsplit("/", 1)[1] for a in asked) == [
        "devices-cc0.tar.gz",
        "footprints-cc0.tar.gz",
        "index.json",
        "symbols-cc0.tar.gz",
    ]
    assert all(
        a.startswith("https://github.com/lgili/fenolite-library/releases/download/v1.0.0/") for a in asked
    )
    assert (work / "fenolite_library/devices/Demo/EXB/EXB.toml").is_file()
    asked.clear()
    second = project(tmp_path / "second")
    code, envelope, _, _ = run(
        monkeypatch, second, "get", "device", "Demo:EXB", "--release", "1.0.0", "--offline", "--confirm"
    )
    assert code == 0 and asked == [] and tried == []
    # a dry run of an asset that is not cached plans its download with its size and digest
    third = project(tmp_path / "third")
    code, envelope, _, _ = run(
        monkeypatch,
        third,
        "get",
        "block",
        "Demo:buck",
        "--release",
        "1.0.0",
        "--accept-licence",
        "Apache-2.0",
        "--dry-run",
    )
    assert code == 0 and asked == []
    shard = next(row for row in envelope["result"]["plan"] if row["path"].endswith("blocks-apache.tar.gz"))
    assert shard["sha256"] == hashlib.sha256((release / "blocks-apache.tar.gz").read_bytes()).hexdigest()
    code, envelope, error, _ = run(
        monkeypatch,
        third,
        "get",
        "block",
        "Demo:buck",
        "--release",
        "1.0.0",
        "--offline",
        "--confirm",
        "--accept-licence",
        "Apache-2.0",
    )
    assert code == 6 and error["code"] == "FEN-6006"


def test_download_failure_is_retryable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    _known(monkeypatch, release)

    def fail(url: str, size: int) -> bytes:
        raise OSError("unreachable")

    monkeypatch.setattr(fetch, "download_url", fail)
    work = project(tmp_path / "work")
    code, _, error, _ = run(monkeypatch, work, "get", "device", "Demo:EXB", "--release", "1.0.0", "--confirm")
    assert code == 6 and error["code"] == "FEN-6003" and error["retryable"] is True
    assert files_of(work).keys() == {"design.py"} and cache_files() == {}


def test_tampered_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    """Scenario "Tampered archive"."""
    shard = release / "devices-cc0.tar.gz"
    expected = hashlib.sha256(shard.read_bytes()).hexdigest()
    shard.write_bytes(shard.read_bytes() + b"\0")
    work = project(tmp_path / "work")
    code, _, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--confirm"
    )
    assert code == 3 and error["code"] == "FEN-3006"
    assert expected in error["message"] and hashlib.sha256(shard.read_bytes()).hexdigest() in error["message"]
    assert cache_files() == {} and files_of(work).keys() == {"design.py"}


def test_index_digest_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    work = project(tmp_path / "work")
    code, _, error, _ = run(
        monkeypatch,
        work,
        "get",
        "device",
        "Demo:EXB",
        "--from",
        str(release),
        "--index-sha256",
        "0" * 64,
        "--dry-run",
    )
    assert code == 3 and error["code"] == "FEN-3006"


def test_search_the_cached_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    """Scenario "Search the cached index"."""
    work = project(tmp_path / "work")
    code, _, _, _ = run(monkeypatch, work, "get", "--refresh", "--from", str(release), "--confirm")
    assert code == 0 and cache_files()["1.0.0/index.json"] == (release / "index.json").read_bytes()
    code, envelope, _, _ = run(monkeypatch, work, "get", "--search", "exb", "--licence", "cc0")
    assert code == 0 and tried == []
    rows = envelope["result"]["rows"]
    assert [(r["kind"], r["id"], r["spdx"]) for r in rows] == [
        ("symbol", "Demo:EXB", "CC0-1.0"),
        ("device", "Demo:EXB", "CC0-1.0"),
    ]
    code, envelope, _, _ = run(monkeypatch, work, "get", "--list", "--kind", "board")
    assert [r["id"] for r in envelope["result"]["rows"]] == ["demo-src/blink"]
    assert envelope["result"]["rows"][0]["authors"] == ["Demo Board Authors"]


def test_nothing_cached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tried: list[str]) -> None:
    """Scenario "Nothing cached"."""
    code, _, error, _ = run(monkeypatch, tmp_path, "get", "--list")
    assert code == 6 and error["code"] == "FEN-6006" and "fenolite get --refresh --dry-run" in error["hint"]
    assert error["retryable"] is False


def test_refresh_caches_one_index(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path, tried: list[str]
) -> None:
    digest = _known(monkeypatch, release)
    code, envelope, _, _ = run(monkeypatch, tmp_path, "get", "--refresh", "--dry-run")
    assert code == 0 and cache_files() == {}
    assert any(row["sha256"] == digest for row in envelope["result"]["plan"])
    asked = _serve(monkeypatch, release)
    code, envelope, _, _ = run(monkeypatch, tmp_path, "get", "--refresh", "--confirm")
    assert code == 0 and len(asked) == 1
    assert cache_files()["1.0.0/index.json"] == (release / "index.json").read_bytes()
