# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The importer's exclusion profiles as shipped (capability design-equivalence, "Importer exclusion list
per version" and "Triangle evidence over the corpus"): the file loads, and every rule is registered,
documented and recorded."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from fenolite.backends.kicad import altium_import
from fenolite.checks.equivalence import Profile, load_profiles, select_profile
from fenolite.verify import load_register

ROOT = Path(__file__).resolve().parents[4]
FACTS = ROOT / "docs" / "formats" / "kicad" / "cli.md"
EVIDENCE_PAGE = ROOT / "docs" / "evidence" / "equivalence-triangle.md"
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"


def _profiles() -> tuple[Profile, ...]:
    return load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE)


def test_data_file_loads() -> None:
    profiles = _profiles()
    assert profiles and {p.name for p in profiles} == {altium_import.PROFILE}
    assert {p.tool for p in profiles} == {"kicad-cli"}
    assert "10.0" in {p.tool_version for p in profiles}
    assert len({p.tool_version for p in profiles}) == len(profiles)
    for profile in profiles:
        assert profile.frame == "relative"  # KiCad moves an imported board on its sheet
        assert profile.tolerance_nm % 10 == 0 and profile.tolerance_udeg == 0
        assert re.fullmatch(r"\d+\.\d+", profile.tool_version), profile.tool_version
    assert select_profile(profiles, altium_import.PROFILE, "10.0.6") is not None
    assert select_profile(profiles, altium_import.PROFILE, "9.0.9") is None


def test_rules_name_registered_hypotheses_and_corpus_rows() -> None:
    registered = {row.id for row in load_register(ROOT / "docs" / "hypotheses.md")}
    rows = {row["id"] for row in tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]}
    for profile in _profiles():
        for rule in profile.rules:
            assert rule.hypothesis in registered, rule.id
            assert rule.id.startswith(f"kicad-{profile.tool_version}-"), rule.id
            assert rule.corpus and set(rule.corpus) <= rows, rule.id
            assert len(rule.reason) >= 40, rule.id


def test_rule_facts_are_documented() -> None:
    page = FACTS.read_text(encoding="utf-8")
    assert page.count("## Importer differences") == 1
    section = page.split("## Importer differences", 1)[1].split("\n## ", 1)[0]
    assert "| fact | source | label | hypothesis |" in section
    for profile in _profiles():
        for rule in profile.rules:
            rows = [line for line in section.splitlines() if line.startswith(f"| `{rule.id}`")]
            assert len(rows) == 1, f"{rule.id}: one fact row in {FACTS.name}, found {len(rows)}"
            assert page.count(f"`{rule.id}`") == 1, rule.id
            assert rows[0].rstrip(" |").endswith(rule.hypothesis), rule.id
            label = rows[0].split(" | ")[2]
            if rule.attribution == "undecided":
                assert label == "INFERRED", rule.id
            else:
                assert label.startswith("ORACLE-VERIFIED(kicad-cli)"), rule.id


def test_evidence_page_matches_the_data() -> None:
    page = EVIDENCE_PAGE.read_text(encoding="utf-8")
    for profile in _profiles():
        assert f"kicad-cli {profile.tool_version}" in page, profile.tool_version
        assert f"`tolerance_nm` is {profile.tolerance_nm}" in page
        for rule in profile.rules:
            assert f"| `{rule.id}` |" in page, rule.id
            row = next(line for line in page.splitlines() if line.startswith(f"| `{rule.id}` |"))
            assert f"| {rule.attribution} |" in row, rule.id
            for corpus_row in rule.corpus:
                assert page.count(corpus_row) >= 1, corpus_row
    for heading in (
        "## Where the triangle runs",
        "## Committed document, kicad-cli 10.0",
        "## Corpus, kicad-cli 10.0",
    ):
        assert page.count(heading) == 1, heading
