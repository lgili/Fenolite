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
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
DATA_MANIFEST = ROOT / "tests" / "data" / "MANIFEST.toml"
EMBEDDABLE_LICENSES = {"CC0-1.0"}
KEYS = {"id", "url", "ref", "sha256", "license", "license_variant", "embeddable", "uses", "notes"}
RT0_ID = re.compile(r"^(kicad-demo-\d+(-\d+){2,3}|third-party)-(pcb|sch|sym|mod|fplib|wks)-\d{2,3}$")
ORIGINS = {"origin:kicad-demos", "origin:third-party"}
PROJECT_ID = re.compile(r"^kicad-demo-\d+(-\d+){2,3}-(pro|dru)-\d{2}$")
ALTIUM_ID = re.compile(
    r"^altium-third-party-(schdoc|schlib|pcbdoc|pcblib|prjpcb|outjob|harness|rules|stackup|schdot)-\d{2}$"
)
ALTIUM_NOTE = re.compile(
    r"^S-\d{4}; (schdoc|schlib|pcbdoc|pcblib|prjpcb|outjob|harness|rules|stackup|schdot); \d+ bytes; \d{4}\.$"
)
ALTIUM_FORBIDDEN_USES = {"rt0", "malformed", "project"}
ALTIUM_TAG_KINDS = {"altium-sch": ("schdoc", "schdot"), "altium-schlib": ("schlib",)}
"""The tags of the schematic reader (change c0040) and the id kinds each allows."""
ALTIUM_TAG_NAMES = {"altium-sch": "schematic", "altium-schlib": "library"}
NON_COMMERCIAL = re.compile(r"\bNC\b|-NC-|non-?commercial", re.IGNORECASE)
HEAVY_BYTES = 20 * 1024 * 1024


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fenolite_corpus_fetch", ROOT / "tools" / "corpus_fetch.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RT2_9 = "rt2-9"
RT2_9_REF = "9.0.9.1"
"""The use that the ``kicad-9`` job fetches: the readable non-heavy board rows at this tag (c0020)."""


LIBS = "libs"
"""The use of a demo ``fp-lib-table`` and of the footprint files its boards place (c0021)."""


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
        if "altium" in uses:
            if not ALTIUM_ID.fullmatch(ident):
                problems.append(f"{ident}: altium ids must match {ALTIUM_ID.pattern}")
            ref = str(entry["ref"])
            if not re.fullmatch(r"[0-9a-f]{40}", ref) or ref not in str(entry["url"]):
                problems.append(f"{ident}: altium rows need a 40-digit commit that the url contains")
            if entry["embeddable"] is not False:
                problems.append(f"{ident}: altium rows must have embeddable = false")
            for required in ("origin:third-party",):
                if required not in uses:
                    problems.append(f"{ident}: altium rows need {required} in uses")
            for forbidden in sorted(ALTIUM_FORBIDDEN_USES & set(uses)):
                problems.append(f"{ident}: altium rows cannot carry {forbidden} in uses")
            if "altium-text" in uses and "cfb" in uses:
                problems.append(f"{ident}: an altium-text row is a text file and cannot carry cfb")
            if not ALTIUM_NOTE.fullmatch(str(entry["notes"])):
                problems.append(
                    f"{ident}: altium notes must contain only source id, kind, byte size and save year"
                )
        if "rt0" in uses and "malformed" in uses:
            problems.append(f"{ident}: a malformed row cannot carry rt0")
        if "rt0" in uses or "malformed" in uses:
            if not RT0_ID.fullmatch(ident):
                problems.append(f"{ident}: rt0 ids must match {RT0_ID.pattern}")
            origins = [u for u in uses if u.startswith("origin:")]
            if len(origins) != 1 or origins[0] not in ORIGINS:
                problems.append(f"{ident}: rt0 rows need exactly one of {sorted(ORIGINS)} in uses")
        wanted = (
            entry["ref"] == RT2_9_REF
            and urlparse(str(entry["url"])).path.endswith(".kicad_pcb")
            and "rt0" in uses
            and "heavy" not in uses
        )
        if (RT2_9 in uses) != wanted:
            state = "carries" if RT2_9 in uses else "lacks"
            problems.append(
                f"{ident}: {state} the use {RT2_9}, which marks exactly the non-heavy rt0 boards at "
                f"ref {RT2_9_REF}"
            )
        if LIBS in uses:
            for use in ("rt0", "origin:kicad-demos"):
                if use not in uses:
                    problems.append(f"{ident}: a {LIBS} row needs {use} in uses")
        if "project" in uses:
            if not PROJECT_ID.fullmatch(ident):
                problems.append(f"{ident}: project ids must match {PROJECT_ID.pattern}")
            for use in ("rt0", "oracle", "malformed"):
                if use in uses:
                    problems.append(f"{ident}: project rows never carry {use}")
            if "origin:kicad-demos" not in uses:
                problems.append(f"{ident}: project rows need origin:kicad-demos in uses")
    return problems + altium_tag_problems(entries)


