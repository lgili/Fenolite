# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT0 over the public corpus, number census and slot identity (capabilities kicad-sexpr, kicad-slots).

Items are named by their neutral manifest id only.
"""

from __future__ import annotations

import random
import re
import tomllib
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence

import pytest
from _corpus import MANIFEST, CorpusItem, manifest_items, require

from fenolite.backends.kicad import (
    Atom,
    AtomKind,
    Node,
    dumps,
    first_difference,
    load,
    parse,
    tree_equal,
    walk,
)
from fenolite.backends.kicad.slots import rebuild, split
from fenolite.core.errors import FormatError

pytestmark = pytest.mark.needs_corpus
ITEMS = manifest_items("rt0")
PASSED: dict[str, list[str]] = defaultdict(list)

# Independent of sexpr.py: parentheses, quoted strings (escapes skipped pairwise) and bare atoms.
_TOKENS = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^ \t\r\n()"][^ \t\r\n()]*')


def tokens(text: str) -> list[str]:
    return _TOKENS.findall(text)


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_rt0(item: CorpusItem) -> None:
    path = require(item)
    original = load(path)
    text = dumps(original)
    again = parse(text)
    assert tree_equal(again, original), f"{item.id}: first difference at {first_difference(again, original)}"
    source = path.read_bytes().decode("utf-8")
    assert tokens(source) == tokens(text), f"{item.id}: token streams differ"
    PASSED[item.origin].append(item.id)


@pytest.mark.parametrize("item", manifest_items("malformed"), ids=lambda i: i.id)
def test_malformed_items_rejected(item: CorpusItem) -> None:
    """Files published malformed stay rejected, with the rule their manifest notes name."""
    if not item.path.is_file():
        pytest.skip(f"{item.id} not cached (fetch with --uses malformed)")
    notes = {row["id"]: row["notes"] for row in tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]}
    with pytest.raises(FormatError) as info:
        load(item.path)
    assert info.value.message in notes[item.id], f"{item.id}: rejected with {info.value.message!r}"


def test_rt0_summary() -> None:
    if not PASSED:
        pytest.skip("no RT0 item ran in this session")
    summary = ", ".join(f"{origin}: {len(ids)}" for origin, ids in sorted(PASSED.items()))
    print(f"RT0 passed per origin: {summary}")
    if len(PASSED) < 2:
        print("only one origin passed: the parser cannot be labelled CORPUS-VERIFIED from this run")


def _numbers(node: Node) -> Iterable[Atom]:
    for _, current in walk(node):
        for atom in (current.head, *current.atoms()):
            if atom.kind == AtomKind.NUMBER:
                yield atom


def test_number_census() -> None:
    """H-K-SEXPR-NUM-CORPUS: exponent atoms and atoms with more than 6 decimals, per origin and version."""
    exponent: Counter[tuple[str, str]] = Counter()
    precise: Counter[tuple[str, str]] = Counter()
    seen: Counter[tuple[str, str]] = Counter()
    for item in ITEMS:
        if item.heavy or not item.path.is_file():
            continue
        root = load(item.path)
        version_node = root.find("version")
        version = version_node.atoms()[0].text if version_node and version_node.atoms() else "none"
        key = (item.origin, version)
        seen[key] += 1
        for atom in _numbers(root):
            mantissa = re.split(r"[eE]", atom.text)[0]
            if "e" in atom.text.lower():
                exponent[key] += 1
            if "." in mantissa and len(mantissa.split(".")[1]) > 6:
                precise[key] += 1
    if not seen:
        pytest.skip("no corpus item cached")
    for key in sorted(seen):
        print(f"{key[0]} format {key[1]}: {seen[key]} file(s), exponent atoms {exponent[key]}, "
              f">6 decimals {precise[key]}")  # fmt: skip


class _Original:
    def __init__(self, node: Node, fields: dict[str, str], positional: Sequence[str]) -> None:
        self.by_field: dict[str, list[Node | Atom]] = defaultdict(list)
        leading, seen_list = 0, False
        for child in node.children:
            if isinstance(child, Node):
                seen_list = True
                if child.head.text in fields:
                    self.by_field[fields[child.head.text]].append(child)
            elif not seen_list and leading < len(positional):
                self.by_field[positional[leading]].append(child)
                leading += 1

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self.by_field.get(field, [])

    def fields(self) -> Iterable[str]:
        return [f for f, items in self.by_field.items() if items]


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_slot_identity(item: CorpusItem) -> None:
    root = load(require(item))
    for locator, node in walk(root):
        rng = random.Random(f"{item.id}:{locator}")
        heads = sorted({c.head.text for c in node.children if isinstance(c, Node)})
        subset = [h for h in heads if rng.random() < 0.5]
        leading = next((i for i, c in enumerate(node.children) if isinstance(c, Node)), len(node.children))
        positional = tuple(f"p{i}" for i in range(rng.randint(0, leading)))
        fields = {h: f"f:{h}" for h in subset}
        slots = split(node, fields, positional=positional, min_version="1")
        rebuilt = rebuild(node.head, slots, _Original(node, fields, positional))
        assert tree_equal(rebuilt, node), (
            f"{item.id}: slot identity failed at {locator} with subset {subset}, {len(positional)} positional"
        )
