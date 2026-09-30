# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Corpus policy: manifest schema, embeddable rule, declared data files, and the fetch tool."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
DATA_MANIFEST = ROOT / "tests" / "data" / "MANIFEST.toml"
EMBEDDABLE_LICENSES = {"CC0-1.0"}
KEYS = {"id", "url", "ref", "sha256", "license", "license_variant", "embeddable", "uses", "notes"}


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fenolite_corpus_fetch", ROOT / "tools" / "corpus_fetch.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def manifest_problems(entries: list[dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        ident = str(entry.get("id", "?"))
        missing = KEYS - entry.keys()
        if missing:
            problems.append(f"{ident}: missing {sorted(missing)}")
            continue
        if ident in seen:
            problems.append(f"{ident}: duplicate id")
        seen.add(ident)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", ident):
            problems.append(f"{ident}: id must be kebab-case")
        if not re.fullmatch(r"[0-9a-f]{64}", str(entry["sha256"])):
            problems.append(f"{ident}: sha256 must be 64 lowercase hex digits")
        if entry["embeddable"] and entry["license"] not in EMBEDDABLE_LICENSES:
            problems.append(f"{ident}: embeddable requires license in {sorted(EMBEDDABLE_LICENSES)}")
    return problems


def data_file_problems(root: Path, corpus: list[dict[str, Any]], declared: list[dict[str, Any]]) -> list[str]:
    embeddable = {str(e["id"]) for e in corpus if e.get("embeddable")}
    known = {str(e["id"]) for e in corpus}
    by_path = {str(d.get("path")): d for d in declared}
    problems: list[str] = []
    for top in ("tests/data", "examples"):
        for path in sorted((root / top).rglob("*")):
            rel = path.relative_to(root).as_posix()
            if not path.is_file() or path.name in ("README.md", "MANIFEST.toml", ".gitkeep"):
                continue
            decl = by_path.get(rel)
            if decl is None:
                problems.append(f"{rel}: not declared in tests/data/MANIFEST.toml")
            elif decl.get("origin") == "corpus":
                cid = str(decl.get("corpus_id", ""))
                if cid not in known:
                    problems.append(f"{rel}: unknown corpus id {cid!r}")
                elif cid not in embeddable:
                    problems.append(f"{rel}: corpus item {cid!r} is not embeddable")
            elif decl.get("origin") != "authored":
                problems.append(f"{rel}: origin must be 'authored' or 'corpus'")
    return problems


def test_manifest_schema() -> None:
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    problems = manifest_problems(entries)
    assert not problems, "\n".join(problems)


def test_committed_data_files_are_declared_and_embeddable() -> None:
    corpus = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    declared = tomllib.loads(DATA_MANIFEST.read_text(encoding="utf-8")).get("file", [])
    problems = data_file_problems(ROOT, corpus, declared)
    assert not problems, "\n".join(problems)


def test_schema_checks_catch_bad_entries() -> None:
    good = {k: "" for k in KEYS} | {"id": "a", "sha256": "0" * 64, "embeddable": False, "uses": []}
    assert manifest_problems([good]) == []
    assert manifest_problems([{**good, "sha256": "xyz"}]) == ["a: sha256 must be 64 lowercase hex digits"]
    assert manifest_problems([{k: v for k, v in good.items() if k != "sha256"}]) == ["a: missing ['sha256']"]
    share_alike = {**good, "license": "CC-BY-SA-4.0", "embeddable": True}
    assert manifest_problems([share_alike]) == ["a: embeddable requires license in ['CC0-1.0']"]


def test_share_alike_copy_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "tests" / "data").mkdir(parents=True)
    (tmp_path / "tests" / "data" / "board.kicad_pcb").write_text("(kicad_pcb)")
    corpus = [{"id": "demo", "embeddable": False}]
    declared = [{"path": "tests/data/board.kicad_pcb", "origin": "corpus", "corpus_id": "demo"}]
    assert data_file_problems(tmp_path, corpus, declared) == [
        "tests/data/board.kicad_pcb: corpus item 'demo' is not embeddable"
    ]
    declared = [{"path": "tests/data/board.kicad_pcb", "origin": "authored"}]
    assert data_file_problems(tmp_path, corpus, declared) == []


@pytest.mark.parametrize("good_hash", [True, False])
def test_fetch_verifies_hash(tmp_path: Path, good_hash: bool) -> None:
    tool = _load_tool()
    source = tmp_path / "src" / "demo.kicad_pcb"
    source.parent.mkdir()
    source.write_bytes(b"(kicad_pcb (version 20260206))\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest() if good_hash else "0" * 64
    manifest = tmp_path / "manifest.toml"
    manifest.write_text(
        f'[[file]]\nid = "demo"\nurl = "{source.as_uri()}"\nref = "x"\nsha256 = "{digest}"\n'
        'license = "CC0-1.0"\nlicense_variant = ""\nembeddable = true\nuses = ["test"]\nnotes = ""\n'
    )
    cache = tmp_path / "cache"
    code = tool.main(["--manifest", str(manifest), "--cache", str(cache)])
    cached_file = cache / "demo" / "demo.kicad_pcb"
    assert code == (0 if good_hash else 1)
    assert cached_file.is_file() is good_hash
    if good_hash:  # second run is served from the cache
        assert tool.fetch(tool.load_manifest(manifest), cache)[1] == ["demo"]