def _repository(url: str) -> tuple[str, ...]:
    """The host and the first two path segments of ``url``, which name a repository."""
    parsed = urlparse(url)
    return (parsed.netloc, *[part for part in parsed.path.split("/") if part][:2])


def altium_tag_problems(entries: list[dict[str, Any]]) -> list[str]:
    """The rules of "Altium schematic corpus rows" (change c0040): a row with ``altium-sch`` or
    ``altium-schlib`` holds ``altium``, has an id of the kinds the tag allows, never holds both tags, and
    each tag that occurs covers three repositories."""
    problems: list[str] = []
    repositories: dict[str, set[tuple[str, ...]]] = {tag: set() for tag in ALTIUM_TAG_KINDS}
    for entry in entries:
        if not KEYS <= entry.keys():
            continue
        ident = str(entry["id"])
        uses = set(entry["uses"])
        tags = sorted(uses & ALTIUM_TAG_KINDS.keys())
        if len(tags) > 1:
            problems.append(f"{ident}: a row cannot carry both {' and '.join(tags)}")
        for tag in tags:
            if "altium" not in uses:
                problems.append(f"{ident}: a row with {tag} needs altium in uses")
            match = ALTIUM_ID.fullmatch(ident)
            kinds = ALTIUM_TAG_KINDS[tag]
            if match is None or match.group(1) not in kinds:
                problems.append(f"{ident}: {tag} rows must have an id of kind {' or '.join(kinds)}")
            repositories[tag].add(_repository(str(entry["url"])))
    for tag, found in repositories.items():
        if found and len(found) < 3:
            problems.append(
                f"{tag}: {ALTIUM_TAG_NAMES[tag]} rows need three repositories, found {len(found)}"
            )
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


def test_altium_census_rows() -> None:
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    rows = [entry for entry in entries if {"altium", "cfb"} <= set(entry["uses"])]
    assert len(rows) == 10
    assert {str(entry["id"]) for entry in rows} == {
        *(f"altium-third-party-pcbdoc-{i:02}" for i in range(1, 5)),
        *(f"altium-third-party-pcblib-{i:02}" for i in range(1, 3)),
        *(f"altium-third-party-schdoc-{i:02}" for i in range(1, 5)),
    }
    repos = {urlparse(str(entry["url"])).path.split("/")[1] for entry in rows}
    assert len(repos) >= 3
    assert all(entry["embeddable"] is False for entry in rows)


def test_altium_text_rows() -> None:
    """Change c0042: twelve text files (project files, output jobs, rule files, stack-up files), each with
    ``altium``, ``altium-text`` and ``origin:third-party`` and without ``cfb`` or ``rt0``."""
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    rows = [entry for entry in entries if "altium-text" in entry["uses"]]
    kinds = ("prjpcb", "outjob", "rules", "stackup")
    assert {str(entry["id"]) for entry in rows} == {
        f"altium-third-party-{kind}-{i:02}" for kind in kinds for i in range(1, 4)
    }
    for entry in rows:
        uses = set(entry["uses"])
        assert {"altium", "origin:third-party"} <= uses and not uses & {"cfb", "rt0"}, entry["id"]
        assert entry["embeddable"] is False and entry["license"] in ("MIT", "LGPL-3.0"), entry["id"]
    assert manifest_problems(rows) == []
    for kind in ("prjpcb", "outjob"):
        repos = {urlparse(str(e["url"])).path.split("/")[1] for e in rows if f"-{kind}-" in str(e["id"])}
        assert len(repos) == 3, kind


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


