# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite blocks list|show|doc|where`` (capability cli-contract, "Blocks command verbs", "Blocks list
command", "Blocks show command", "Blocks doc command" and "Blocks where command"; capability
block-library, "Catalog sources of blocks" and "Replacements of blocks"; change c0268)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli.blocksrc import find_blocks

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "blocks"
DIVIDER = "tests/data/blocks/divider.py"
REPLACE = "tests/data/blocks/replace.py"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    target = tmp_path / "tests" / "data" / "blocks"
    target.mkdir(parents=True)
    for name in ("divider.py", "replace.py"):
        shutil.copy(DATA / name, target / name)
    return tmp_path


def lock(path: Path, design: str, entries: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['schema = "fenolite.lock.v0"', f'design = "{design}"', "", "[blocks]"]
    lines += [f'"{key}" = "{value}"' for key, value in entries.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_list_shipped_and_file_blocks(folder: Path) -> None:
    """Scenario "Shipped and file blocks"."""
    entries = find_blocks(files=[DIVIDER], cwd=folder)
    assert [(e.id, e.source) for e in entries if e.source == "file"] == [("Acme:divider", "file")]
    assert all(e.source == "builtin" for e in entries if e.id != "Acme:divider")
    assert not (folder / "tests" / "data" / "blocks" / "__pycache__").exists()


def test_list_with_a_file_source(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Scenario "List with a file source"."""
    code, env, err, _ = run(monkeypatch, folder, "blocks", "list", "--from", DIVIDER)
    assert code == 0, err
    (row,) = [row for row in env["result"]["blocks"] if row["id"] == "Acme:divider"]
    assert (row["source"], row["version"], row["category"], row["deprecated"]) == (
        "file",
        "1.0.0",
        "analog",
        False,
    )
    assert row["where"] == DIVIDER and row["digest"].startswith("sha256:")
    assert env["receipt"] is None and "plan" not in env["result"]


def test_list_category_and_duplicates(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    code, env, _, _ = run(
        monkeypatch, folder, "blocks", "list", "--from", REPLACE, "--from", DIVIDER, "--category", "analog"
    )
    assert code == 0 and [row["id"] for row in env["result"]["blocks"]] == ["Acme:divider"]
    shutil.copy(folder / DIVIDER, folder / "copy.py")
    code, env, _, _ = run(monkeypatch, folder, "blocks", "list", "--from", DIVIDER, "--from", "copy.py")
    assert code == 5
    (issue,) = env["issues"]
    assert (
        issue["code"] == "blocks.duplicate-id"
        and DIVIDER in issue["message"]
        and "copy.py" in issue["message"]
    )
    assert [row["where"] for row in env["result"]["blocks"]] == ["copy.py", DIVIDER]


def test_show_the_authored_divider(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Scenario "Show the authored divider"."""
    code, env, err, _ = run(monkeypatch, folder, "blocks", "show", "Acme:divider", "--from", DIVIDER)
    assert code == 0, err
    block = env["result"]["block"]
    assert [port["name"] for port in block["ports"]] == ["HI", "LO", "OUT"]
    assert set(block["digests"]) == {"record", "definition", "interface"}
    assert (block["schema"], block["source"], block["where"]) == ("fenolite.block.v0", "file", DIVIDER)
    assert str(folder) not in str(env)


def test_show_unknown_id(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Scenario "Unknown id"."""
    code, _, err, _ = run(monkeypatch, folder, "blocks", "show", "Acme:divder", "--from", DIVIDER)
    assert code == 2 and err["code"] == "FEN-2001" and "Acme:divider" in err["hint"]


def test_show_replacement_without_deprecation(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Scenario "Replacement without deprecation"."""
    code, _, err, _ = run(monkeypatch, folder, "blocks", "show", "Acme:div2", "--from", REPLACE)
    assert code == 3 and err["code"] == "FEN-3004"
    assert "Acme:div" in err["message"] and "Acme:div2" in err["message"]


def test_show_a_block_that_fails(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    (folder / "broken.py").write_text(
        "from fenolite.dsl import block\n\n\n"
        '@block(id="Acme:broken", version="1.0.0", summary="Fails", licence="MIT")\n'
        "def broken(b):\n    raise ValueError('no luck')\n",
        encoding="utf-8",
    )
    code, _, err, _ = run(monkeypatch, folder, "blocks", "show", "Acme:broken", "--from", "broken.py")
    assert code == 3 and err["code"] == "FEN-3004" and "no luck" in err["message"]


def test_show_verb_usage(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    assert run(monkeypatch, folder, "blocks", "show")[0] == 2
    assert run(monkeypatch, folder, "blocks", "list", "Acme:divider")[0] == 2
    assert run(monkeypatch, folder, "blocks", "show", "Acme:divider", "--category", "analog")[0] == 2
    code, _, err, _ = run(monkeypatch, folder, "blocks", "list", "--from", "missing.py")
    assert code == 3 and err["code"] == "FEN-3004"


def test_list_verbs_in_capabilities(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Scenario "Verbs in capabilities": the entry of ``blocks`` names its four verbs."""
    code, env, _, _ = run(monkeypatch, folder, "capabilities", "--no-tools")
    assert code == 0
    (entry,) = [c for c in env["result"]["commands"] if c["name"] == "blocks"]
    assert entry["verbs"] == ["blocks list", "blocks show", "blocks doc", "blocks where"]


def test_doc_page_planned_not_written(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    """Scenario "Page planned, not written"."""
    args = ("blocks", "doc", "Acme:divider", "--from", DIVIDER, "--out", "D")
    code, env, err, _ = run(monkeypatch, folder, *args, "--dry-run")
    assert code == 0, err
    assert [(p["path"], p["kind"]) for p in env["result"]["plan"]] == [("D/Acme/divider.md", "block-doc")]
    assert not (folder / "D").exists()
    code, env, err, _ = run(monkeypatch, folder, *args, "--confirm")
    assert code == 0, err
    text = (folder / "D" / "Acme" / "divider.md").read_text(encoding="utf-8")
    assert (
        text.startswith("# Acme:divider 1.0.0\n")
        and "| current | quantity | ampere | 100uA | 1uA to 10mA |" in text
    )
    assert [w["path"] for w in env["receipt"]["written"]] == ["D/Acme/divider.md"]


def test_doc_text(monkeypatch: pytest.MonkeyPatch, folder: Path) -> None:
    code, env, _, _ = run(monkeypatch, folder, "blocks", "doc", "Acme:divider", "--from", DIVIDER)
    assert code == 0 and env["result"]["text"].startswith("# Acme:divider 1.0.0")
    assert env["receipt"] is None


def test_where_two_designs_use_one_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Two designs use one block"."""
    lock(tmp_path / "a" / "design.lock", "a", {"sense_a": "Acme:divider@1.0.0", "other": "Acme:div@1.0.0"})
    lock(tmp_path / "b" / "design.lock", "b", {"adc": "Acme:divider@1.1.0"})
    (tmp_path / "b" / "broken.lock").write_text("not toml [", encoding="utf-8")
    code, env, err, _ = run(monkeypatch, tmp_path, "blocks", "where", "Acme:divider", "a", "b")
    assert code == 0, err
    assert env["result"]["uses"] == [
        {"lock": "a/design.lock", "design": "a", "instance": "sense_a", "version": "1.0.0"},
        {"lock": "b/design.lock", "design": "b", "instance": "adc", "version": "1.1.0"},
    ]
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("blocks.lock-unreadable", "warning", "b/broken.lock")
    ]


def test_where_default_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    lock(tmp_path / "x" / "y.lock", "y", {"d": "Acme:divider@1.0.0"})
    code, env, _, _ = run(monkeypatch, tmp_path, "blocks", "where", "Acme:divider")
    assert code == 0 and [u["lock"] for u in env["result"]["uses"]] == ["x/y.lock"]
    assert run(monkeypatch, tmp_path, "blocks", "where", "Acme:divider", "nowhere")[0] == 3
