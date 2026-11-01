# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library check, mixed traversal, exact sheet plans and comparison (c0262)."""

import hashlib
import json
import shutil
from pathlib import Path

from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
GOOD = ROOT / "tests/data/library_rules/good"


def external_sources(tmp_path):
    tree = tmp_path / "external"
    shutil.copytree(ROOT / "examples/library-devices/source", tree)
    register = tree / "sources.toml"
    register.write_text(register.read_text().replace("D-0001", "D-0003"))
    paths = sorted(tree.glob("*/cc0/*/*/record.toml"))
    assert len(paths) == 3
    for path in paths:
        path.write_text(path.read_text().replace("D-0001", "D-0003"))
    return tree, paths


def test_external_sources_registered_for_all_device_kinds(monkeypatch, tmp_path):
    _, paths = external_sources(tmp_path)
    code, reply, error, _ = run(monkeypatch, tmp_path, "library", "check", *map(str, paths))
    assert code == 0, (reply, error)
    assert {row["kind"] for row in reply["result"]["items"]} == {"pins", "package", "device"}
    assert not any(issue["code"] == "library.source-unknown" for issue in reply["issues"])


def test_external_sources_unregistered_comment_is_rejected(monkeypatch, tmp_path):
    tree, paths = external_sources(tmp_path)
    register = tree / "sources.toml"
    register.write_text(register.read_text() + "\n# D-0099 is not a registered source.\n")
    for path in paths:
        path.write_text(path.read_text().replace("D-0003", "D-0099"))
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", *map(str, paths))
    assert code == 5
    findings = [issue for issue in reply["issues"] if issue["code"] == "library.source-unknown"]
    assert findings and all("D-0099" in issue["message"] for issue in findings)


def test_external_sources_missing_register_is_rejected(monkeypatch, tmp_path):
    tree, paths = external_sources(tmp_path)
    (tree / "sources.toml").unlink()
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", *map(str, paths))
    assert code == 5
    assert any(issue["code"] == "library.source-unknown" for issue in reply["issues"])


def test_external_sources_malformed_row_is_bad_input(monkeypatch, tmp_path):
    tree, paths = external_sources(tmp_path)
    register = tree / "sources.toml"
    register.write_text(
        "\n".join(line for line in register.read_text().splitlines() if not line.startswith("used ="))
    )
    code, reply, error, _ = run(
        monkeypatch, tmp_path, "library", "check", *map(str, paths), "--sheets", "review", "--dry-run"
    )
    assert code == 3 and error["code"] == "FEN-3004", reply
    assert "sources.toml" in error["message"] and "used" in error["message"]
    assert not reply["result"].get("plan") and not (tmp_path / "review").exists()


def test_external_sources_legacy_s_register_stays_supported(monkeypatch, tmp_path):
    tree, paths = external_sources(tmp_path)
    (tree / "sources.toml").write_text(
        'schema = "fenolite.sources.v0"\n[sources.S-1234]\ntitle = "Authored project source"\n'
    )
    for path in paths:
        path.write_text(path.read_text().replace("D-0003", "S-1234"))
    code, reply, error, _ = run(monkeypatch, tmp_path, "library", "check", *map(str, paths))
    assert code == 0, (reply, error)
    assert not any(issue["code"] == "library.source-unknown" for issue in reply["issues"])


def copy_records(tmp_path):
    target = tmp_path / "records"
    shutil.copytree(GOOD, target)
    return target


def test_clean_records_and_plain_library_mixed_folder(monkeypatch, tmp_path):
    from fenolite.backends.kicad.mod import write_footprint
    from fenolite.catalog.footprints import generate, read_package

    tree = copy_records(tmp_path)
    (tree / "broken.toml").write_text("schema = [")
    pretty = tree / "Demo.pretty"
    pretty.mkdir()
    fp = generate(read_package((tree / "packages/chip.toml").read_text())).footprint
    assert fp is not None
    (pretty / "chip.kicad_mod").write_text(write_footprint(fp))
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", "records")
    assert code == 5, reply
    assert sum(f["code"] == "library.record-invalid" for f in reply["issues"]) == 1
    plain = next(i for i in reply["result"]["items"] if i["kind"] == "footprint")
    assert "library.body-span" not in plain["rules_run"]