def _altium_row(**overrides: Any) -> dict[str, Any]:
    return (
        _row(
            id="altium-third-party-schdoc-01",
            url="https://example.invalid/repo/" + "a" * 40 + "/file.SchDoc",
            ref="a" * 40,
            embeddable=False,
            uses=["altium", "cfb", "origin:third-party"],
            notes="S-0188; schdoc; 23040 bytes; 2016.",
        )
        | overrides
    )


def test_altium_rules_reject_bad_rows() -> None:
    assert "altium ids must match" in "\n".join(
        manifest_problems([_altium_row(id="altium-third-party-battman-01")])
    )
    assert "40-digit commit" in "\n".join(manifest_problems([_altium_row(ref="master")]))
    assert "cannot carry rt0" in "\n".join(
        manifest_problems([_altium_row(uses=["altium", "cfb", "origin:third-party", "rt0"])])
    )
    assert "cannot carry cfb" in "\n".join(
        manifest_problems([_altium_row(uses=["altium", "altium-text", "cfb", "origin:third-party"])])
    )


def _sch_rows(tag: str, kind: str, repositories: int) -> list[dict[str, Any]]:
    return [
        _altium_row(
            id=f"altium-third-party-{kind}-{n:02}",
            url=f"https://example.invalid/owner{n % repositories}/repo/" + "a" * 40 + f"/f{n}",
            uses=["altium", "origin:third-party", tag],
            notes=f"S-0277; {kind}; 10 bytes; 2019.",
        )
        for n in range(1, 4)
    ]


def test_schematic_reader_rows_pass() -> None:
    assert altium_tag_problems(_sch_rows("altium-sch", "schdoc", 3)) == []
    assert altium_tag_problems(_sch_rows("altium-schlib", "schlib", 3)) == []
    assert manifest_problems(_sch_rows("altium-schlib", "schlib", 3)) == []


def test_tag_on_the_wrong_kind() -> None:
    rows = _sch_rows("altium-schlib", "schlib", 3)
    rows[0] = rows[0] | {"id": "altium-third-party-pcblib-01"}
    (problem,) = altium_tag_problems(rows)
    assert problem == "altium-third-party-pcblib-01: altium-schlib rows must have an id of kind schlib"
    rows = _sch_rows("altium-sch", "schlib", 3)
    assert "altium-third-party-schlib-01: altium-sch rows must have an id of kind schdoc or schdot" in (
        altium_tag_problems(rows)
    )


def test_tag_without_the_family_use() -> None:
    rows = _sch_rows("altium-sch", "schdoc", 3)
    rows[1] = rows[1] | {"uses": ["altium-sch", "origin:third-party"]}
    (problem,) = altium_tag_problems(rows)
    assert problem == "altium-third-party-schdoc-02: a row with altium-sch needs altium in uses"


def test_two_repositories_only() -> None:
    (problem,) = altium_tag_problems(_sch_rows("altium-schlib", "schlib", 2))
    assert problem == "altium-schlib: library rows need three repositories, found 2"
    (problem,) = altium_tag_problems(_sch_rows("altium-sch", "schdoc", 2))
    assert problem == "altium-sch: schematic rows need three repositories, found 2"


def test_both_tags_refused() -> None:
    rows = _sch_rows("altium-sch", "schdoc", 3)
    rows[0] = rows[0] | {"uses": ["altium", "origin:third-party", "altium-sch", "altium-schlib"]}
    assert "altium-third-party-schdoc-01: a row cannot carry both altium-sch and altium-schlib" in (
        altium_tag_problems(rows)
    )


def test_schematic_reader_rows() -> None:
    """The live rows of changes c0039 and c0040: 13 schematic documents and 9 libraries, three repositories
    each, the four rows of c0039 tagged too, and no URL listed twice."""
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    sch = [e for e in entries if "altium-sch" in e["uses"]]
    lib = [e for e in entries if "altium-schlib" in e["uses"]]
    assert {str(e["id"]) for e in sch} >= {f"altium-third-party-schdoc-{n:02}" for n in range(1, 14)}
    assert {str(e["id"]) for e in lib} >= {f"altium-third-party-schlib-{n:02}" for n in range(1, 10)}
    assert len({_repository(str(e["url"])) for e in sch}) >= 3
    assert len({_repository(str(e["url"])) for e in lib}) >= 3
    urls = [str(e["url"]) for e in entries]
    assert len(urls) == len(set(urls))


