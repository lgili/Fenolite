# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""LEGAL.md, LEGAL-ANNEX.md and CONTRIBUTING.md keep their required structure."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from email.message import Message
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
ANNEX_HEADER = ["date", "area", "files touched", "public sources consulted", "author"]


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_legal_has_both_blocks() -> None:
    text = _read("LEGAL.md")
    assert "## A. Format analysis" in text
    assert "## B. Material from organisations" in text


def test_legal_block_a_forbids_reverse_engineering_and_requires_sources() -> None:
    text = _read("LEGAL.md").lower()
    assert "never" in text and "decompile" in text
    assert "docs/formats/" in text and "docs/evidence/sources.md" in text


def test_legal_block_b_states_clean_room() -> None:
    assert "clean-room" in _read("LEGAL.md")


def test_annex_table_header() -> None:
    header_rows = [line for line in _read("LEGAL-ANNEX.md").splitlines() if line.startswith("| date")]
    assert len(header_rows) == 1
    cells = [c.strip() for c in header_rows[0].strip("|").split("|")]
    assert cells == ANNEX_HEADER


def test_contributing_requires_dco() -> None:
    text = _read("CONTRIBUTING.md")
    assert "Signed-off-by:" in text
    assert "https://developercertificate.org/" in text


def test_legal_lists_the_four_prohibitions() -> None:
    text = _read("LEGAL.md")
    for tag in ("(P1)", "(P2)", "(P3)", "(P4)"):
        assert tag in text
    lower = text.lower()
    assert "decompil" in lower and "grammar" in lower and "entitled to read" in lower
    assert "employer's software licence" in lower


def test_legal_allows_facts_with_source_only() -> None:
    assert "only when the fact is recorded there with its source" in _read("LEGAL.md")


def test_contributing_explains_allowed_vs_forbidden() -> None:
    assert "## Allowed vs forbidden derivation" in _read("CONTRIBUTING.md")


# --- fenolite-library (capability ip-hygiene, "Third-party material only in fenolite-library"; c0279) ---

LIBRARY_RULE = "**Third-party material lives only in `fenolite-library`**"


def library_rule_problems(agents: str) -> list[str]:
    """What the "Hard rules" of ``agents`` lack of the fenolite-library rule; empty when it is complete."""
    rules = agents.split("## Hard rules", 1)[-1].split("\n## ", 1)[0]
    found = [block for block in rules.split("\n- ") if LIBRARY_RULE in block]
    if not found:
        return ["AGENTS.md: the hard rule 'Third-party material lives only in fenolite-library' is missing"]
    text = " ".join(found[0].split())
    words = ("github.com/lgili/fenolite-library", "licence", "NOTICE", "`PROVENANCE.json`")
    return [
        f"AGENTS.md: the fenolite-library rule does not name {word}" for word in words if word not in text
    ]


def test_fenolite_library_sentence_present() -> None:
    assert library_rule_problems(_read("AGENTS.md")) == []
    adr = _read("docs/adr/0003-clean-room-and-provenance.md")
    assert [line for line in adr.splitlines() if "fenolite-library" in line and "2026-10-29" in line]


def test_fenolite_library_sentence_removed() -> None:
    text = _read("AGENTS.md")
    start = text.index("- " + LIBRARY_RULE)
    end = text.index("\n- ", start + 2)
    problems = library_rule_problems(text[:start] + text[end + 1 :])
    assert problems and "missing" in problems[0]


def _licences():  # noqa: ANN202
    name = "fenolite_licence_inventory_tool"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools/gen_licences.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def _licence_lock() -> dict:
    """Original illustrative dependency graph, including a cycle and two interpreter versions."""
    return {
        "package": [
            {"name": "fenolite", "optional-dependencies": {"geo": [{"name": "root", "extra": ["draw"]}]}},
            {
                "name": "root",
                "version": "1",
                "dependencies": [{"name": "leaf"}],
                "optional-dependencies": {"draw": [{"name": "painter"}]},
            },
            {"name": "leaf", "version": "1", "dependencies": [{"name": "root"}]},
            {"name": "leaf", "version": "2"},
            {"name": "painter", "version": "1"},
            {"name": "unrelated", "version": "1"},
        ]
    }


