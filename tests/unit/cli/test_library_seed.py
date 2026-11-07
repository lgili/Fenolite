# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0266 seed scenarios: authored subset only, no third-party fixture or oracle claims."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from _checkcli import run

import fenolite.library.audit as audit_module
import fenolite.library.seed as seed_module
from fenolite.backends.librepcb.reader import CC0_SHA256 as PRODUCTION_CC0_SHA256
from fenolite.catalog.records import (
    DeviceRecord,
    Origin,
    PackageRecord,
    PinsRecord,
    Review,
    parse_record,
    record_digest,
    record_text,
)
from fenolite.library.audit import audit
from fenolite.library.licences import normalised_digest, shipped
from fenolite.library.provenance import provenance_problems

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


def legacy_surface_package(root: Path, scalar: str = "0.0") -> Path:
    """Transform only our authored fixture into the separately observed old representation."""
    path = next((root / "pkg").glob("*/package.lp"))
    changed, count = re.subn(
        r"\(pad [0-9a-f-]+ \(package_pad ([0-9a-f-]+)\)",
        lambda match: f"(pad {match[1]} (drill {scalar})",
        path.read_text(),
    )
    assert count == 2
    path.write_text(changed)
    return path


@pytest.mark.parametrize("prefix", ["Z", "invalid prefix"])
def test_declared_prefix_is_preserved_or_explicitly_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, prefix: str
) -> None:
    root = source(tmp_path)
    path = next((root / "cmp").glob("*/component.lp"))
    path.write_text(
        path.read_text().replace('(name "Demo Passive")', f'(name "Demo Passive") (prefix "{prefix}")')
    )
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    if prefix == "invalid prefix":
        assert [r["kind"] for r in env["result"]["items"]] == ["footprint"]
        assert len([r for r in env["issues"] if r["code"] == "library.seed-skipped"]) == 2
        return
    code, env, error, _ = run(
        monkeypatch, tmp_path, *arguments(), "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, error
    records = [parse_record(p.read_text()) for p in (tmp_path / "output").rglob("record.toml")]
    assert next(r for r in records if isinstance(r, DeviceRecord)).device.ref_prefix == prefix
    assert next(r for r in records if isinstance(r, PinsRecord)).symbol.reference == prefix


def test_legacy_zero_drill_and_direct_uuid_keep_exact_surface_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = source(tmp_path)
    legacy_surface_package(root)
    component = next((root / "cmp").glob("*/component.lp"))
    component.write_text(
        component.read_text().replace(
            '(name "Demo Passive")', '(name "Demo Passive") (name (locale "xy_XY") "Localized")'
        )
    )
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert not [row for row in env["issues"] if row["code"] == "library.seed-skipped"]
    code, env, error, _ = run(
        monkeypatch, tmp_path, *arguments(), "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, error
    records = [parse_record(p.read_text()) for p in (tmp_path / "output").rglob("record.toml")]
    package = next(r for r in records if isinstance(r, PackageRecord))
    assert package.kind == "smd"
    assert [(p.number, p.at.x, p.at.y, p.size.w, p.size.h, p.drill) for p in package.pads] == [
        ("1", -1_300_000, 0, 1_000_000, 1_400_000, None),
        ("2", 1_300_000, 0, 1_000_000, 1_400_000, None),
    ]
    assert next(r for r in records if isinstance(r, DeviceRecord)).device.pad_map == (("1", "1"), ("2", "2"))
    assert all(r.header.evidence == "UNVERIFIED" for r in records)


@pytest.mark.parametrize("scalar", ["0.3", "-0.1", "nan", "0.0000001", "bad", ""])
def test_nonzero_or_malformed_scalar_drill_does_not_fabricate_surface_pads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, scalar: str
) -> None:
    legacy_surface_package(source(tmp_path), scalar)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert [r["kind"] for r in env["result"]["items"]] == ["symbol"]
    assert len([r for r in env["issues"] if r["code"] == "library.seed-skipped"]) == 2


@pytest.mark.parametrize("bad", ["hole", "reference"])
def test_legacy_surface_pad_rejects_ambiguous_hole_or_unknown_uuid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
) -> None:
    path = legacy_surface_package(source(tmp_path))
    text = path.read_text()
    if bad == "hole":
        text = text.replace("(drill 0.0)", "(drill 0.0) (hole (diameter 0.4))", 1)
    else:
        text = text.replace(
            "(pad 26600000-0000-4000-8000-000000000021 (drill",
            "(pad 26600000-0000-4000-8000-000000000099 (drill",
        )
    path.write_text(text)
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert [r["kind"] for r in env["result"]["items"]] == ["symbol"]
    assert any(
        "ambiguous" in r["message"] if bad == "hole" else "unmapped" in r["message"] for r in env["issues"]
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


@pytest.mark.parametrize("second", ["2", "Pin_1"])
def test_numeric_function_names_are_reversible_and_collisions_refuse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, second: str
) -> None:
    root = source(tmp_path)
    path = next((root / "cmp").glob("*/component.lp"))
    path.write_text(
        path.read_text().replace('(name "A")', '(name "1")').replace('(name "B")', f'(name "{second}")')
    )
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    if second == "Pin_1":
        assert not any(r["kind"] == "device" for r in env["result"]["items"])
        assert any("normalization collision" in r["message"] for r in env["issues"])
        assert not any(r["code"] == "library.seed-function-normalized" for r in env["issues"])
        return
    warning = next(r for r in env["issues"] if r["code"] == "library.seed-function-normalized")
    assert warning["severity"] == "warning"
    changes = json.loads(warning["message"].split(": ", 1)[1])
    assert [(r["original"], r["normalized"]) for r in changes] == [("1", "Pin_1"), ("2", "Pin_2")]
    assert all(r["component_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest() for r in changes)
    code, repeated, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    assert repeated["result"]["plan"] == env["result"]["plan"]
    code, written, error, _ = run(
        monkeypatch, tmp_path, *arguments(), "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, error
    files = list((tmp_path / "output").rglob("record.toml"))
    records = [parse_record(p.read_text()) for p in files]
    symbol = next(r for r in records if isinstance(r, PinsRecord))
    device = next(r for r in records if isinstance(r, DeviceRecord))
    assert [(p.number, p.name) for p in symbol.pins] == [("1", "1"), ("2", "2")]
    assert [(p.function, p.pin_pads) for p in device.device.pins] == [
        ("Pin_1", (("1", "1"),)),
        ("Pin_2", (("2", "2"),)),
    ]
    device_file = next(p for p in files if p.parent.parent.parent.parent.name == "devices")
    provenance = json.loads((device_file.parent / "PROVENANCE.json").read_text())
    assert provenance_problems(provenance) == []
    assert warning["message"] in provenance["modification_notice"]
    assert warning["message"] in (device_file.parent / "NOTICE").read_text()
    assert [r["signal"] for r in changes] == [
        "26600000-0000-4000-8000-000000000031",
        "26600000-0000-4000-8000-000000000032",
    ]


@pytest.mark.parametrize("angle", ["-90", "450", "45", "-90.0001"])
def test_only_exact_cardinal_pin_angles_are_normalized(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, angle: str
) -> None:
    root = source(tmp_path)
    path = next((root / "sym").glob("*/symbol.lp"))
    path.write_text(path.read_text().replace("(rotation 180)", f"(rotation {angle})"))
    code, env, error, _ = run(monkeypatch, tmp_path, *arguments(), "--dry-run")
    assert code == 0, error
    if angle in {"45", "-90.0001"}:
        assert [r["kind"] for r in env["result"]["items"]] == ["footprint"]
        assert any("noncardinal" in r["message"] for r in env["issues"])
        return
    warning = next(r for r in env["issues"] if r["code"] == "library.seed-angle-normalized")
    changes = json.loads(warning["message"].split(": ", 1)[1])
    expected = 270_000_000 if angle == "-90" else 90_000_000
    assert changes[0]["normalized_microdegrees"] == expected
    assert changes[0]["symbol_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    code, env, error, _ = run(
        monkeypatch, tmp_path, *arguments(), "--confirm", "--plan", env["result"]["plan_id"]
    )
    assert code == 0, error
    pins_path = next(p for p in (tmp_path / "output").rglob("record.toml") if "symbols" in p.parts)
    record = parse_record(pins_path.read_text())
    assert isinstance(record, PinsRecord) and record.symbol is not None
    assert record.symbol.placements[1].rotation == expected
    assert (
        warning["message"]
        in json.loads((pins_path.parent / "PROVENANCE.json").read_text())["modification_notice"]
    )
