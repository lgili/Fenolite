# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic reader on the public Altium corpus (capability altium-schematic-reader, "Corpus reading and
census"; corpus-policy, "Altium schematic corpus rows"). Counts and key names only; no value leaves the
cache."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tomllib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from urllib.parse import urlparse

import pytest
from _boards import census
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.read import sch, schlib
from fenolite.backends.altium.read.sch.census import LABELS
from fenolite.backends.altium.read.sch.records import LENGTH
from fenolite.core.errors import Issue

pytestmark = pytest.mark.needs_corpus
ROOT = Path(__file__).resolve().parents[2]
SCH = manifest_items("altium-sch")
LIB = manifest_items("altium-schlib")
EXPECTED: dict[tuple[str, str], str] = {}
"""``(issue code, row id)`` → the one-line reason a warning is expected. Empty: no row gives a warning."""


def _repository(url: str) -> tuple[str, ...]:
    parsed = urlparse(url)
    return (parsed.netloc, *[part for part in parsed.path.split("/") if part][:2])


def test_three_repositories_per_tag() -> None:
    manifest = tomllib.loads((ROOT / "tests" / "corpus" / "manifest.toml").read_text(encoding="utf-8"))
    rows = {row["id"]: row["url"] for row in manifest["file"]}
    for items in (SCH, LIB):
        assert len({_repository(rows[item.id]) for item in items}) >= 3


def _warnings(issues: list[Issue], ident: str) -> list[str]:
    return [
        f"{issue.code} at {issue.where}"
        for issue in issues
        if issue.severity == "warning" and (issue.code, ident) not in EXPECTED
    ]


