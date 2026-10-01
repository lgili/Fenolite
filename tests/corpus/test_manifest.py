# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Corpus policy: manifest schema, embeddable rule, origins and names, declared data files, the fetch tool."""

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
RT0_ID = re.compile(r"^(kicad-demo-\d+(-\d+){2,3}|third-party)-(pcb|sch|sym|mod|fplib|wks)-\d{2}$")
ORIGINS = {"origin:kicad-demos", "origin:third-party"}
NON_COMMERCIAL = re.compile(r"\bNC\b|-NC-|non-?commercial", re.IGNORECASE)
HEAVY_BYTES = 20 * 1024 * 1024


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
        if NON_COMMERCIAL.search(f"{entry['license']} {entry['license_variant']}"):
            problems.append(f"{ident}: licences with a non-commercial clause are not allowed in the corpus")
        uses = list(entry["uses"])
        if "rt0" in uses and "malformed" in uses:
            problems.append(f"{ident}: a malformed row cannot carry rt0")
        if "rt0" in uses or "malformed" in uses:
            if not RT0_ID.fullmatch(ident):
                problems.append(f"{ident}: rt0 ids must match {RT0_ID.pattern}")
            origins = [u for u in uses if u.startswith("origin:")]
            if len(origins) != 1 or origins[0] not in ORIGINS:
                problems.append(f"{ident}: rt0 rows need exactly one of {sorted(ORIGINS)} in uses")
    return problems


def heavy_problems(entries: list[dict[str, Any]], cache: Path) -> list[str]:
    """Fetched files over 20 MB must carry the ``heavy`` use."""
    tool = _load_tool()
    problems: list[str] = []
    for entry in entries:
        path = cache / str(entry["id"]) / tool.file_name(entry)
        if path.is_file() and path.stat().st_size > HEAVY_BYTES and "heavy" not in entry["uses"]:
            problems.append(f"{entry['id']}: fetched file is over 20 MB but uses lacks 'heavy'")
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


def _row(**overrides: Any) -> dict[str, Any]:
    row = {k: "" for k in KEYS} | {
        "id": "kicad-demo-10-0-6-pcb-01",
        "sha256": "0" * 64,
        "license": "CC-BY-SA-4.0",
        "embeddable": False,
        "uses": ["rt0", "oracle", "origin:kicad-demos"],
    }
    return row | overrides


def test_demo_rules() -> None:
    assert manifest_problems([_row()]) == []
    assert manifest_problems([_row(id="third-party-pcb-01", uses=["rt0", "origin:third-party"])]) == []
    assert manifest_problems([_row(id="kicad-demo-9-0-9-1-sch-03")]) == []


def test_non_commercial_folder_excluded() -> None:
    problems = manifest_problems([_row(license_variant="CC-BY-NC-SA-4.0 with an exemption")])
    assert problems == [
        "kicad-demo-10-0-6-pcb-01: licences with a non-commercial clause are not allowed in the corpus"
    ]


def test_missing_origin() -> None:
    (problem,) = manifest_problems([_row(uses=["rt0"])])
    assert problem == (
        "kicad-demo-10-0-6-pcb-01: rt0 rows need exactly one of "
        "['origin:kicad-demos', 'origin:third-party'] in uses"
    )
    assert len(manifest_problems([_row(uses=["rt0", "origin:kicad-demos", "origin:third-party"])])) == 1


def test_named_id_rejected() -> None:
    (problem,) = manifest_problems([_row(id="kicad-demo-pic-programmer")])
    assert problem.startswith("kicad-demo-pic-programmer: rt0 ids must match ^(kicad-demo-")


def test_malformed_rows() -> None:
    assert manifest_problems([_row(uses=["malformed", "origin:kicad-demos"])]) == []
    assert manifest_problems([_row(uses=["rt0", "malformed", "origin:kicad-demos"])]) == [
        "kicad-demo-10-0-6-pcb-01: a malformed row cannot carry rt0"
    ]


def test_share_alike_demo_is_not_embeddable() -> None:
    assert manifest_problems([_row(embeddable=True)]) == [
        "kicad-demo-10-0-6-pcb-01: embeddable requires license in ['CC0-1.0']"
    ]


def test_heavy_file_untagged_detected(tmp_path: Path) -> None:
    row = _row()
    target = tmp_path / str(row["id"]) / "x.kicad_pcb"
    target.parent.mkdir(parents=True)
    with target.open("wb") as handle:
        handle.truncate(HEAVY_BYTES + 1)
    entry = row | {"url": "https://example.invalid/x.kicad_pcb"}
    assert heavy_problems([entry], tmp_path) == [
        "kicad-demo-10-0-6-pcb-01: fetched file is over 20 MB but uses lacks 'heavy'"
    ]
    assert heavy_problems([entry | {"uses": [*row["uses"], "heavy"]}], tmp_path) == []


@pytest.mark.needs_corpus
def test_heavy_files_are_tagged() -> None:
    from _resources import corpus_cache_dir

    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    problems = heavy_problems(entries, corpus_cache_dir())
    assert not problems, "\n".join(problems)


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


def _manifest(tmp_path: Path, rows: list[tuple[str, str, list[str]]]) -> Path:
    lines: list[str] = []
    for ident, source_name, uses in rows:
        source = tmp_path / "src" / source_name
        source.parent.mkdir(exist_ok=True)
        source.write_bytes(f"(kicad_pcb (version 20260206)) ; {ident}\n".encode())
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        tags = ", ".join(f'"{u}"' for u in uses)
        lines.append(
            f'[[file]]\nid = "{ident}"\nurl = "{source.as_uri()}"\nref = "x"\nsha256 = "{digest}"\n'
            f'license = "CC0-1.0"\nlicense_variant = ""\nembeddable = true\nuses = [{tags}]\nnotes = ""\n'
        )
    manifest = tmp_path / "manifest.toml"
    manifest.write_text("\n".join(lines))
    return manifest


def test_heavy_files_skipped(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tool = _load_tool()
    manifest = _manifest(
        tmp_path, [("light", "a.kicad_pcb", ["rt0"]), ("big", "b.kicad_pcb", ["rt0", "heavy"])]
    )
    cache = tmp_path / "cache"
    assert (
        tool.main(
            ["--manifest", str(manifest), "--cache", str(cache), "--uses", "rt0", "--exclude-uses", "heavy"]
        )
        == 0
    )
    assert "1 item(s)" in capsys.readouterr().out
    assert (cache / "light" / "a.kicad_pcb").is_file() and not (cache / "big").exists()


def test_encoded_space_in_a_url(tmp_path: Path) -> None:
    tool = _load_tool()
    manifest = _manifest(tmp_path, [("spaced", "demo board.kicad_pcb", ["rt0"])])
    cache = tmp_path / "cache"
    assert "%20" in manifest.read_text()
    assert tool.main(["--manifest", str(manifest), "--cache", str(cache)]) == 0
    assert (cache / "spaced" / "demo board.kicad_pcb").is_file()
