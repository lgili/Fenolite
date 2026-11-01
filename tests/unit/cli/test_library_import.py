# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Import mutation, target and re-import contracts, on authored data only (c0264)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
from _checkcli import run
from _library_import import DATA

from fenolite.catalog.records import DeviceRecord, ImportOrigin, parse_record

STAMP = ("--timestamp", "2026-10-29T00:00:00Z")
IMPORT = ("library", "import", str(DATA / "exb6202.zip"), "--into", "devices", *STAMP)
FOLDER = "devices/Imported/EXB6202"


def test_import_plans_then_confirms_exact_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, reply, error, _ = run(monkeypatch, tmp_path, *IMPORT, "--dry-run")
    assert code == 0, error
    result = reply["result"]
    assert result["schema"] == "fenolite.library-import.v0"
    assert set(result) >= {
        "device",
        "folder",
        "sources",
        "skipped",
        "symbol",
        "footprint",
        "step",
        "family",
        "crosscheck",
        "unchanged",
    }
    assert reply["evidence"]["level"] == "INFERRED" and result["evidence"] == "UNVERIFIED"
    assert len(result["plan"]) == 6 and all(p["path"].startswith(FOLDER + "/") for p in result["plan"])
    assert not (tmp_path / "devices").exists()
    import fenolite.cli._library_import as importer

    monkeypatch.setattr(
        importer, "make_records", lambda *a, **kw: pytest.fail("confirmation must replay the staged bytes")
    )
    code, confirmed, error, _ = run(monkeypatch, tmp_path, *IMPORT, "--confirm", "--plan", result["plan_id"])
    assert code == 0, error
    for row in confirmed["receipt"]["written"]:
        assert hashlib.sha256((tmp_path / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_plan_is_deterministic_and_binds_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "part.zip"
    shutil.copy(DATA / "exb6202.zip", archive)
    args = ("library", "import", "part.zip", "--into", "devices", *STAMP)
    first = run(monkeypatch, tmp_path, *args, "--dry-run")[1]["result"]
    second = run(monkeypatch, tmp_path, *args, "--dry-run")[1]["result"]
    assert first["plan_id"] == second["plan_id"] and first["plan"] == second["plan"]
    archive.write_bytes(archive.read_bytes() + b"authored changed archive")
    code, _, error, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", first["plan_id"])
    assert code == 4 and error["code"] == "FEN-4002" and not (tmp_path / "devices").exists()


@pytest.mark.parametrize("target", ["../outside", "/outside", "fenolite_library/local", "devices/../outside"])
def test_invalid_target_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    args = list(IMPORT)
    args[args.index("devices")] = target
    code, _, error, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001"


def test_shipped_package_cache_and_symlink_targets_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fenolite

    package = Path(fenolite.__file__).resolve().parent
    (tmp_path / "installed").symlink_to(package, target_is_directory=True)
    cache = tmp_path / "cache"
    monkeypatch.setenv("FENOLITE_LIBRARY_DIR", str(cache))
    for into in ("installed/catalog", "cache/devices"):
        code, _, error, _ = run(
            monkeypatch, tmp_path, "library", "import", str(DATA / "exb6202.zip"), "--into", into
        )
        assert code == 2 and error["code"] == "FEN-2001"
    shipped = tmp_path / "shipped/Example/X"
    shipped.mkdir(parents=True)
    (shipped / "device.toml").write_text('licence = "CC0-1.0"\n')
    assert (
        run(monkeypatch, tmp_path, "library", "import", str(DATA / "exb6202.zip"), "--into", "shipped")[0]
        == 2
    )


def test_unchanged_and_replacement_and_hand_edits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    code, reply, error, _ = run(monkeypatch, tmp_path, *IMPORT, "--dry-run")
    assert code == 0, error
    assert reply["result"]["unchanged"] and "plan" not in reply["result"]
    assert run(monkeypatch, tmp_path, *IMPORT, "--manufacturer", "Example", "--confirm")[0] == 0
    path = tmp_path / FOLDER / "device.toml"
    path.write_text(path.read_text().replace("imported from", "reviewed from"))
    code, _, error, _ = run(monkeypatch, tmp_path, *IMPORT, "--dry-run")
    assert code == 7 and error["code"] == "FEN-7001"
    assert run(monkeypatch, tmp_path, *IMPORT, "--allow-lossy", "--confirm")[0] == 0
    record = parse_record(path.read_text())
    assert isinstance(record, DeviceRecord) and isinstance(record.header.origin, ImportOrigin)
    assert record.header.evidence == "UNVERIFIED"
    native = tmp_path / FOLDER / "EXB6202.kicad_mod"
    native.write_bytes(native.read_bytes() + b"\n")
    assert run(monkeypatch, tmp_path, *IMPORT, "--dry-run")[0] == 7


def test_shrinking_output_is_refused_even_with_loss_consent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    args = (
        "library",
        "import",
        str(DATA / "exb6202.kicad_sym"),
        str(DATA / "exb6202.kicad_mod"),
        "--into",
        "devices",
        *STAMP,
    )
    code, _, error, _ = run(monkeypatch, tmp_path, *args, "--allow-lossy", "--dry-run")
    assert code == 7 and error["code"] == "FEN-7001" and "another --id" in error["hint"]


def test_lib_id_form_and_crosscheck_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = (
        "library",
        "import",
        "--symbol",
        "Fenolite:Resistor",
        "--footprint",
        "Fenolite:Chip_0603",
        "--into",
        "devices",
        "--id",
        "Proj:R",
        *STAMP,
    )
    code, reply, error, _ = run(monkeypatch, tmp_path, *args, "--no-crosscheck", "--dry-run")
    assert code == 0, error
    assert "library.import-crosscheck-skipped" in {i["code"] for i in reply["issues"]}
    assert reply["result"]["device"] == "Proj:R"
    code, reply, error, _ = run(
        monkeypatch, tmp_path, *IMPORT, "--package", str(DATA / "exb6202.toml"), "--dry-run"
    )
    assert code == 0 and not [i for i in reply["issues"] if i["severity"] in ("warning", "error")], error


def test_confirmed_import_builds_with_native_files_and_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    (tmp_path / "design.py").write_text(
        "from fenolite.dsl import Design, mm\n"
        'design = Design("local_import")\n'
        "design.board(mm(20), mm(15))\n"
        'design.part("U1", device="Imported:EXB6202").place(mm(10), mm(7))\n'
    )
    code, reply, error, _ = run(monkeypatch, tmp_path, "build", "design.py", "--out", "build", "--confirm")
    assert code == 0, error
    assert reply["result"]["devices"][0]["evidence"] == "UNVERIFIED"
    path = tmp_path / "build/lib/Imported.3dshapes/EXB6202.step"
    assert path.read_bytes() == (DATA / "exb6202.step").read_bytes()
    assert (
        "${KIPRJMOD}/lib/Imported.3dshapes/EXB6202.step"
        in (tmp_path / "build/lib/Imported.pretty/EXB6202.kicad_mod").read_text()
    )


def test_imported_record_kinds_share_id_and_keep_normalized_bodies(tmp_path, monkeypatch):
    from dataclasses import replace

    from fenolite.catalog.records import BodyEntry, PackageRecord, record_text
    from fenolite.cli._library_check import _read
    from fenolite.core.coords import Point

    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    folder = tmp_path / FOLDER
    package_path = folder / "package.toml"
    package = parse_record(package_path.read_text())
    assert isinstance(package, PackageRecord)
    body = BodyEntry(
        "extruded",
        1_000_000,
        outline=(
            Point(-200_000, -200_000),
            Point(200_000, -200_000),
            Point(200_000, 200_000),
            Point(-200_000, 200_000),
        ),
        name="authored-body",
    )
    package = replace(package, family="gullwing", bodies=(body,))
    package_path.write_text(record_text(package))
    loaded = _read(package_path, tmp_path)[0]
    assert loaded.footprint is not None and loaded.footprint.bodies[0].name == "authored-body"
    _, reply, error, _ = run(monkeypatch, tmp_path, "library", "check", FOLDER, "--compare", FOLDER)
    assert error.get("code") != "FEN-1001", error
    assert len(reply["result"]["items"]) == 3
    assert len(reply["result"]["compare"]) == 3
    assert all(p["change"] == "same" for p in reply["result"]["compare"])
    assert not [f for f in reply["issues"] if f["code"] == "library.record-invalid"]


def test_error_findings_plan_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, reply, error, _ = run(
        monkeypatch, tmp_path, *IMPORT, "--package", str(DATA.parent / "packages/chip0603.toml"), "--confirm"
    )
    assert code == 5 and error["code"] == "FEN-5001"
    assert "plan" not in reply["result"] and not (tmp_path / "devices").exists()


def test_import_flags_are_rejected_by_the_board_form(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run(monkeypatch, tmp_path, "library", "board.kicad_pcb", "--into", "devices")[0] == 2


def test_import_starts_no_network_or_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import socket
    import subprocess

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("local import attempted external I/O")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    assert run(monkeypatch, tmp_path, *IMPORT, "--dry-run")[0] == 0


def test_namespace_symlink_cannot_route_output_into_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "devices"
    cache = root / "cache"
    cache.mkdir(parents=True)
    (root / "Imported").symlink_to(cache, target_is_directory=True)
    monkeypatch.setenv("FENOLITE_LIBRARY_DIR", str(cache))
    code, _, error, _ = run(monkeypatch, tmp_path, *IMPORT, "--dry-run")
    assert code == 2 and error["code"] == "FEN-2001"
    assert not (cache / "EXB6202").exists()