def test_inventory_keeps_transitive_extras_and_uninstalled_versions() -> None:
    tool = _licences()
    installed = {("leaf", "1"): tool.Metadata("MIT", "License-Expression")}
    found = tool.inventory(_licence_lock(), installed)
    assert found["runtime"] == ()
    assert [(p.name, p.version) for p in found["geo"]] == [
        ("leaf", "1"),
        ("leaf", "2"),
        ("painter", "1"),
        ("root", "1"),
    ]
    assert found["geo"][0].metadata.licence == "MIT"
    assert found["geo"][1].metadata is None
    text = tool.render(found)
    assert "| leaf | 2 | not inspected |" in text and "unrelated" not in text
    assert text == tool.render(found) and text.endswith("\n") and "\r" not in text


def test_inventory_rejects_missing_locked_dependency() -> None:
    lock = _licence_lock()
    lock["package"][1]["dependencies"].append({"name": "absent"})
    with pytest.raises(ValueError, match="absent.*no matching locked package"):
        _licences().inventory(lock, {})


@pytest.mark.parametrize("licence", ["GPL-3.0-only", "AGPL-3.0-or-later", "LGPL-2.1-only"])
def test_copyleft_transitive_import_is_refused(licence: str) -> None:
    tool = _licences()
    info = tool.Metadata(licence, "License-Expression", copyleft=True)
    found = tool.inventory(_licence_lock(), {("leaf", "1"): info})
    assert tool.copyleft_problems(found) == [
        f"geo: leaf 1: {licence}; copyleft tools require a process boundary"
    ]


def test_mpl_is_limited_to_development_tools() -> None:
    tool = _licences()
    package = tool.Package("authored", "1", tool.Metadata("MPL-2.0", "License-Expression", mpl=True))
    assert tool.copyleft_problems({"dev": (package,)}) == []
    assert tool.copyleft_problems({"suppliers": (package,)})[0].startswith("suppliers: authored")


def test_metadata_expression_precedes_legacy_and_long_text_is_not_copied(monkeypatch) -> None:  # noqa: ANN001
    tool = _licences()
    current = Message()
    current["Name"] = "Authored_Test"
    current["License-Expression"] = "MIT"
    current["License"] = "GPL-3.0-only"
    legacy = Message()
    legacy["Name"] = "Authored-Long"
    payload = "Authored licence declaration for this regression. " * 20
    legacy["License"] = payload
    legacy["Classifier"] = "License :: OSI Approved :: MIT License"
    monkeypatch.setattr(
        tool.importlib.metadata,
        "distributions",
        lambda: [
            SimpleNamespace(metadata=current, version="1"),
            SimpleNamespace(metadata=legacy, version="1"),
        ],
    )
    found = tool.environment()
    assert found[("authored-test", "1")].licence == "MIT"
    assert not found[("authored-test", "1")].copyleft
    summary = found[("authored-long", "1")]
    assert "sha256:" in summary.field and payload not in summary.licence
    assert "MIT License" in summary.licence


def test_inventory_cli_detects_drift_without_writing(tmp_path: Path, monkeypatch, capsys) -> None:  # noqa: ANN001
    tool = _licences()
    (tmp_path / "uv.lock").write_text('[[package]]\nname = "fenolite"\n', encoding="utf-8")
    page = tmp_path / "licences.md"
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    monkeypatch.setattr(tool, "PAGE", page)
    monkeypatch.setattr(tool, "environment", lambda: {})
    assert tool.main([]) == 0
    expected = page.read_bytes()
    assert tool.main(["--check"]) == 0
    page.write_bytes(expected + b"stale\n")
    assert tool.main(["--check"]) == 1
    assert "stale" in capsys.readouterr().err
    assert page.read_bytes() == expected + b"stale\n"


def test_committed_inventory_follows_the_process_boundary_policy() -> None:
    assert _licences().page_copyleft_problems(_read("docs/licences.md")) == []


def test_edited_inventory_cannot_hide_an_imported_copyleft_package() -> None:
    page = "## geo\n\n| Package | Locked version | Declared licence | Metadata |\n|---|---|---|---|\n"
    page += "| authored | 1 | GPL-3.0-only | License-Expression |\n"
    assert _licences().page_copyleft_problems(page) == ["geo: authored 1: GPL-3.0-only (License-Expression)"]


