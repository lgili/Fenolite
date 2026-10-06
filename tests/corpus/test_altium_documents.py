# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite check`` on the public Altium project sets (capability altium-verification, "Round trips over
the corpus and the samples"; change c0044; ``H-A-VER-ERC``).

Each set of c0043's "Altium project sets" (the rows of one use ``altium-set:<nn>``) is laid out as its
project folder under pytest's temporary directory and checked. The test records, per set, the status of
each stage and the counts of the pair (``schematic``, ``pcb``). A set with differences does not fail here:
c0043's "Altium project sets agree" judges them (``H-A-IMP-NETLIST``). The census holds counts only.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from _altium_sets import SETS, lay_out
from _boards import census
from _corpus import heavy_enabled
from _projects import tree_snapshot

import fenolite.cli.main as cli_main
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.checks.documents import DOCUMENT_STAGES

pytestmark = pytest.mark.needs_corpus


def check(folder: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", str(folder), "--json"])
    assert out.getvalue(), err.getvalue()
    return code, json.loads(out.getvalue())


def test_sets_exist() -> None:
    assert len(SETS) >= 3 and all(any("-prjpcb-" in item.id for item in items) for items in SETS.values())


@pytest.mark.parametrize("name", list(SETS))
def test_project_set_is_checked(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Project sets": every set is checked without a crash and its folder copy is unchanged."""
    items = SETS[name]
    if any(item.heavy for item in items) and not heavy_enabled():
        pytest.skip(f"{name} holds a heavy corpus item: set FENOLITE_HEAVY=1 to include it")
    folder = lay_out(items, tmp_path / "set")
    before = tree_snapshot(folder)
    code, env = check(folder, monkeypatch)
    assert tree_snapshot(folder) == before and not (folder / ".fenolite").exists()
    assert code in (0, 5), env
    project = env["result"]["project"]
    assert project["backend"] == "altium" and project["built"] is False and project["board"] is not None
    stages = {stage["name"]: stage for stage in env["result"]["stages"]}
    assert list(stages) == list(DOCUMENT_STAGES)
    assert stages["roundtrip.rta2"]["reason"] == "native-input"
    for level in ("roundtrip.rta0", "roundtrip.rta1"):
        assert stages[level]["summary"]["failed"] == 0, (name, level)
    assert stages["roundtrip.rta1"]["status"] == "ok"
    assert set(stages["roundtrip.rta0"]["summary"]["unjudged"]) <= {"not-a-container", "too-large"}
    assert stages["model.validate"]["status"] != "skipped" and stages["erc.lite"]["status"] == "ok"
    compare = stages["netlist.assignment_compare"]
    assert compare["status"] in ("ok", "errors")
    (pair,) = compare["summary"]["pairs"]
    assert (pair["a"], pair["b"]) == ("schematic", "pcb") and pair["common"] > 0

    # H-A-VER-ERC: no floating-pin warning names a pin that carries a No ERC mark or that a net lists.
    read = AltiumBackend().read_documents(AltiumBackend().documents(folder))
    assert read.schematic is not None
    circuit = read.schematic.design.circuit
    refs = {component.id: component.ref for component in circuit.components}
    marked = {f"{refs[mark.component_id]}-{mark.pin}" for mark in circuit.no_connects}
    on_net = {f"{refs[m.component_id]}-{m.pin}" for net in circuit.nets for m in net.members}
    floating = {i["where"] for i in env["issues"] if i["code"] == "erc.lite.floating-pin"}
    assert not floating & marked, name
    assert not floating & on_net, name
    census(
        "altium-documents",
        name,
        {
            "documents": len(project["documents"]),
            "missing": len(project["skipped"]),
            "exit": code,
            "stages": {stage: [found["status"], found["reason"]] for stage, found in stages.items()},
            "pair": {key: pair[key] for key in ("common", "only_a", "only_b", "differences")},
            "erc": dict(stages["erc.lite"]["summary"]),
            "no_connect_marks": len(marked),
            "rt_a0": {
                key: stages["roundtrip.rta0"]["summary"][key] for key in ("documents", "streams", "unjudged")
            },
            "rt_a1": {
                key: stages["roundtrip.rta1"]["summary"][key]
                for key in ("documents", "streams", "records", "bytes_equal", "opaque_count")
            },
            "evidence": env["evidence"]["level"],
        },
    )
