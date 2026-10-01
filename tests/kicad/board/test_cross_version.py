# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Written boards keep read content across versions (capability kicad-oracle, "Written boards keep read
content"; change c0017 Decision 23).

9 → 10 on the non-heavy major-9 demos: the target-10 text loads on 10.0.6, and the re-read equals the
source once the slots a target-10 write removes are taken out of the source (the root ``(net 0 "")``,
``(net 0)`` references, zone ``net_name`` and ``filled_areas_thickness``), apart from the board's header
bag, net numbers and the text of opaque fragments. Also the two refusals and the lossy embedding.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any

import _triad
import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import canonical
from _corpus import CorpusItem, require
from _probes import load, lossy_design, lossy_text, major, run, triad_text

from fenolite.backends.kicad.pcb import opaque_count, opaque_digests, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse_fragment, walk
from fenolite.backends.kicad.versions import (
    DowngradeRefusedError,
    FileKind,
    LegacyEditRefusedError,
    LossyWriteError,
    load_inventory,
    major_for,
)
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
DEMOS = [i for i in READABLE_ITEMS if not i.heavy]
OLD = _triad.LIBS.parents[0] / "kicad" / "tokens" / "old" / "old.kicad_pcb"


def _removed(fragment: str) -> bool:
    """Whether a target-10 write removes this whole opaque child."""
    node = parse_fragment(fragment)
    if not isinstance(node, Node):
        return False
    if node.name == "net":
        atoms = node.atoms()
        return bool(atoms) and atoms[0].text in ("0", '""')
    return node.name in ("net_name", "filled_areas_thickness")


OBSOLETE_HEADS = frozenset(r.pattern[-1] for r in load_inventory().tokens if r.until_major is not None)


def _changes_inside(fragment: str) -> bool:
    """Whether a fragment holds a ``net`` node or a node of a row target 10 no longer writes."""
    if "(net" not in fragment and not any(f"({head}" in fragment for head in OBSOLETE_HEADS):
        return False
    node = parse_fragment(fragment)
    return isinstance(node, Node) and any(
        child.name == "net" or child.name in OBSOLETE_HEADS for _, child in walk(node)
    )


def _opaque(key: str) -> bool:
    return key.startswith("slot:") and key.rpartition(":")[2].startswith("opaque")


def removed_count(design: Design) -> int:
    """The opaque slots of ``design`` that a target-10 write removes."""
    return sum(
        1
        for entity in design.entities()
        for key, value in (entity.ext["kicad"].payload if "kicad" in entity.ext else ())
        if _opaque(key) and _removed(value)
    )


def _normal(data: Any, unconnected: bool = False) -> Any:
    """Canonical data without the slots a target-10 write removes (``(net 0)`` of an unconnected zone
    or rule area included), with opaque fragment texts and minimum versions left out."""
    if isinstance(data, dict):
        flag = unconnected or ("outline" in data and "net_id" not in data)
        out: dict[str, Any] = {}
        for key, value in data.items():  # pyright: ignore[reportUnknownVariableType]
            if key == "min_version":
                continue
            if key == "payload":
                value = [
                    [k.split("@")[0], "<fragment>"] if _opaque(k) else [k, v]
                    for k, v in value  # pyright: ignore[reportUnknownVariableType]
                    if not (_opaque(k) and _removed(v))
                    and not (flag and k == "slot:.:modeled" and v == "net_id")
                ]
            out[key] = _normal(value, flag if key in ("ext", "kicad") else False)
        return out
    if isinstance(data, list):
        return [_normal(v) for v in data]  # pyright: ignore[reportUnknownVariableType]
    return data


def comparable(design: Design) -> Any:
    """The canonical data of a design apart from the board's header bag and net numbers."""
    data = canonical(design)
    data[2].pop("ext", None)
    for net in data[1].get("nets", []):
        net.pop("ext", None)
    return _normal(data)


def major_nine(item: CorpusItem) -> bool:
    text = item.path.read_text(encoding="utf-8")[:200] if item.path.is_file() else ""
    version = next((int(t) for t in text.replace(")", " ").split() if t.isdigit() and len(t) == 8), 0)
    return major_for(FileKind.BOARD, version) == 9


@pytest.mark.needs_corpus
@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_demos_converted_to_10(item: CorpusItem) -> None:
    path = require(item)
    if not major_nine(item):
        pytest.skip(f"{item.id} is not a major-9 board")
    design = read(path)[0]
    text = write_board(design, target=10).text
    assert load(text) == "load", f"{item.id}: the target-10 text does not load"
    again = read_board(text)
    again = dataclasses.replace(again, header=dataclasses.replace(again.header, name=design.header.name))
    assert opaque_count(again) == opaque_count(design) - removed_count(design), item.id
    assert comparable(again) == comparable(design), f"{item.id}: the re-read model differs"
    digests = opaque_digests(again)
    for entity in design.entities():
        for key, fragment in entity.ext["kicad"].payload if "kicad" in entity.ext else ():
            if _opaque(key) and not _removed(fragment) and not _changes_inside(fragment):
                digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
                assert digest in digests, f"{item.id}: fragment changed: {fragment[:80]}"


def test_downgrade_refused() -> None:
    again = read_board(triad_text(10))
    with pytest.raises(DowngradeRefusedError):
        write_board(again, target=9)


def test_kicad_8_refused() -> None:
    with pytest.raises(LegacyEditRefusedError):
        write_board(read_board(OLD), target=10)


def test_lossy_embedding() -> None:
    """A 10.0 ``Mini_R_0603`` placed for target 9 is refused; with ``allow_lossy`` it loads on 9.0.9."""
    with pytest.raises(LossyWriteError):
        write_board(lossy_design(), target=9)
    assert "duplicate_pad_numbers_are_jumpers" not in lossy_text()
    outcome = run("pcb-write-lossy-9")
    if major() == 9:
        assert outcome == "load"
