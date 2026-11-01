# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0266 seed scenarios: authored subset only, no third-party fixture or oracle claims."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run

import fenolite.library.audit as audit_module
import fenolite.library.seed as seed_module
from fenolite.backends.librepcb.reader import CC0_SHA256 as PRODUCTION_CC0_SHA256
from fenolite.catalog.records import DeviceRecord, Origin, Review, parse_record, record_digest, record_text
from fenolite.library.audit import audit
from fenolite.library.licences import normalised_digest, shipped

DEMO = Path(__file__).resolve().parents[3] / "tests/data/librepcb/demo"
COMMIT = "1" * 40
STAMP = ("--timestamp", "2026-11-01T00:00:00Z")


@pytest.fixture(autouse=True)
def authored_licence_hash(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use original fixture text for positive unit paths; production keeps the public S-1097 pin."""
    if getattr(request, "param", "authored") == "production":
        return
    digest = normalised_digest((DEMO / "LICENSE.txt").read_bytes())
    assert digest != PRODUCTION_CC0_SHA256
    monkeypatch.setattr(seed_module, "CC0_SHA256", digest)
    licences = shipped()
    # The positive output audit is a unit test too, never a licence approval for upstream material.
    monkeypatch.setattr(
        audit_module,
        "for_root",
        lambda root: replace(licences, texts={**licences.texts, "CC0-1.0": (digest,)}),
    )


def source(tmp_path: Path) -> Path:
    path = tmp_path / "upstream"
    shutil.copytree(DEMO, path)
    return path


def arguments() -> tuple[str, ...]:
    return (
        "library",
        "seed",
        "--from-librepcb",
        "upstream",
        "--commit",
        COMMIT,
        "--library",
        "Authored Demo",
        "--into",
        "output",
        *STAMP,
    )


def test_seed_items_carry_origin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert {r["kind"] for r in env["result"]["items"]} == {"symbol", "footprint", "device"}
    assert not (tmp_path / "output").exists()
    plan = env["result"]["plan_id"]
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm", "--plan", plan)
    assert code == 0, error
    out = tmp_path / "output"
    records = [parse_record(path.read_text()) for path in out.rglob("record.toml")]
    for record in records:
        assert isinstance(record.header.origin, Origin)
        assert record.header.origin.version == COMMIT and record.header.origin.library == "Authored Demo"
        assert record.header.evidence == "UNVERIFIED" and record.header.sources == ("D-0001",)
        assert record.header.licence == "CC0-1.0" and record.header.version == "1.0.0"
    device = next(r for r in records if isinstance(r, DeviceRecord))
    assert device.parts[0].mpn == "DEMO-266" and device.parts[0].manufacturer == "Example Assemblies"
    assert device.device.pad_map == (("1", "1"), ("2", "2"))
    provenance = [json.loads(path.read_text()) for path in out.rglob("PROVENANCE.json")]
    assert all(p["origin"] == "seeded" and p["upstream"]["commit"] == COMMIT for p in provenance)
    assert all(
        (path.parent / "LICENSE").read_bytes() == (DEMO / "LICENSE.txt").read_bytes()
        for path in out.rglob("item.json")
    )
    assert not audit(out, item="devices/cc0/FenoliteDevices/Demo_Part").issues


@pytest.mark.parametrize("licence", ["CC0-1.0\n", "All rights reserved\n", ""])
def test_not_full_cc0_legal_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, licence: str) -> None:
    root = source(tmp_path)
    (root / "LICENSE.txt").write_text(licence)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 3 and error["code"] == "FEN-3004" and "not a CC0-1.0 library" in error["message"]
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("authored_licence_hash", ["production"], indirect=True)
def test_authored_placeholder_rejected_under_production_defaults(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source(tmp_path)
    assert seed_module.CC0_SHA256 == PRODUCTION_CC0_SHA256
    assert PRODUCTION_CC0_SHA256 in shipped().texts["CC0-1.0"]
    fixture_hash = normalised_digest((DEMO / "LICENSE.txt").read_bytes())
    assert fixture_hash != PRODUCTION_CC0_SHA256
    assert fixture_hash not in shipped().texts["CC0-1.0"]
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 3 and error["code"] == "FEN-3004" and "not a CC0-1.0 library" in error["message"]
    assert not (tmp_path / "output").exists()


def test_commit_mismatch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = source(tmp_path)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture Author",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "Authored fixture",
        ],
        check=True,
    )
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 3 and error["code"] == "FEN-3004" and "HEAD" in error["message"]
    assert not (tmp_path / "output").exists()


def test_seed_same_bytes_twice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 0, error
    before = {
        p.relative_to(tmp_path / "output"): p.read_bytes()
        for p in (tmp_path / "output").rglob("*")
        if p.is_file()
    }
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert env["result"]["unchanged"] and not env["result"].get("plan", [])
    assert before == {
        p.relative_to(tmp_path / "output"): p.read_bytes()
        for p in (tmp_path / "output").rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize("name", ["..", "Demo..Land"])
def test_seed_names_cannot_be_path_segments(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    root = source(tmp_path)
    path = next((root / "pkg").rglob("package.lp"))
    path.write_text(path.read_text().replace('(name "Demo Land")', f'(name "{name}")'))
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert all(".." not in r["id"] for r in env["result"]["items"])
    assert all(Path(w["path"]).is_relative_to("output") for w in env["result"]["plan"])


def test_seed_colliding_names_get_stable_uuid_suffix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = source(tmp_path)
    original = next((root / "pkg").iterdir())
    second = original.with_name(original.name.replace("26600000", "69990000"))
    shutil.copytree(original, second)
    path = second / "package.lp"
    path.write_text(path.read_text().replace("26600000", "69990000"))
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 0, error
    ids = [r["id"] for r in env["result"]["items"]]
    assert "FenoliteDevices:Demo_Land_69990000" in ids
    assert "library.seed-renamed" in {i["code"] for i in env["issues"]}
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0 and env["result"]["unchanged"], error
    assert [r["id"] for r in env["result"]["items"]] == ids


def test_seed_unknown_version_skips_dependants(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = source(tmp_path)
    next((root / "pkg").rglob(".librepcb-pkg")).write_text("999\n")
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert [r["kind"] for r in env["result"]["items"]] == ["symbol"]
    assert len([i for i in env["issues"] if i["code"] == "library.seed-skipped"]) == 2


def test_seed_multiple_footprints_and_default_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = source(tmp_path)
    path = next((root / "pkg").rglob("package.lp"))
    text = path.read_text()
    start, end = text.index(" (footprint "), text.rindex("\n)")
    extra = text[start:end].replace('(name "Default")', '(name "Hand")')
    for suffix in ("23", "24", "25", "26"):
        extra = extra.replace(
            f"26600000-0000-4000-8000-0000000000{suffix}", f"69990000-0000-4000-8000-0000000000{suffix}"
        )
    path.write_text(text[:end] + extra + text[end:])
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 0, error
    assert {r["id"] for r in env["result"]["items"] if r["kind"] == "footprint"} == {
        "FenoliteDevices:Demo_Land",
        "FenoliteDevices:Demo_Land_Hand",
    }
    marker = next((tmp_path / "output/devices").rglob("item.json"))
    assert {d["id"] for d in json.loads(marker.read_text())["depends"]} == {
        "FenoliteDevices:Demo_Land",
        "FenoliteDevices:Demo_Passive",
    }


def test_seed_gate_units_and_unknown_roles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = source(tmp_path)
    path = next((root / "cmp").rglob("component.lp"))
    extra = """
 (gate 69990000-0000-4000-8000-000000000034 (name "B") (symbol 26600000-0000-4000-8000-000000000001)
  (pin 26600000-0000-4000-8000-000000000011 (signal 26600000-0000-4000-8000-000000000031))
  (pin 26600000-0000-4000-8000-000000000012 (signal 26600000-0000-4000-8000-000000000032)))
"""
    text = path.read_text().replace("(role passive)", "(role unknown_role)")
    assert text.count("\n )\n)\n") == 1
    path.write_text(text.replace("\n )\n)\n", extra + "\n )\n)\n"))
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 0, error
    symbol = parse_record(next((tmp_path / "output/symbols").rglob("record.toml")).read_text())
    assert {pin.unit for pin in symbol.pins} == {1, 2}
    assert all(pin.type == "unspecified" for pin in symbol.pins)
    # This fixture repeats signals in both gates. The record model cannot assign one physical pad
    # to two distinct symbol numbers, so the dependent device is explicitly skipped.
    assert not (tmp_path / "output/devices").exists()
    assert any(i["code"] == "library.seed-skipped" and "pad" in i["message"] for i in env["issues"])


@pytest.mark.parametrize(
    "old,new", [("(shape rect)", "(shape custom)"), ("(size 1 1.4)", "(size 0.0000001 1.4)")]
)
def test_unsupported_package_and_dependants_skipped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, old: str, new: str
) -> None:
    root = source(tmp_path)
    path = next((root / "pkg").rglob("package.lp"))
    path.write_text(path.read_text().replace(old, new))
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert [r["kind"] for r in env["result"]["items"]] == ["symbol"]
    assert len([i for i in env["issues"] if i["code"] == "library.seed-skipped"]) == 2


def test_reviewed_record_kept_even_allow_lossy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm")
    assert code == 0, error
    path = next((tmp_path / "output/devices").rglob("record.toml"))
    record = parse_record(path.read_text())
    review = Review("Fixture Reviewer", "2026-11-01", "1.0.0", record_digest(record), "INFERRED")
    record = replace(record, header=replace(record.header, reviewed_by=(review,)))
    path.write_text(record_text(record))
    before = path.read_bytes()
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--allow-lossy", "--confirm")
    assert code == 7 and error["code"] == "FEN-7001"
    assert path.read_bytes() == before


def test_seed_plan_binds_source_bytes_and_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = source(tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    plan = env["result"]["plan_id"]
    path = next((root / "dev").rglob("device.lp"))
    path.write_text(path.read_text().replace("Demo Part", "Other Part"))
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--confirm", "--plan", plan)
    assert code == 4 and error["code"] == "FEN-4002"
    assert not (tmp_path / "output").exists()


def test_seed_action_and_board_path_form(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, error, _ = run(monkeypatch, tmp_path, "capabilities")
    assert code == 0 and any(row["name"] == "library seed" for row in env["result"]["commands"])
    assert "seed" in next(row for row in env["result"]["commands"] if row["name"] == "library")["actions"]
    code, env, error, _ = run(monkeypatch, tmp_path, "library", "seed", "--dry-run")
    assert code == 2 and "--from-librepcb" in error["message"]
    code, env, error, _ = run(monkeypatch, tmp_path, "library", "./seed", "--out", "x.pretty", "--dry-run")
    assert code == 3 and "requires --from-librepcb" not in error["message"]
