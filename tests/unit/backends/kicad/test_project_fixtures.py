# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""GUI-saved project fixtures and the packaged templates (hypotheses H-K-PRO-VERSION and
H-K-PRO-TUNING; change c0010 Decisions 4 and 5)."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.lowering import FLOOR_KEYS
from fenolite.backends.kicad.pro import PROJECT_VERSIONS, TEN_ONLY_PATHS, template

ROOT = Path(__file__).resolve().parents[4]
PROJECTS = ROOT / "tests" / "data" / "kicad" / "project"
EMPTY_10 = PROJECTS / "empty_10.kicad_pro"
EMPTY_9 = PROJECTS / "empty_9.kicad_pro"
TEN_ONLY_TOP = ("component_class_settings", "tuning_profiles", "time_domain_parameters")


def fixture(path: Path) -> JsonObject:
    return _json.loads(path.read_text(encoding="utf-8"))


def pair(data: JsonObject) -> tuple[int, int]:
    return int(data["meta"]["version"].text), int(data["net_settings"]["meta"]["version"].text)


def derived_9(data: JsonObject) -> JsonObject:
    """Decision 5: the 9 template from the 10 one, without the 10.0-only paths, net settings version 4."""
    for key in TEN_ONLY_TOP:
        data.pop(key, None)
    for cls in data["net_settings"]["classes"]:
        cls.pop("tuning_profile", None)
    data["net_settings"]["meta"]["version"] = JsonNumber("4")
    return data


def test_version_pairs() -> None:
    assert pair(fixture(EMPTY_10)) == PROJECT_VERSIONS[10]
    assert pair(template(10)) == PROJECT_VERSIONS[10] and pair(template(9)) == PROJECT_VERSIONS[9]
    if EMPTY_9.is_file():
        assert pair(fixture(EMPTY_9)) == PROJECT_VERSIONS[9]


def test_tuning_profiles() -> None:
    ten = fixture(EMPTY_10)
    assert "tuning_profiles" in ten and all("tuning_profile" in c for c in ten["net_settings"]["classes"])
    nine = fixture(EMPTY_9) if EMPTY_9.is_file() else template(9)
    assert "tuning_profiles" not in nine and not any(
        "tuning_profile" in c for c in nine["net_settings"]["classes"]
    )
    assert "/tuning_profiles" in TEN_ONLY_PATHS and "/net_settings/classes/*/tuning_profile" in TEN_ONLY_PATHS


def test_templates_match_fixtures() -> None:
    ten = fixture(EMPTY_10)
    ten["meta"]["filename"] = ""
    assert _json.structural_equal(template(10), ten)
    nine = fixture(EMPTY_9) if EMPTY_9.is_file() else derived_9(fixture(EMPTY_10))
    nine["meta"]["filename"] = ""
    assert _json.structural_equal(template(9), nine)
    assert TEN_ONLY_PATHS == _json.key_paths(template(10)) - _json.key_paths(template(9))


def test_fixture_floors() -> None:
    for path in sorted(PROJECTS.glob("*.kicad_pro")):
        data = fixture(path)
        assert data["meta"]["version"] == JsonNumber("3"), path.name
        rules = data["board"]["design_settings"]["rules"]
        assert set(FLOOR_KEYS.values()) <= set(rules), path.name


def test_default_class() -> None:
    (default,) = template(10)["net_settings"]["classes"]
    assert default["name"] == "Default" and default["priority"] == JsonNumber("2147483647")
    assert template(10)["net_settings"]["netclass_patterns"] == []
    assert template(10)["boards"] == [] and template(10)["net_settings"]["netclass_assignments"] is None
