# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A human can accept exact content; acceptance never invalidates its own review (c0262)."""

import json
import shutil
from pathlib import Path

import pytest
from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def tree(tmp_path):
    path = tmp_path / "records"
    shutil.copytree(ROOT / "tests/data/library_rules/good", path)
    return path


def check(monkeypatch, tmp_path, path):
    return run(monkeypatch, tmp_path, "library", "check", str(path))


def accept(monkeypatch, tmp_path, path, sha):
    return run(
        monkeypatch,
        tmp_path,
        "library",
        "review",
        str(path),
        "--accept",
        "--reviewer",
        "human-reviewer",
        "--sheet",
        sha[:12],
        "--timestamp",
        "2026-11-02T00:00:00Z",
        "--confirm",
    )


@pytest.fixture(params=["repository", "vendored"])
def nested_tree(tmp_path, request):
    root = tmp_path / "nested"
    selected = {}
    for kind, folder, source, ident in (
        ("symbol", "symbols", "pins", "RuleChipPins"),
        ("footprint", "footprints", "packages", "RuleChip"),
        ("device", "devices", "devices", "RuleChipDevice"),
    ):
        category = Path("cc0") if request.param == "repository" else Path()
        target = root / folder / category / "Rules" / ident / "record.toml"
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / f"tests/data/library_rules/good/{source}/chip.toml", target)
        manifest = {
            "schema": "fenolite.library-item.v0",
            "kind": kind,
            "id": f"Rules:{ident}",
            "version": "1.0.0",
            "title": ident,
            "summary": "Authored nested review control",
            "spdx": "CC0-1.0",
            "tags": [],
            "files": ["record.toml"],
            "depends": [],
            "executes": False,
        }
        target.with_name("item.json").write_text(json.dumps(manifest))
        selected[kind] = target
    return selected


def test_nested_device_review_and_dependency_staleness(monkeypatch, tmp_path, nested_tree):
    path = nested_tree["device"]
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 0, reply
    assert len(reply["result"]["items"]) == 1
    sha = reply["result"]["items"][0]["sheet"]["sha256"]
    assert accept(monkeypatch, tmp_path, path, sha)[0] == 0
    assert check(monkeypatch, tmp_path, path)[1]["result"]["items"][0]["review"]["state"] == "accepted"
    dependency = nested_tree["symbol"]
    dependency.write_text(dependency.read_text().replace('name = "P1"', 'name = "EDITED"'))
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 5
    assert "library.review-stale" in {finding["code"] for finding in reply["issues"]}


@pytest.mark.parametrize("manifest", [None, "invalid", "mismatch", "unlisted", "too_deep"])
def test_nested_device_does_not_trust_unbound_manifest(monkeypatch, tmp_path, nested_tree, manifest):
    path = nested_tree["device"]
    metadata = path.with_name("item.json")
    if manifest is None:
        metadata.unlink()
    elif manifest == "invalid":
        metadata.write_text("{")
    elif manifest == "too_deep":
        deeper = path.parent / "extra" / "deeper" / "deeper_again" / "record.toml"
        deeper.parent.mkdir(parents=True)
        shutil.move(path, deeper)
        shutil.move(metadata, deeper.with_name("item.json"))
        path = deeper
    else:
        value = json.loads(metadata.read_text())
        if manifest == "mismatch":
            value["id"] = "Rules:OtherDevice"
        else:
            value["files"] = ["other.toml"]
        metadata.write_text(json.dumps(value))
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 5
    assert any("unresolved symbol" in finding["message"] for finding in reply["issues"])


@pytest.mark.parametrize(
    "target", ["pins/chip.toml", "packages/chip.toml", "devices/chip.toml", "packages/waived_connector.toml"]
)
def test_accept_check_check_and_revoke(monkeypatch, tmp_path, tree, target):
    from fenolite.catalog import records

    path = tree / target
    before = path.read_bytes()
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 0, reply
    sha = reply["result"]["items"][0]["sheet"]["sha256"]
    code, accepted, _, _ = accept(monkeypatch, tmp_path, path, sha)
    assert code == 0, accepted
    assert accepted["receipt"]
    for _ in range(2):
        code, reply, _, _ = check(monkeypatch, tmp_path, path)
        assert code == 0, reply
        row = reply["result"]["items"][0]
        assert row["review"]["state"] == "accepted" and row["sheet"]["sha256"] == sha
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "review", str(path), "--revoke", "--confirm")
    assert code == 0, reply
    # Revoke restores semantic content; canonical writing deliberately normalizes source formatting.
    if target.startswith("packages/chip"):
        import tomllib

        assert tomllib.loads(path.read_text()) == tomllib.loads(before.decode())
    else:
        assert records.parse_record(path.read_text()) == records.parse_record(before.decode())


