# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A human can accept exact content; acceptance never invalidates its own review (c0262)."""

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