def test_sheets_dry_run_deterministic_and_receipt(monkeypatch, tmp_path):
    tree = copy_records(tmp_path)
    args = ("library", "check", str(tree / "devices/chip.toml"), "--sheets", "review")
    code, reply, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, reply
    assert not (tmp_path / "review").exists()
    plan = reply["result"]["plan"]
    assert len(plan) == 3
    code, written, _, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", reply["result"]["plan_id"])
    assert code == 0, written
    manifest = json.loads((tmp_path / "review/sheets.json").read_text())
    row = manifest["items"][0]
    sheet = (tmp_path / "review" / row["path"]).read_bytes()
    assert hashlib.sha256(sheet).hexdigest() == row["sha256"]
    assert b"Pin table" in sheet and b"Pin-to-pad map" in sheet
    assert written["receipt"]
    assert run(monkeypatch, tmp_path, *args, "--confirm")[0] == 0
    assert (tmp_path / "review" / row["path"]).read_bytes() == sheet


def test_findings_exit_warning_threshold_and_selection(monkeypatch, tmp_path):
    path = ROOT / "tests/data/library_rules/bad/pin_group_type.toml"
    assert run(monkeypatch, tmp_path, "library", "check", str(path))[0] == 0
    assert run(monkeypatch, tmp_path, "library", "check", str(path), "--fail-on", "warning")[0] == 5
    code, reply, _, _ = run(
        monkeypatch, tmp_path, "library", "check", str(path), "--skip", "library.pin-group-type"
    )
    assert code == 0 and not reply["issues"]
    assert run(monkeypatch, tmp_path, "library", "check", "missing")[0] == 3
    assert run(monkeypatch, tmp_path, "library", "check", str(path), "--rules", "unknown")[0] == 2


def test_compare_same_added_removed_fields_and_interface(monkeypatch, tmp_path):
    tree = copy_records(tmp_path)
    old = tmp_path / "old"
    shutil.copytree(tree, old)
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", "records", "--compare", "old")
    assert code == 0 and all(p["change"] == "same" for p in reply["result"]["compare"])
    path = tree / "pins/chip.toml"
    path.write_text(path.read_text().replace('name = "P1"', 'name = "RENAMED"'))
    (tree / "devices/to.toml").unlink()
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", "records", "--compare", "old")
    assert code == 0, reply
    pairs = reply["result"]["compare"]
    assert any(p["change"] == "changed" and p["symbol_changed"] for p in pairs)
    assert "library.removed" in {f["code"] for f in reply["issues"]}
    path.write_text(path.read_text().replace('number = "1"', 'number = "9"'))
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", "records", "--compare", "old")
    assert code == 5 and "library.interface-changed" in {f["code"] for f in reply["issues"]}


def test_compare_sheets_reuses_visual_overlay(monkeypatch, tmp_path):
    tree = copy_records(tmp_path)
    old = tmp_path / "old"
    shutil.copytree(tree, old)
    path = tree / "packages/chip.toml"
    path.write_text(path.read_text().replace('length="0.8mm"', 'length="0.9mm"'))
    code, reply, _, _ = run(
        monkeypatch,
        tmp_path,
        "library",
        "check",
        "records/packages/chip.toml",
        "--compare",
        "old/packages/chip.toml",
        "--sheets",
        "review",
        "--confirm",
    )
    assert code == 0, reply
    pair = reply["result"]["compare"][0]
    assert pair["footprint_changed"] and "land.pad.length" in pair["fields"]
    html = (tmp_path / "review" / reply["result"]["items"][0]["sheet"]["path"]).read_text()
    assert "review-diff-0" in html and "Visual diff" in html and "srcdoc=" in html


def test_manufacturer_land_detects_generator_drift(monkeypatch, tmp_path):
    from dataclasses import replace

    from fenolite.cli import _library_check
    from fenolite.core.coords import Size

    original = _library_check.generate

    def drift(package, **kwargs):
        generated = original(package, **kwargs)
        fp = generated.footprint
        assert fp is not None
        pads = (replace(fp.pads[0], size=Size(fp.pads[0].size.w + 100_000, fp.pads[0].size.h)), *fp.pads[1:])
        return replace(generated, footprint=replace(fp, pads=pads))

    monkeypatch.setattr(_library_check, "generate", drift)
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", str(GOOD / "packages/chip.toml"))
    assert code == 5
    assert "library.land-mismatch" in {f["code"] for f in reply["issues"]}


def test_sheet_paths_do_not_collide_when_namespaces_contain_underscores(monkeypatch, tmp_path):
    text = (GOOD / "pins/chip.toml").read_text()
    for name, ident in (("a.toml", "Rules_A:B"), ("b.toml", "Rules:A_B")):
        (tmp_path / name).write_text(text.replace("Rules:RuleChipPins", ident))
    code, reply, _, _ = run(
        monkeypatch, tmp_path, "library", "check", "a.toml", "b.toml", "--sheets", "review", "--dry-run"
    )
    assert code == 0, reply
    paths = [row["path"] for row in reply["result"]["plan"]]
    assert len(paths) == len(set(paths)) == 4