def _check_lengths_and_text(records: Iterator[sch.SchRecord]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for record in records:
        props = record.props
        if props is None:
            continue
        for key in props.keys():
            props.text(key)  # every text view decodes without an exception
            spec = record.spec_for(key)
            if spec is None or spec.kind != LENGTH or key in record.bad_keys:
                continue
            frac_key = f"{key}_FRAC1" if key == "DISTANCEFROMTOP" else f"{key}_FRAC"
            length = sch.SchLength.of(props.int(key), props.int(frac_key))
            assert isinstance(length.nm(), int)
            counts["lengths"] += 1
    return counts


def _reached_once(roots: tuple[sch.RecordRef, ...], walk: object, total: int) -> None:
    seen: list[sch.RecordRef] = []
    for root in roots:
        seen.extend(record.ref for record in walk(root))  # type: ignore[operator]
    assert len(seen) == len(set(seen)) == total


@pytest.mark.parametrize("item", SCH, ids=lambda item: item.id)
def test_schematic_rows(item: CorpusItem) -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(require(item).read_bytes(), file=item.id, issues=issues)
    assert sch.check_identity(document) == ()
    assert _warnings(issues, item.id) == []
    for record in document.all_records():
        owner = record.owner
        if owner is None:
            continue
        if record.ref.stream == owner.stream:
            assert owner.index < record.ref.index
        else:
            assert (record.ref.stream, owner.stream) == ("additional", "main")
    _reached_once(document.roots, lambda ref: document.walk(document.get(ref)), len(document.all_records()))
    for component in document.components():
        for child in document.children_of(component):
            assert child.owner_part <= component.part_count
            if child.owner_part != -1:
                assert child.owner_display_mode < component.display_mode_count
    for record in document.additional:
        if isinstance(record, (sch.HarnessEntry, sch.HarnessType)):
            assert isinstance(document.owner_of(record), sch.HarnessConnector)
    counts = _check_lengths_and_text(iter(document.all_records()))
    census("altium_sch_read", item.id, {"records": len(document.all_records()), **counts})


@pytest.mark.parametrize("item", LIB, ids=lambda item: item.id)
def test_library_rows(item: CorpusItem) -> None:
    issues: list[Issue] = []
    library = schlib.read_schlib(require(item).read_bytes(), file=item.id, issues=issues)
    assert sch.check_identity(library) == ()
    assert _warnings(issues, item.id) == []
    total = 0
    for component in library.components:
        assert isinstance(component.component, sch.Component)
        for record in component.records[1:]:
            assert record.owner is not None and record.owner.index < record.ref.index
            index = record.owner_index
            assert index is None or record.owner.index == index
        _reached_once((component.records[0].ref,), _component_walk(component), len(component.records))
        for child in component.children():
            assert child.owner_part <= component.part_count
            if child.owner_part != -1:
                assert child.owner_display_mode < component.display_mode_count
        total += len(component.records)
        _check_lengths_and_text(iter(component.records))
    census("altium_schlib_read", item.id, {"components": len(library.components), "records": total})


def _component_walk(component: schlib.SchLibComponent) -> object:
    def walk(ref: sch.RecordRef) -> Iterator[sch.SchRecord]:
        stack = [ref]
        while stack:
            record = component.get(stack.pop())
            yield record
            stack.extend(reversed(record.children))

    return walk


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("altium_census", ROOT / "tools" / "altium_census.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["altium_census"] = module
    spec.loader.exec_module(module)
    return module


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, inner in value.items():  # type: ignore[misc]
            yield str(key)
            yield from _strings(inner)
    elif isinstance(value, list):
        for inner in value:  # type: ignore[misc]
            yield from _strings(inner)


VOCABULARY = re.compile(
    r"^(\d+|none|binary -?\d+|[A-Z0-9_.%]+|[A-Z][A-Za-z]+|altium-third-party-[a-z]+-\d{2}|"
    r"(altium|cfb)\.[a-z.-]+|[+0-]/[+0-]|<component>/[A-Za-z]+|altium-sch|altium-schlib)$"
)
"""Key names, record ids, class names, stream names, issue codes and row ids."""
TOOL_LABELS = {"tag", "rows", "missing", "per row", "census", "identity mismatches"}


@pytest.mark.parametrize("tag", ["altium-sch", "altium-schlib"])
def test_census_vocabulary(tag: str) -> None:
    tool = _load_tool()
    rows, _ = tool.cached_rows(tag, tool.default_cache())
    if not rows:
        pytest.skip("run: uv run python tools/corpus_fetch.py")
    result = tool.census(tag, tool.default_cache())
    dumped = json.dumps(result)
    strings = set(_strings(json.loads(dumped)))
    assert (
        sorted(text for text in strings if text not in LABELS | TOOL_LABELS and not VOCABULARY.match(text))
        == []
    )
    values: set[str] = set()
    vocabulary = {cls.__name__ for cls in sch.RECORD_TYPES.values()} | {"UnknownRecord", "PropertyRecord"}
    for _, path in rows:
        data = path.read_bytes()
        reader = schlib.read_schlib if tag == "altium-schlib" else sch.read_schematic
        result_file = reader(data)
        records = (
            [record for component in result_file.components for record in component.records]  # type: ignore[union-attr]
            if tag == "altium-schlib"
            else list(result_file.all_records())  # type: ignore[union-attr]
        )
        for record in records:
            if record.props is not None:
                values.update(record.props.text(key) for key in record.props.keys())
                vocabulary.update(record.props.all_keys())
            if isinstance(record, sch.Pin) and record.binary:
                values.update((record.name, record.designator, record.description))
        if tag == "altium-schlib":
            values.update(component.storage_name for component in result_file.components)  # type: ignore[union-attr]
    # a string that is also a key name or a class name is vocabulary, whatever value happens to equal it
    leaked = [
        text for text in strings - vocabulary if text in values and not re.fullmatch(r"-?\d+|[TF]|", text)
    ]
    assert sorted(leaked) == [], "census strings that are also values of the files"


def test_ascii_form_from_corpus_records(tmp_path: Path) -> None:
    item = next(item for item in SCH if item.id == "altium-third-party-schdoc-03")
    binary = sch.read_schematic(require(item).read_bytes())
    lines = [f"|HEADER={sch.document.ASCII_HEADER}|WEIGHT={len(binary.records)}".encode()]
    lines += [record.payload[:-1] for record in binary.records]
    if binary.additional:
        lines.append(f"|HEADER={sch.document.ASCII_HEADER}|WEIGHT={len(binary.additional)}".encode())
        lines += [record.payload[:-1] for record in binary.additional]
    assert not any(b"\r" in line or b"\n" in line or line.endswith(b"|>") for line in lines)
    target = tmp_path / "rewritten.SchDoc"
    target.write_bytes(b"".join(line + b"\r\n" for line in lines))
    issues: list[Issue] = []
    rewritten = sch.read_schematic(target.read_bytes(), issues=issues)
    assert rewritten.form == "ascii"
    assert _warnings(issues, item.id) == []

    def view(records: tuple[sch.SchRecord, ...]) -> list[tuple[type, object, object, object]]:
        return [(type(r), r.props.items if r.props else None, r.owner, r.children) for r in records]

    assert view(rewritten.records) == view(binary.records)
    assert view(rewritten.additional) == view(binary.additional)
    assert sch.encode_stream(rewritten, "ascii") == target.read_bytes()