def _release():  # noqa: ANN202
    name = "fenolite_legal_release_tool"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools/release.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def test_legal_review_has_dated_answers_and_existing_evidence() -> None:
    assert _release().legal_review_problems(ROOT) == []
    assert "docs/licences.md" in _read("LEGAL.md")
    assert "docs/release/v1.0-legal-review.md" in _read("LEGAL.md")


def test_unanswered_legal_review_is_refused(tmp_path: Path) -> None:
    page = tmp_path / "docs/release/v1.0-legal-review.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "No lawyer's review is claimed.\n\n"
        "| Id | Claim | Stated in | Shown by | Answer |\n|---|---|---|---|---|\n"
        "| A1 | Authored policy | policy.md | witness.md | |\n",
        encoding="utf-8",
    )
    (tmp_path / "policy.md").write_text("Authored policy.\n", encoding="utf-8")
    (tmp_path / "witness.md").write_text("Authored evidence.\n", encoding="utf-8")
    problems = _release().legal_review_problems(tmp_path)
    assert "legal review row A1 is unanswered" in problems
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "witness.md | |", "witness.md | Accepted 2026-11-01: policy. |"
        ),
        encoding="utf-8",
    )
    problems = _release().legal_review_problems(tmp_path)
    assert "legal review row A1 is unanswered" not in problems
    (tmp_path / "witness.md").unlink()
    assert any("missing evidence witness.md" in p for p in _release().legal_review_problems(tmp_path))


def _viewer_review_tree(root: Path) -> Path:
    for name in (
        "NOTICE",
        "viewer/package.json",
        "viewer/package-lock.json",
        "src/fenolite/view/static/viewer.js",
        "docs/release/v1.0-legal-review.md",
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return root


def test_bundled_asset_requires_its_own_review_row(tmp_path: Path) -> None:
    tree = _viewer_review_tree(tmp_path)
    page = tree / "docs/release/v1.0-legal-review.md"
    page.write_text(
        "\n".join(
            line
            for line in page.read_text(encoding="utf-8").splitlines()
            if not line.startswith("| PREACT |")
        )
        + "\n",
        encoding="utf-8",
    )
    assert "legal review is missing row PREACT" in _release().legal_review_problems(tree)


def test_bundled_asset_notice_change_requires_review_again(tmp_path: Path) -> None:
    tree = _viewer_review_tree(tmp_path)
    notice = tree / "NOTICE"
    notice.write_bytes(notice.read_bytes() + b"\nAuthored notice revision.\n")
    assert "bundled Preact review has a stale NOTICE digest" in _release().legal_review_problems(tree)


def test_bundled_asset_version_change_requires_review_again(tmp_path: Path) -> None:
    tree = _viewer_review_tree(tmp_path)
    package = tree / "viewer/package.json"
    lock = tree / "viewer/package-lock.json"
    manifest = json.loads(package.read_text(encoding="utf-8"))
    locked = json.loads(lock.read_text(encoding="utf-8"))
    manifest["dependencies"]["preact"] = "0.0.1"
    locked["packages"][""]["dependencies"]["preact"] = "0.0.1"
    locked["packages"]["node_modules/preact"]["version"] = "0.0.1"
    package.write_text(json.dumps(manifest), encoding="utf-8")
    lock.write_text(json.dumps(locked), encoding="utf-8")
    assert "bundled Preact review has a stale locked version" in _release().legal_review_problems(tree)


def test_bundle_and_lock_must_retain_reviewed_terms(tmp_path: Path) -> None:
    tree = _viewer_review_tree(tmp_path)
    bundle = tree / "src/fenolite/view/static/viewer.js"
    bundle.write_text(
        bundle.read_text(encoding="utf-8").replace("Permission is hereby granted", "Authored missing notice"),
        encoding="utf-8",
    )
    assert "bundled Preact header lacks its version or permission notice" in _release().legal_review_problems(
        tree
    )
    lock = tree / "viewer/package-lock.json"
    locked = json.loads(lock.read_text(encoding="utf-8"))
    locked["packages"]["node_modules/preact"]["license"] = "UNREVIEWED"
    lock.write_text(json.dumps(locked), encoding="utf-8")
    assert any("lock licence differs" in problem for problem in _release().legal_review_problems(tree))
