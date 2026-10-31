# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite get`` and the design lock: the section ``library``, the build check, updates, removals,
``--locked`` and ``--status`` (capability design-dsl, "Library section of the design lock", "Missing vendored
item"; capability cli-contract, "Get updates and removals", "Get restore and status"; change c0279)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _checkcli import run
from _libdemo import DEMO, ROOT, demo_copy, edit_json, files_of, no_network, write_release

from fenolite.dsl.lock import read_lock

EXAMPLE = ROOT / "examples" / "lock"
DEVICE = "fenolite_library/devices/Demo/EXB"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    no_network(monkeypatch)


@pytest.fixture
def release(tmp_path: Path) -> Path:
    folder = tmp_path / "release"
    write_release(DEMO, folder)
    return folder


def _project(tmp_path: Path, *, lock: bool = True) -> Path:
    folder = tmp_path / "ex"
    folder.mkdir()
    shutil.copy(EXAMPLE / "design.py", folder / "design.py")
    if lock:
        shutil.copy(EXAMPLE / "design.lock", folder / "design.lock")
    return folder


def _got(monkeypatch: pytest.MonkeyPatch, work: Path, release: Path, *extra: str) -> dict[str, object]:
    code, envelope, error, _ = run(
        monkeypatch, work, "get", "device", "Demo:EXB", "--from", str(release), *extra, "--confirm"
    )
    assert code == 0, (envelope, error)
    return envelope


def test_pin_written_by_get(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    """Scenario "Pin written by get": a project with design.py and no lock."""
    work = _project(tmp_path, lock=False)
    envelope = _got(monkeypatch, work, release)
    lock = read_lock((work / "design.lock").read_text(encoding="utf-8"), file="design.lock")
    entry = lock.sections["library"]["device/Demo:EXB"]
    index = json.loads((release / "index.json").read_text(encoding="utf-8"))
    row = next(r for r in index["items"] if r["kind"] == "device")
    assert dict(entry) == {
        "index": f"sha256:{envelope['result']['index_sha256']}",  # type: ignore[index]
        "path": DEVICE,
        "release": "1.0.0",
        "spdx": "CC0-1.0",
        "tree": row["tree"],
        "version": "1.2.0",
    }
    assert set(lock.sections["library"]) == {"device/Demo:EXB", "symbol/Demo:EXB", "footprint/Demo:SOT"}
    assert lock.design == "lock_demo"  # read from the script without running it


def test_build_leaves_the_section_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path
) -> None:
    """Scenario "Build leaves the section alone"."""
    work = _project(tmp_path)
    _got(monkeypatch, work, release)
    before = (work / "design.lock").read_bytes()
    code, envelope, error, _ = run(
        monkeypatch, tmp_path, "build", "ex/design.py", "--out", "B", "--frozen", "--dry-run"
    )
    assert code == 0, (envelope, error)
    assert not [i for i in envelope["issues"] if i["code"] == "lock.changed"]
    assert (work / "design.lock").read_bytes() == before


def test_fresh_clone_without_library_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path
) -> None:
    """Scenario "Fresh clone without library folder"."""
    work = _project(tmp_path)
    _got(monkeypatch, work, release)
    shutil.rmtree(work / "fenolite_library")
    before = files_of(tmp_path)
    code, envelope, error, _ = run(monkeypatch, work, "build", "design.py", "--out", "B", "--confirm")
    assert code == 6 and error["code"] == "FEN-6004" and error["retryable"] is False
    assert error["hint"] == "fenolite get --locked design.py --dry-run"
    assert {i["code"] for i in envelope["issues"]} == {"library.item-missing"}
    assert files_of(tmp_path) == before


def test_local_edit_protected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    """Scenario "Local edit protected", then the update with --allow-lossy, which reports before and after."""

    def newer(root: Path) -> None:
        for name in ("item.json", "PROVENANCE.json"):
            edit_json(root / "devices/cc0/Demo/EXB" / name, version="1.3.0")
        (root / "devices/cc0/Demo/EXB/EXB.toml").write_text("# version 1.3.0\n", encoding="utf-8")

    second = tmp_path / "release2"
    write_release(demo_copy(tmp_path / "lib2", newer), second, "1.1.0")
    work = _project(tmp_path)
    _got(monkeypatch, work, release)
    (work / DEVICE / "EXB.toml").write_text("# edited by hand\n", encoding="utf-8")
    before = files_of(work)
    code, envelope, error, _ = run(
        monkeypatch,
        work,
        "get",
        "device",
        "Demo:EXB",
        "--version",
        "1.3.0",
        "--from",
        str(second),
        "--confirm",
    )
    assert code == 7 and error["code"] == "FEN-7001"
    assert [i["code"] for i in envelope["issues"]] == ["library.item-modified"]
    assert files_of(work) == before
    code, envelope, _, _ = run(
        monkeypatch,
        work,
        "get",
        "device",
        "Demo:EXB",
        "--version",
        "1.3.0",
        "--from",
        str(second),
        "--allow-lossy",
        "--confirm",
    )
    assert code == 0, envelope
    row = next(r for r in envelope["result"]["items"] if r["kind"] == "device")
    assert (row["action"], row["before"], row["after"]) == ("updated", "1.2.0", "1.3.0")
    assert (work / DEVICE / "EXB.toml").read_text(encoding="utf-8") == "# version 1.3.0\n"
    lock = read_lock((work / "design.lock").read_text(encoding="utf-8"), file="design.lock")
    assert lock.sections["library"]["device/Demo:EXB"]["release"] == "1.1.0"