def test_malformed_rows() -> None:
    assert manifest_problems([_row(uses=["malformed", "origin:kicad-demos"])]) == []
    assert manifest_problems([_row(uses=["rt0", "malformed", "origin:kicad-demos"])]) == [
        "kicad-demo-10-0-6-pcb-01: a malformed row cannot carry rt0"
    ]


def test_library_rows_need_rt0_and_the_demo_origin() -> None:
    good = _row(id="kicad-demo-10-0-6-mod-02", uses=["rt0", "libs", "origin:kicad-demos"])
    assert manifest_problems([good]) == []
    assert manifest_problems([good | {"uses": ["libs", "origin:kicad-demos"]}]) == [
        "kicad-demo-10-0-6-mod-02: a libs row needs rt0 in uses"
    ]
    third = good | {"id": "third-party-mod-01", "uses": ["rt0", "libs", "origin:third-party"]}
    assert manifest_problems([third]) == ["third-party-mod-01: a libs row needs origin:kicad-demos in uses"]


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


# --- project fixtures saved by the KiCad GUI (c0010) ----------------------------------------------

PROJECT_FIXTURES = "tests/data/kicad/project/"
VERSION_NOTE = re.compile(r"\b(9|10)\.\d+\.\d+\b")
SHA_NOTE = re.compile(r"\b[0-9a-f]{64}\b")
ABSOLUTE = re.compile(r"^(/|~/|[A-Za-z]:[\\/])")


def project_fixture_problems(root: Path, declared: list[dict[str, Any]]) -> list[str]:
    """Notes name a KiCad version and the file's SHA-256; no JSON string is an absolute path."""
    import json

    problems: list[str] = []
    for decl in declared:
        rel = str(decl.get("path", ""))
        if not rel.startswith(PROJECT_FIXTURES):
            continue
        notes = str(decl.get("notes", ""))
        if not VERSION_NOTE.search(notes):
            problems.append(f"{rel}: the notes name no KiCad version")
        path = root / rel
        if not path.is_file():
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        noted = SHA_NOTE.findall(notes)
        if noted != [actual]:
            problems.append(f"{rel}: notes SHA-256 {noted or 'none'} differs from the file's {actual}")

        def walk(value: Any, pointer: str, rel: str = rel) -> None:
            if isinstance(value, dict):
                for key, item in value.items():  # type: ignore[union-attr]
                    walk(item, f"{pointer}/{key}", rel)
            elif isinstance(value, list):
                for index, item in enumerate(value):  # type: ignore[arg-type]
                    walk(item, f"{pointer}/{index}", rel)
            elif isinstance(value, str) and ABSOLUTE.match(value):
                problems.append(f"{rel}: absolute path at {pointer}")

        walk(json.loads(path.read_text(encoding="utf-8")), "")
    return problems


def test_project_fixtures() -> None:
    declared = tomllib.loads(DATA_MANIFEST.read_text(encoding="utf-8")).get("file", [])
    assert project_fixture_problems(ROOT, declared) == []
    assert any(str(d["path"]).startswith(PROJECT_FIXTURES) for d in declared)


def _fixture(tmp_path: Path, body: str, notes: str | None = None) -> list[str]:
    path = tmp_path / "tests" / "data" / "kicad" / "project" / "empty_10.kicad_pro"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    entry = {"path": "tests/data/kicad/project/empty_10.kicad_pro", "notes": notes or f"KiCad 10.0.6, {sha}"}
    return project_fixture_problems(tmp_path, [entry])


def test_absolute_path_in_a_fixture(tmp_path: Path) -> None:
    problems = _fixture(tmp_path, '{"schematic": {"plot_directory": "/tmp/out/"}, "a": "~A", "b": "C:\\\\x"}')
    assert problems == [
        "tests/data/kicad/project/empty_10.kicad_pro: absolute path at /schematic/plot_directory",
        "tests/data/kicad/project/empty_10.kicad_pro: absolute path at /b",
    ]


def test_fixture_edited_after_the_save(tmp_path: Path) -> None:
    problems = _fixture(tmp_path, "{}", notes="KiCad 10.0.6, " + "0" * 64)
    assert len(problems) == 1 and "0" * 64 in problems[0] and "differs" in problems[0]


