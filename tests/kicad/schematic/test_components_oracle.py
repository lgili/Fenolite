# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The components Fenolite reads from a schematic are those ``kicad-cli`` exports (capability
kicad-oracle, "Schematic components agree with kicad-cli"; hypothesis ``H-K-SCH-COMPONENTS``; c0060)."""

from __future__ import annotations

from pathlib import Path

import _probes
import _schcases
import _schcorpus
import _schfix
import pytest
from _boards import census
from _corpus import manifest_items, require

from fenolite.backends.kicad.cli import NETLIST
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("name", sorted(_schcases.FIXTURES))
def test_fixtures_components(name: str) -> None:
    found = _schcases.compare(_schcases.fixture(name))
    assert found is not None, f"kicad-cli did not load {_schcases.fixture(name).name}"
    ours, theirs = found
    assert ours == theirs
    assert _probes.run(f"sch-components-{name}") == "equal"


def test_fixtures_on_board_symbol() -> None:
    outcome = _probes.run("sch-components-on-board")
    assert outcome in ("present", "absent")
    with_all = _schcases.read(_schcases.fixture("flat"), on_board_only=False)
    without = _schcases.read(_schcases.fixture("flat"), on_board_only=True)
    assert {ref for ref, _, _ in with_all - without} == {"R3"}
    print(f"sch-components-on-board: {outcome}; on_board_only={_schcases.on_board_only()}")


def test_fixtures_load_on_their_major() -> None:
    """Every authored schematic of the running major's format is loaded by ``kicad-cli``."""
    ten = _probes.major() >= 10
    roots = (
        ["flat.kicad_sch", "units.kicad_sch", "hier/top.kicad_sch", "multi/top.kicad_sch", "bus.kicad_sch"]
        if ten
        else ["flat_v9.kicad_sch", "units_v9.kicad_sch", "hier_v9/top.kicad_sch"]
    )
    for name in roots:
        root = _schfix.SCHEMATICS / name
        extra = {"child.kicad_sch": root.parent / "child.kicad_sch"} if "hier" in name else {}
        if name.startswith("multi"):
            extra = {"cell.kicad_sch": root.parent / "cell.kicad_sch"}
        run = _probes.runner().export_netlist(root, files=extra)
        assert run.ok and NETLIST in run.outputs, f"{name}: exit {run.returncode}: {run.stderr.strip()}"


# -- corpus projects ("Corpus": every project with a root row and no multi-instance or old sheet)

TAG_OF_MAJOR = {10: "10.0.6", 9: "9.0.9.1"}


def _projects(
    tag: str, folder: Path
) -> tuple[list[tuple[str, Path, list[_schcorpus.SchRow]]], dict[str, int]]:
    """``(root id, placed root, rows of its sheets)`` of the projects to compare at ``tag``, and the
    number of projects left out per reason."""
    by_id = {item.id: item for item in manifest_items("sch")}
    rows = [r for r in _schcorpus.rows() if tag in r.tags]
    for row in rows:
        require(by_id[row.id])
    placed = _schcorpus.layout(folder, tag, rows)
    by_path = _schcorpus.at_tag(tag, rows)
    by_file = {str(path): by_path[name] for name, path in placed.items()}
    left: dict[str, int] = {"sch-old": 0, "newer-than-the-running-major": 0}
    newest = FORMAT_VERSIONS[FileKind.SCHEMATIC][_probes.major()]
    selected: list[tuple[str, Path, list[_schcorpus.SchRow]]] = []
    for path, row in sorted(by_path.items()):
        if not _schcorpus.root_at(row, tag):
            continue
        if "sch-old" in row.uses:
            left["sch-old"] += 1
            continue
        sheets = [by_file[str(f)] for f in _schcorpus.project_files(placed[path]) if str(f) in by_file]
        if any("sch-old" in s.uses for s in sheets):
            left["sch-old"] += 1
        elif any(_schcorpus.version_of(s.file) > newest for s in sheets):
            left["newer-than-the-running-major"] += 1
        else:
            selected.append((row.id, placed[path], sheets))
    return selected, left


@pytest.mark.needs_corpus
@pytest.mark.slow
def test_corpus_components(tmp_path: Path) -> None:
    major = _probes.major()
    tag = TAG_OF_MAJOR[major]
    selected, left = _projects(tag, tmp_path)
    assert selected, "no corpus project to compare"
    different: list[str] = []
    not_loaded: list[str] = []
    components = variables = 0
    for root_id, root, _sheets in selected:
        found = _schcases.compare(root)
        if found is None:
            not_loaded.append(root_id)
            continue
        ours, theirs = found
        components += len(theirs)
        variables += sum(1 for _, value, footprint in ours if "${" in value + footprint)
        if not _schcases.same(ours, theirs):
            only_ours, only_theirs = len(ours - theirs), len(theirs - ours)
            different.append(
                f"{root_id}: {only_ours} only read by Fenolite, {only_theirs} only in the netlist"
            )
    data = {
        "tag": tag,
        "projects_compared": len(selected) - len(not_loaded),
        "projects_equal": len(selected) - len(not_loaded) - len(different),
        "projects_not_loaded_by_kicad_cli": sorted(not_loaded),
        "projects_left_out": left,
        "components": components,
        "components_with_a_text_variable": variables,
        "on_board_only": _schcases.on_board_only(),
    }
    census("schematic_components", f"major-{major}", data)
    print("schematic components:", data)
    assert not different, "\n".join(different)
    assert not not_loaded, f"kicad-cli did not load: {', '.join(not_loaded)}"