def test_restore_after_a_fresh_clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    """Scenario "Restore after a fresh clone": the release is cached by the first get."""
    work = _project(tmp_path)
    _got(monkeypatch, work, release)
    vendored = files_of(work / "fenolite_library")
    lock = (work / "design.lock").read_bytes()
    shutil.rmtree(work / "fenolite_library")
    code, envelope, error, _ = run(
        monkeypatch, work, "get", "--locked", "design.py", "--offline", "--confirm"
    )
    assert code == 0, (envelope, error)
    assert files_of(work / "fenolite_library") == vendored
    assert (work / "design.lock").read_bytes() == lock
    code, envelope, _, _ = run(monkeypatch, work, "get", "--locked", "design.py", "--offline", "--dry-run")
    assert code == 0 and "plan" not in envelope["result"]


def test_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    work = _project(tmp_path)
    _got(monkeypatch, work, release)
    (work / DEVICE / "EXB.toml").write_text("# edited\n", encoding="utf-8")
    shutil.rmtree(work / "fenolite_library/symbols")
    code, envelope, error, _ = run(monkeypatch, work, "get", "--status")
    assert code == 5 and error["code"] == "FEN-5001"
    rows = {r["kind"]: r for r in envelope["result"]["rows"]}
    assert rows["device"]["present"] and rows["device"]["modified"] and rows["device"]["newer"] is None
    assert not rows["symbol"]["present"] and not rows["footprint"]["modified"]
    assert [i["code"] for i in envelope["issues"]] == ["library.item-missing"]


def test_remove(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, release: Path) -> None:
    work = _project(tmp_path)
    _got(monkeypatch, work, release)
    code, _, error, _ = run(monkeypatch, work, "get", "--remove", "symbol", "Demo:EXB", "--dry-run")
    assert code == 2 and "device/Demo:EXB" in error["message"]
    code, envelope, _, _ = run(monkeypatch, work, "get", "--remove", "device", "Demo:EXB", "--dry-run")
    assert code == 0 and f"{DEVICE}/EXB.toml" in envelope["result"]["removes"]
    plan_id = envelope["result"]["plan_id"]
    code, envelope, _, _ = run(
        monkeypatch, work, "get", "--remove", "device", "Demo:EXB", "--confirm", "--plan", plan_id
    )
    assert code == 0, envelope
    assert not (work / DEVICE).exists() and (work / "fenolite_library/symbols/Demo/EXB").is_dir()
    lock = read_lock((work / "design.lock").read_text(encoding="utf-8"), file="design.lock")
    assert "device/Demo:EXB" not in lock.sections["library"]
    assert "device `Demo:EXB`" not in (work / "fenolite_library/ATTRIBUTION.md").read_text(encoding="utf-8")


def test_codes_explained() -> None:
    """Scenario "Codes explained"."""
    from fenolite.cli.errors import REGISTRY
    from fenolite.cli.exitcodes import ExitCode
    from fenolite.cli.explain import explain

    wanted = {
        "FEN-6004": ExitCode.TOOL,
        "FEN-6006": ExitCode.TOOL,
        "FEN-4003": ExitCode.CONFIRM_REQUIRED,
        "FEN-3021": ExitCode.INPUT,
    }
    for code, exit_code in wanted.items():
        assert REGISTRY[code].exit_code is exit_code and not REGISTRY[code].retryable, code
        found = explain(code)
        assert found is not None and found.see == "get", code
    found = explain("FEN-6004")
    assert found is not None and "fenolite get --locked" in found.fix
    assert "fenolite get --locked" in REGISTRY["FEN-6004"].hint
    contract = (ROOT / "docs" / "cli-contract.md").read_text(encoding="utf-8")
    assert all(f"| `{code}` |" in contract for code in wanted)