def test_notes_without_a_version(tmp_path: Path) -> None:
    sha = hashlib.sha256(b"{}").hexdigest()
    problems = _fixture(tmp_path, "{}", notes=f"saved by KiCad, {sha}")
    assert problems == ["tests/data/kicad/project/empty_10.kicad_pro: the notes name no KiCad version"]


def _project_row(ident: str, uses: list[str]) -> dict[str, Any]:
    return {
        "id": ident, "url": "https://example.org/x.kicad_pro", "ref": "10.0.6", "sha256": "0" * 64,
        "license": "CC-BY-SA-4.0", "license_variant": "", "embeddable": False, "uses": uses, "notes": "",
    }  # fmt: skip


def test_project_rows() -> None:
    good = _project_row("kicad-demo-10-0-6-pro-01", ["project", "origin:kicad-demos"])
    assert manifest_problems([good]) == []
    named = _project_row("kicad-demo-10-0-6-cm5-minima", ["project", "origin:kicad-demos"])
    assert manifest_problems([named]) == [
        f"kicad-demo-10-0-6-cm5-minima: project ids must match {PROJECT_ID.pattern}"
    ]
    tagged = _project_row("kicad-demo-10-0-6-pro-01", ["project", "rt0", "origin:kicad-demos"])
    assert "kicad-demo-10-0-6-pro-01: project rows never carry rt0" in manifest_problems([tagged])
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    rows = [e for e in entries if "project" in e["uses"]]
    assert rows and all(not e["embeddable"] for e in rows)
    assert not any("stickhub" in e["url"] for e in rows)


# -- rt2-9 rows (c0020; capability corpus-policy, "RT2 rows for KiCad 9.0")


def _board_row(ident: str, ref: str, uses: list[str]) -> dict[str, Any]:
    return _row(id=ident, ref=ref, url=f"https://example.org/{ident}.kicad_pcb", uses=uses)


def test_rt2_9_rows_of_the_committed_manifest() -> None:
    tagged = sorted(e["id"] for e in _load_tool().load_manifest(MANIFEST) if RT2_9 in e["uses"])
    assert tagged == [f"kicad-demo-9-0-9-1-pcb-0{n}" for n in (1, 2, 3, 5, 6)]


def test_rt2_9_wrong_row_tagged() -> None:
    row = _board_row("kicad-demo-10-0-6-pcb-01", "10.0.6", ["rt0", "oracle", "origin:kicad-demos", RT2_9])
    (problem,) = manifest_problems([row])
    assert "kicad-demo-10-0-6-pcb-01" in problem and "carries the use rt2-9" in problem


def test_rt2_9_tag_missing() -> None:
    row = _board_row("kicad-demo-9-0-9-1-pcb-03", RT2_9_REF, ["rt0", "oracle", "origin:kicad-demos"])
    (problem,) = manifest_problems([row])
    assert "kicad-demo-9-0-9-1-pcb-03" in problem and "lacks the use rt2-9" in problem
    tagged = _board_row(
        "kicad-demo-9-0-9-1-pcb-03", RT2_9_REF, ["rt0", "oracle", "origin:kicad-demos", RT2_9]
    )
    assert manifest_problems([tagged]) == []


def test_rt2_9_never_on_malformed_or_heavy_rows() -> None:
    malformed = _board_row("kicad-demo-9-0-9-1-pcb-04", RT2_9_REF, ["malformed", "origin:kicad-demos"])
    heavy = _board_row("kicad-demo-9-0-9-1-pcb-07", RT2_9_REF, ["rt0", "heavy", "origin:kicad-demos"])
    assert manifest_problems([malformed, heavy]) == []
    assert len(manifest_problems([malformed | {"uses": [*malformed["uses"], RT2_9]}])) == 1


def test_fetch_by_use(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    tool = _load_tool()
    manifest = _manifest(tmp_path, [("a", "a.kicad_pcb", ["rt0"]), ("b", "b.kicad_pcb", ["rt0", RT2_9])])
    cache = tmp_path / "cache"
    assert tool.main(["--manifest", str(manifest), "--cache", str(cache), "--uses", RT2_9]) == 0
    assert sorted(p.name for p in cache.iterdir()) == ["b"]
    assert "1 item(s)" in capsys.readouterr().out
