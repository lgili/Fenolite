# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the stack-up nodes of the readable corpus boards (capability kicad-file-backend, "Stack-up
on boards", scenario "Corpus census"; change c0101): every board whose ``setup`` holds a node gets a
stack-up, and the counts go to ``docs/evidence/kicad-stackup.md`` (``FENOLITE_CENSUS_OUT`` writes them).
Items are named by their manifest id only."""

from __future__ import annotations

from collections import Counter

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import census
from _corpus import CorpusItem, require

from fenolite.backends.kicad.sexpr import parse

pytestmark = pytest.mark.needs_corpus
SEEN: dict[str, dict[str, object]] = {}


@pytest.mark.parametrize("item", READABLE_ITEMS, ids=lambda i: i.id)
def test_node_gives_a_stackup(item: CorpusItem) -> None:
    path = require(item)
    design, issues = read(path)
    assert design.board is not None
    setup = parse(path.read_bytes().decode("utf-8")).find("setup")
    node = setup.find("stackup") if setup is not None else None
    codes = sorted(i.code for i in issues if i.code.startswith("kicad.board.stackup-"))
    found = design.board.stackup
    if node is None:
        assert found is None and codes == [], item.id
        SEEN[item.id] = {"node": False}
        return
    assert found is not None, f"{item.id}: {codes}"
    assert not [c for c in codes if c != "kicad.board.stackup-thickness"], item.id
    assert not [i for i in design.validate() if i.code.startswith("model.stackup-")], item.id
    kinds = Counter(e.kind for e in found.layers)
    SEEN[item.id] = {
        "node": True,
        "copper": kinds["copper"],
        "entries": len(found.layers),
        "dielectric_kinds": Counter(str(e.dielectric_kind) for e in found.layers if e.kind == "dielectric"),
        "sheets": kinds["dielectric"] - (kinds["copper"] - 1),
        "finish": found.finish or "None",
        "impedance_controlled": found.impedance_controlled,
        "thickness_warning": "kicad.board.stackup-thickness" in codes,
        "loss_tangent_zero": sum(1 for e in found.layers if e.loss_tangent == "0"),
    }


def test_census_summary() -> None:
    if not SEEN:
        pytest.skip("no board was read in this session")
    with_node = [v for v in SEEN.values() if v["node"]]
    kinds: Counter[str] = Counter()
    for entry in with_node:
        kinds.update(entry["dielectric_kinds"])  # type: ignore[arg-type]
    summary = {
        "boards": len(SEEN),
        "with_node": len(with_node),
        "projected": len(with_node),
        "by_copper": dict(sorted(Counter(str(v["copper"]) for v in with_node).items())),
        "entries": sum(int(v["entries"]) for v in with_node),  # type: ignore[call-overload]
        "dielectric_kinds": dict(sorted(kinds.items())),
        "extra_sheets": sum(int(v["sheets"]) for v in with_node),  # type: ignore[call-overload]
        "finish": dict(sorted(Counter(str(v["finish"]) for v in with_node).items())),
        "impedance_controlled": sum(1 for v in with_node if v["impedance_controlled"]),
        "thickness_warning": sum(1 for v in with_node if v["thickness_warning"]),
        "loss_tangent_zero": sum(int(v["loss_tangent_zero"]) for v in with_node),  # type: ignore[call-overload]
    }
    census("stackup", "summary", summary)
    print(f"stack-up census: {summary}")
    assert summary["with_node"] > 0
