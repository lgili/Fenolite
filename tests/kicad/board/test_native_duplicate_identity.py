# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored duplicate identity controls; no production ambiguity exception (c0355)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from pathlib import Path

import _kicad
import pytest
from _drawn_curve import curve_project
from _native_identity_refs import unreferenced_id_facts

from fenolite.api.sides import read_side
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.derived_teardrops import regions
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse_bytes
from fenolite.cli._derived_cache import _raw_bindings, inputs

pytestmark = pytest.mark.needs_kicad


def physical(n):
    if isinstance(n, Atom):
        return n.kind.value, n.value
    if n.name in {"uuid", "tstamp"}:
        return None
    return n.name, tuple(x for c in n.children if (x := physical(c)) is not None)


def pad_multiset(root):
    return Counter(physical(pad) for fp in root.nodes("footprint") for pad in fp.nodes("pad"))


@pytest.mark.parametrize("case", ("identical-signature-order", "aliased-id-distinct-roles"))
def test_authored_unreferenced_duplicate_identity_keeps_native_physical_multiset(
    tmp_path: Path, case: str
) -> None:
    if not _kicad.supported_version().startswith("10."):
        pytest.skip("this control requires actual native10 refill/save; no native9 refill claim")
    source = curve_project(tmp_path / "source", 10, 10_000)
    path = source / "font_probe.kicad_pcb"
    root = parse_bytes(path.read_bytes())
    fp = root.nodes("footprint")[0]
    pads = fp.nodes("pad")
    assert len(pads) == 2
    original_id = pads[0].find("uuid")
    assert original_id is not None

    def with_id(pad, identity):
        assert pad.find("uuid") is not None
        return pad.with_children(
            tuple(identity if isinstance(c, Node) and c.name == "uuid" else c for c in pad.children)
        )

    if case == "identical-signature-order":
        new_id = original_id.with_children(
            (Atom.string(str(uuid.UUID("00000000-0000-4000-8000-000000003555"))),)
        )
        duplicate = with_id(pads[0], new_id)
        a_fp = fp.with_children((*fp.children, duplicate))
        # Both identical physical objects remain; swap complete slots/IDs without choosing a first match.
        b_children = tuple(duplicate if c is pads[0] else c for c in fp.children)
        b_fp = fp.with_children((*b_children, pads[0]))
    else:
        a_fp = fp.with_children(tuple(with_id(c, original_id) if c is pads[1] else c for c in fp.children))
        b_fp = fp
    a = root.with_children(tuple(a_fp if c is fp else c for c in root.children))
    b = root.with_children(tuple(b_fp if c is fp else c for c in root.children))
    files = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file() and p != path}
    closure = [unreferenced_id_facts(n, files) for n in (a, b)]
    assert pad_multiset(a) == pad_multiset(b)
    assert dumps(a) != dumps(b)
    files = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file() and p != path}
    native = KicadCli(Path(_kicad.cli()))
    saved = []
    output_hashes = []
    input_hashes = []
    for label, board in (("a", a), ("b", b)):
        body = dumps(board).encode()
        input_hashes.append(hashlib.sha256(body).hexdigest())
        folder = tmp_path / label
        folder.mkdir()
        candidate = folder / path.name
        candidate.write_bytes(body)
        result = native.refill(candidate, files=files)
        assert result.run.ok and result.board is not None
        (folder / "native-saved.kicad_pcb").write_bytes(result.board)
        saved.append(parse_bytes(result.board))
        output_hashes.append(hashlib.sha256(result.board).hexdigest())
    assert pad_multiset(saved[0]) == pad_multiset(saved[1])
    assert sum(pad_multiset(saved[0]).values()) == sum(pad_multiset(a).values())
    ci = inputs(read_side(source))
    assert ci is not None
    compared = [regions(n, _raw_bindings(n, frozenset(ci.bindings.values()))) for n in saved]
    assert compared[0] and compared[0] == compared[1]
    (tmp_path / "native-duplicate-identity-proof.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "case": case,
                "input_sha256": input_hashes,
                "saved_sha256": output_hashes,
                "physical_pads": sum(pad_multiset(a).values()),
                "physical_multisets_equal": True,
                "exact_derived_regions": len(compared[0]),
                "exact_derived_sha256": hashlib.sha256(repr(compared[0]).encode()).hexdigest(),
                "runtime_exception_or_royal_admission_claimed": False,
                "reference_closure": closure,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )
