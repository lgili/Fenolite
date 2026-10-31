# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite get``: plan, closure, copy targets, ``ATTRIBUTION.md``, ``--from``, the client licence check and
licence acceptance (capability cli-contract, "Get command", "Licence shown and accepted", "Client licence
check", "Get closure conflicts"; change c0279). Hermetic: no test opens a network connection."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from _checkcli import run
from _libdemo import DEMO, cache_files, demo_copy, edit_json, files_of, no_network, project, write_release

DEVICE = "fenolite_library/devices/Demo/EXB"
SYMBOL = "fenolite_library/symbols/Demo/EXB"
FOOTPRINT = "fenolite_library/footprints/Demo/SOT"


@pytest.fixture
def release(tmp_path: Path) -> Path:
    folder = tmp_path / "release"
    write_release(DEMO, folder)
    return folder


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    return no_network(monkeypatch)


def test_plan_a_device_with_its_closure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path
) -> None:
    """Scenario "Plan a device with its closure"."""
    work = project(tmp_path / "work")
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--dry-run"
    )
    assert code == 0, envelope
    paths = [row["path"] for row in envelope["result"]["plan"]]
    for folder in (DEVICE, SYMBOL, FOOTPRINT):
        assert {f"{folder}/{name}" for name in ("LICENSE", "NOTICE", "PROVENANCE.json", "item.json")} <= set(
            paths
        )
    assert "fenolite_library/ATTRIBUTION.md" in paths and "design.lock" in paths
    assert files_of(work) == {"design.py": (work / "design.py").read_bytes()}
    items = {row["id"] + "@" + row["kind"]: row for row in envelope["result"]["items"]}
    assert items["Demo:EXB@symbol"]["required_by"] == ["device/Demo:EXB"]
    device = items["Demo:EXB@device"]
    assert device["spdx"] == "CC0-1.0" and device["family"] == "cc0" and device["reciprocal"] is False
    assert (
        device["obligations"]
        and device["authors"] == ["Fenolite contributors"]
        and device["executes"] is False
    )
    assert envelope["result"]["licences"] == [{"spdx": "CC0-1.0", "accept_required": False, "accepted": True}]


def test_confirmed_copy_keeps_the_licence_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path
) -> None:
    """Scenario "Confirmed copy keeps the licence files"."""
    work = project(tmp_path / "work")
    _, planned, _, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--dry-run"
    )
    plan_id = planned["result"]["plan_id"]
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--confirm", "--plan", plan_id
    )
    assert code == 0, envelope
    for folder, source in (
        (DEVICE, "devices/cc0/Demo/EXB"),
        (SYMBOL, "symbols/cc0/Demo/EXB"),
        (FOOTPRINT, "footprints/cc0/Demo/SOT"),
    ):
        assert files_of(work / folder) == files_of(DEMO / source)
    receipt = {row["path"]: row["sha256"] for row in envelope["receipt"]["written"]}
    for path, digest in receipt.items():
        assert hashlib.sha256((work / path).read_bytes()).hexdigest() == digest
    assert f"{DEVICE}/LICENSE" in receipt and "design.lock" in receipt
    attribution = (work / "fenolite_library/ATTRIBUTION.md").read_text(encoding="utf-8")
    assert (
        attribution.index("symbol `Demo:EXB`")
        < attribution.index("footprint `Demo:SOT`")
        < attribution.index("device `Demo:EXB`")
    )
    assert "authored for the Fenolite tests" in attribution


def test_cache_keeps_the_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    work = project(tmp_path / "work")
    code, _, _, _ = run(monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--confirm")
    assert code == 0
    cached = cache_files()
    assert cached["1.0.0/index.json"] == (release / "index.json").read_bytes()
    for name in ("devices-cc0.tar.gz", "symbols-cc0.tar.gz", "footprints-cc0.tar.gz"):
        assert cached[f"1.0.0/assets/{name}"] == (release / name).read_bytes()
    assert "1.0.0/.fenolite-library.toml" in cached


def test_share_alike_item_needs_acceptance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path
) -> None:
    """Scenarios "Share-alike item needs acceptance" and "Accepted by name"."""
    work = project(tmp_path / "work")
    before = files_of(work)
    code, envelope, error, _ = run(
        monkeypatch, work, "get", "footprint", "Demo:SA_PAD", "--from", str(release), "--confirm"
    )
    assert code == 4 and error["code"] == "FEN-4003" and "CC-BY-SA-4.0" in error["message"]
    assert files_of(work) == before and cache_files() == {}
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "footprint", "Demo:SA_PAD", "--from", str(release), "--dry-run"
    )
    assert code == 0 and envelope["result"]["licences"] == [
        {"spdx": "CC-BY-SA-4.0", "accept_required": True, "accepted": False}
    ]
    plan_id = envelope["result"]["plan_id"]
    code, envelope, error, _ = run(
        monkeypatch,
        work,
        "get",
        "footprint",
        "Demo:SA_PAD",
        "--from",
        str(release),
        "--confirm",
        "--plan",
        plan_id,
    )
    assert code == 4 and error["code"] == "FEN-4003"
    code, envelope, _, _ = run(
        monkeypatch,
        work,
        "get",
        "footprint",
        "Demo:SA_PAD",
        "--from",
        str(release),
        "--accept-licence",
        "CC-BY-SA-4.0",
        "--confirm",
    )
    assert code == 0, envelope
    assert envelope["result"]["accepted"] == ["CC-BY-SA-4.0"]
    item = envelope["result"]["items"][0]
    assert item["reciprocal"] is True and "same licence" in item["obligations"]
    assert (work / "fenolite_library/footprints/Demo/SA_PAD/LICENSE").is_file()


def test_release_with_a_denied_item(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    """Scenario "Release with a denied item"."""
    index = json.loads((release / "index.json").read_text(encoding="utf-8"))
    row = next(r for r in index["items"] if r["kind"] == "device")
    row.update(id="Demo:NC", spdx="CC-BY-NC-4.0")
    (release / "index.json").write_text(json.dumps(index), encoding="utf-8")
    work = project(tmp_path / "work")
    code, envelope, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:NC", "--from", str(release), "--dry-run"
    )
    assert code == 3 and error["code"] == "FEN-3021"
    assert "Demo:NC" in error["message"] and "CC-BY-NC-4.0" in error["message"]
    assert envelope["issues"][0]["code"] == "library.licence-denied"


def test_provenance_and_index_disagree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path
) -> None:
    index = json.loads((release / "index.json").read_text(encoding="utf-8"))
    for row in index["items"]:
        if row["kind"] == "device":
            row["spdx"] = "MIT"
    (release / "index.json").write_text(json.dumps(index), encoding="utf-8")
    work = project(tmp_path / "work")
    code, _, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--dry-run"
    )
    assert code == 3 and error["code"] == "FEN-3021" and "PROVENANCE.json" in error["message"]


def test_conflicting_dependency(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    """Scenario "Conflicting dependency"."""

    def newer(root: Path) -> None:
        for name in ("item.json", "PROVENANCE.json"):
            edit_json(root / "footprints/cc0/Demo/SOT" / name, version="1.1.0")
        edit_json(
            root / "devices/cc0/Demo/EXB/item.json",
            depends=[
                {"kind": "symbol", "id": "Demo:EXB", "version": "1.0.0"},
                {"kind": "footprint", "id": "Demo:SOT", "version": "1.1.0"},
            ],
        )

    second = tmp_path / "release2"
    write_release(demo_copy(tmp_path / "lib2", newer), second, "1.1.0")
    work = project(tmp_path / "work")
    code, _, _, _ = run(
        monkeypatch, work, "get", "footprint", "Demo:SOT", "--from", str(release), "--confirm"
    )
    assert code == 0
    before = files_of(work)
    code, envelope, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(second), "--dry-run"
    )
    assert code == 5 and error["code"] == "FEN-5001"
    found = [i for i in envelope["issues"] if i["code"] == "library.depends-conflict"]
    assert found and "1.0.0" in found[0]["message"] and "1.1.0" in found[0]["message"]
    assert "plan" not in envelope["result"] and files_of(work) == before


def test_board_goes_into_its_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    code, envelope, _, _ = run(
        monkeypatch,
        work,
        "get",
        "board",
        "demo-src/blink",
        "--from",
        str(release),
        "--into",
        "blink",
        "--accept-licence",
        "CERN-OHL-S-2.0",
        "--confirm",
    )
    assert code == 0, envelope
    assert files_of(work / "blink").keys() >= {
        "design.py",
        "LICENSE",
        "NOTICE",
        "PROVENANCE.json",
        "item.json",
        "design.lock",
    }
    lock = (work / "blink" / "design.lock").read_text(encoding="utf-8")
    assert '[library.items."board/demo-src/blink"]' in lock and 'path = "."' in lock
    assert envelope["result"]["items"][0]["executes"] is True
    code, _, error, _ = run(
        monkeypatch,
        work,
        "get",
        "board",
        "demo-src/blink",
        "--from",
        str(release),
        "--into",
        "blink",
        "--dry-run",
    )
    assert code == 2 and "--into" in error["message"]


def test_from_a_checkout_and_a_file_git_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """--from a library checkout builds the release in memory; a file:// git URL is cloned first."""
    work = project(tmp_path / "work")
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(DEMO), "--dry-run"
    )
    assert code == 0 and envelope["result"]["origin"] == "tree" and envelope["result"]["downloads"] == []
    repo = demo_copy(tmp_path / "repo")
    git = [
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-C",
        str(repo),
    ]
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "demo"], check=True)
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", f"{repo.as_uri()}#main", "--confirm"
    )
    assert code == 0, envelope
    assert (work / DEVICE / "EXB.toml").read_bytes() == (DEMO / "devices/cc0/Demo/EXB/EXB.toml").read_bytes()
    assert cache_files() == {}
    code, _, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", "https://example.invalid/x.git", "--dry-run"
    )
    assert code == 2 and error["code"] == "FEN-2001"


def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    work = tmp_path / "empty"
    work.mkdir()
    code, _, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), "--dry-run"
    )
    assert code == 2 and "--script" in error["hint"]
    work = project(tmp_path / "work")
    for args in (
        ("device",),
        ("widget", "a:b"),
        ("--list", "device", "Demo:EXB"),
        ("--status", "--list"),
        ("device", "Demo:EXB", "--frozen"),
    ):
        code, _, error, _ = run(monkeypatch, work, "get", *args, "--from", str(release), "--dry-run")
        assert code == 2, args
    code, _, error, _ = run(
        monkeypatch,
        work,
        "get",
        "device",
        "Demo:EXB",
        "--version",
        "9.9.9",
        "--from",
        str(release),
        "--dry-run",
    )
    assert code == 2 and "1.2.0" in error["hint"]