def test_edited_record_dependency_and_reformat(monkeypatch, tmp_path, tree):
    path = tree / "devices/chip.toml"
    sha = check(monkeypatch, tmp_path, path)[1]["result"]["items"][0]["sheet"]["sha256"]
    assert accept(monkeypatch, tmp_path, path, sha)[0] == 0
    path.write_text("\n# whitespace only\n" + path.read_text())
    assert check(monkeypatch, tmp_path, path)[0] == 0
    pins = tree / "pins/chip.toml"
    pins.write_text(pins.read_text().replace('name = "P1"', 'name = "CHANGED"'))
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 5 and "library.review-stale" in {f["code"] for f in reply["issues"]}
    assert reply["result"]["items"][0]["effective_evidence"] == "INFERRED"


def test_review_preconditions_state_and_stale_sheet(monkeypatch, tmp_path, tree):
    path = tree / "pins/chip.toml"
    assert run(monkeypatch, tmp_path, "library", "review", str(path))[0] == 0
    assert run(monkeypatch, tmp_path, "library", "review", str(path), "--reviewer", "who")[0] == 2
    before = path.read_bytes()
    assert accept(monkeypatch, tmp_path, path, "a" * 64)[0] == 4
    assert path.read_bytes() == before
    for reviewer in ("", "name@example.test"):
        assert (
            run(
                monkeypatch,
                tmp_path,
                "library",
                "review",
                str(path),
                "--accept",
                "--reviewer",
                reviewer,
                "--sheet",
                "a" * 64,
                "--confirm",
            )[0]
            == 2
        )
    path.write_text(path.read_text().replace('evidence = "INFERRED"', 'evidence = "KICAD-VERIFIED (10.0.6)"'))
    assert accept(monkeypatch, tmp_path, path, "a" * 64)[0] == 7


def test_error_blocks_review_and_bad_waiver(monkeypatch, tmp_path, tree):
    path = tree / "pins/chip.toml"
    path.write_text(path.read_text().replace('"-5.08mm"', '"-0.127mm"'))
    assert accept(monkeypatch, tmp_path, path, "a" * 64)[0] == 5
    path.write_text(path.read_text() + '\n[[waiver]]\ncode="library.review-stale"\nreason="invalid"\n')
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 5 and "library.record-invalid" in {f["code"] for f in reply["issues"]}


def test_authored_description_suffix_edit_stales_accepted_content(monkeypatch, tmp_path, tree):
    path = tree / "packages/waived_connector.toml"
    sha = check(monkeypatch, tmp_path, path)[1]["result"]["items"][0]["sheet"]["sha256"]
    assert accept(monkeypatch, tmp_path, path, sha)[0] == 0
    suffix = "; land pattern remains INFERRED and requires part-specific review"
    text = path.read_text()
    text = text.replace('summary = "Cable-end pin 1"', 'summary = "Cable-end pin 1' + suffix + '"')
    path.write_text(text)
    code, reply, _, _ = check(monkeypatch, tmp_path, path)
    assert code == 5 and "library.review-stale" in {f["code"] for f in reply["issues"]}


def test_accept_plan_refuses_changed_referenced_record(monkeypatch, tmp_path, tree):
    path = tree / "devices/chip.toml"
    sha = check(monkeypatch, tmp_path, path)[1]["result"]["items"][0]["sheet"]["sha256"]
    args = (
        "library",
        "review",
        str(path),
        "--accept",
        "--reviewer",
        "human-reviewer",
        "--sheet",
        sha,
        "--timestamp",
        "2026-11-02T00:00:00Z",
    )
    code, planned, _, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, planned
    before = path.read_bytes()
    package = tree / "packages/chip.toml"
    package.write_text(package.read_text().replace('length="0.8mm"', 'length="0.9mm"'))
    code, _, error, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", planned["result"]["plan_id"])
    assert code == 4 and error["code"] == "FEN-4002"
    assert path.read_bytes() == before


def test_device_review_on_a_later_day_keeps_its_digest(monkeypatch, tmp_path, nested_tree):
    """c0266 task 6.2: a device record holds its evidence twice (header and device). A renewed acceptance on
    another day must store the digest of the record as written, or a record with an origin is refused by
    every strict read (the library audit) as unreviewed."""
    from fenolite.catalog import records

    path = nested_tree["device"]
    origin = 'origin = { library = "Synthetic", version = "1", element = "e1", licence = "CC0-1.0" }\n'
    text = path.read_text().replace('licence = "CC0-1.0"\n', 'licence = "CC0-1.0"\n' + origin, 1)
    path.write_text(text.replace('evidence = "INFERRED"', 'evidence = "UNVERIFIED"'))
    for day in ("2026-11-02", "2026-11-04"):
        sha = check(monkeypatch, tmp_path, path)[1]["result"]["items"][0]["sheet"]["sha256"]
        code = run(
            monkeypatch,
            tmp_path,
            "library",
            "review",
            str(path),
            "--accept",
            "--reviewer",
            "human-reviewer",
            "--sheet",
            sha[:12],
            "--timestamp",
            f"{day}T00:00:00Z",
            "--confirm",
        )[0]
        assert code == 0
        written = path.read_text()
        assert f'evidence = "CORPUS-VERIFIED (review {day})"' in written
        record = records.parse_record(written, file=str(path))
        assert record.header.reviewed_by[-1].record_sha256 == records.record_digest(record)
        assert check(monkeypatch, tmp_path, path)[1]["result"]["items"][0]["review"]["state"] == "accepted"
