# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Head chains that ``kicad-cli`` 10.0.6 writes against those that 9.0 wrote (capability
kicad-token-inventory, "Observed board paths are inventoried"; ``H-K-TOK-CENSUS``; change c0020).

An unmatched board path counts as a floor token, so a chain that only 10.0 writes must be accounted for:
by a token row of its own, by a 10.0 row of one of its ancestors (the writer gates the parent, children
included), by a ``FLOOR_CHAINS`` entry backed by an inventory example that loads on 9.0.9, or by a
``PENDING_CHAINS`` entry that names who resolves it. Only counts and head names are recorded.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import pytest
from _boardcorpus import OLD_ITEMS, READABLE_ITEMS
from _boards import census
from _corpus import CorpusItem
from _upgrade import upgraded

from fenolite.backends.kicad import versions
from fenolite.backends.kicad.sexpr import Node, load, parse

Chain = tuple[str, ...]
FLOOR_CHAINS: Mapping[str, str] = {}
"""``chain → inventory example`` whose committed fuzz results load on 9.0.9. None yet: the suspects that
are floor tokens wait in ``PENDING_CHAINS`` for an example each."""
VOCABULARY = "v0.5a exhaustive 8.0 vocabulary: an inventory example that loads on 9.0.9"
TUNING = "next token inventory change: rows for the tuning-pattern tokens that 10.0 writes"
PENDING_CHAINS: Mapping[str, str] = {
    "kicad_pcb/footprint/dimension/format/suppress_zeroes": VOCABULARY,
    "kicad_pcb/footprint/dimension/height": VOCABULARY,
    "kicad_pcb/footprint/dimension/orientation": VOCABULARY,
    "kicad_pcb/footprint/dimension/style/extension_height": VOCABULARY,
    "kicad_pcb/footprint/fp_text/effects/font/bold": VOCABULARY,
    "kicad_pcb/footprint/solder_mask_margin": VOCABULARY,
    "kicad_pcb/footprint/solder_paste_margin": VOCABULARY,
    "kicad_pcb/footprint/zone/fill/island_removal_mode": VOCABULARY,
    "kicad_pcb/gr_text/effects/font/italic": VOCABULARY,
    "kicad_pcb/zone/fill/radius": VOCABULARY,
    "kicad_pcb/zone/fill/smoothing": VOCABULARY,
    "kicad_pcb/zone/filled_polygon/island": VOCABULARY,
    "kicad_pcb/zone/locked": VOCABULARY,
    "kicad_pcb/generated/base_line_coupled": TUNING,
    "kicad_pcb/generated/base_line_coupled/pts": TUNING,
    "kicad_pcb/generated/base_line_coupled/pts/xy": TUNING,
    "kicad_pcb/generated/is_time_domain": TUNING,
    "kicad_pcb/generated/last_tuning_length": TUNING,
    "kicad_pcb/generated/target_delay": TUNING,
    "kicad_pcb/generated/target_delay_max": TUNING,
    "kicad_pcb/generated/target_delay_min": TUNING,
}
"""First-run suspects that need a row or an example, each with the change that resolves it. While this is
not empty, ``H-K-TOK-CENSUS`` stays ``INFERRED``."""
NINE_HEADER = ("(version 20241229)", '(generator_version "9.0")')


def chains(root: Node) -> set[Chain]:
    """Every list of heads from the root to a node, numeric heads read as ``#`` (``Inventory.match``)."""
    found: set[Chain] = set()

    def visit(node: Node, prefix: Chain) -> None:
        chain = (*prefix, "#" if node.name.isdigit() else node.name)
        found.add(chain)
        for child in node.children:
            if isinstance(child, Node):
                visit(child, chain)

    visit(root, ())
    return found


def resolution(chain: Chain, inventory: versions.Inventory) -> str:
    """``row``, ``ancestor``, ``floor``, ``pending`` or ``unresolved`` for a suspect chain."""
    board = versions.FileKind.BOARD
    if inventory.match(board, chain) is not None:
        return "row"
    for length in range(len(chain) - 1, 1, -1):
        row = inventory.match(board, chain[:length])
        if row is not None and row.since_major >= 10:
            return "ancestor"
    name = "/".join(chain)
    if name in FLOOR_CHAINS:
        return "floor"
    return "pending" if name in PENDING_CHAINS else "unresolved"


def token_census(written_10: Iterable[Node], written_9: Iterable[Node]) -> dict[str, object]:
    """The counts of the census and the suspects that nothing accounts for."""
    ten: set[Chain] = set()
    for root in written_10:
        ten |= chains(root)
    nine: set[Chain] = set()
    for root in written_9:
        nine |= chains(root)
    inventory = versions.load_inventory()
    suspects = sorted(ten - nine)
    resolved = {chain: resolution(chain, inventory) for chain in suspects}
    counts = {kind: sum(1 for r in resolved.values() if r == kind) for kind in ("row", "ancestor", "floor")}
    return {
        "chains_10": len(ten),
        "chains_9": len(nine),
        "suspects": len(suspects),
        **counts,
        "pending": sorted("/".join(c) for c, r in resolved.items() if r == "pending"),
        "unresolved": sorted("/".join(c) for c, r in resolved.items() if r == "unresolved"),
    }


def _nine_written(item: CorpusItem) -> bool:
    head = item.path.read_text(encoding="utf-8")[:300]
    return all(marker in head for marker in NINE_HEADER)


def _ten_native(item: CorpusItem) -> bool:
    root = load(item.path)
    return versions.major_for(versions.FileKind.BOARD, versions.detect_version(root)) >= 10


@pytest.mark.needs_kicad
@pytest.mark.needs_corpus
@pytest.mark.kicad_min_major(10)
@pytest.mark.slow
def test_observed_paths() -> None:
    demos = [i for i in READABLE_ITEMS if not i.heavy and i.path.is_file()]
    old = [i for i in OLD_ITEMS if not i.heavy and i.path.is_file()]
    if not demos:
        pytest.skip("no demo board is cached")
    written_10 = [parse(upgraded(i.path)) for i in (*demos, *old)]
    written_10 += [load(i.path) for i in demos if _ten_native(i)]
    written_9 = [load(i.path) for i in demos if _nine_written(i)]
    found = token_census(written_10, written_9)
    census("token_census", "boards", {"upgraded": len(demos) + len(old), "nine_written": len(written_9)})
    census("token_census", "counts", found)
    assert found["unresolved"] == [], f"chains that only 10.0 writes and nothing accounts for: {found}"
    stale = sorted(set(PENDING_CHAINS) - set(found["pending"]))  # type: ignore[arg-type]
    assert not stale, f"PENDING_CHAINS entries that are no longer suspects: {stale}"


def test_suspects_detected() -> None:
    ten = parse('(kicad_pcb (version 20260206) (fenolite_probe 1) (net 0 "") (via (covering (front yes))))')
    nine = parse('(kicad_pcb (version 20241229) (net 0 "") (via))')
    found = token_census([ten], [nine])
    assert found["unresolved"] == ["kicad_pcb/fenolite_probe"]
    # the via's covering row is a 10.0 token, and its child is accounted for by that ancestor
    assert found["row"] >= 1 and found["ancestor"] == 1 and found["suspects"] >= 3
    assert token_census([nine], [nine])["suspects"] == 0


def test_numeric_heads_and_pending_owners() -> None:
    assert ("kicad_pcb", "layers", "#") in chains(parse('(kicad_pcb (layers (0 "F.Cu" signal)))'))
    assert all(owner for owner in PENDING_CHAINS.values()) and not set(FLOOR_CHAINS) & set(PENDING_CHAINS)
