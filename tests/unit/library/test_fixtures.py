# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored review fixtures cover every generated package family (c0262)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))
from _checkcli import run  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
GOOD = ROOT / "tests/data/library_rules/good"


def test_good_fixtures_cover_every_family_and_are_declared(monkeypatch, tmp_path):
    from fenolite.catalog.footprints.record import FAMILIES

    assert {p.stem for p in (GOOD / "packages").glob("*.toml")} >= set(FAMILIES)
    manifest = (ROOT / "tests/data/MANIFEST.toml").read_text()
    for path in GOOD.rglob("*.toml"):
        assert "# SPDX-License-Identifier: CC0-1.0" in path.read_text()
        assert "Authored for Fenolite" in path.read_text()
        assert path.relative_to(ROOT).as_posix() in manifest
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", str(GOOD))
    assert code == 0, reply
    assert not [f for f in reply["issues"] if f["severity"] in {"error", "warning"}]


def test_bad_fixtures_trigger_the_named_rule(monkeypatch, tmp_path):
    for path in sorted((ROOT / "tests/data/library_rules/bad").glob("*.toml")):
        code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", str(path))
        expected = "library." + path.stem.replace("_", "-")
        assert expected in {f["code"] for f in reply["issues"]}, (path, reply)
        assert code in {0, 5}
