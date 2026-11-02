# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Owner context is complete, hash-bound and strict (c0276 task 7.4)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import _drawn
import _drawn_context as context
import _drawn_corpus as census
import pytest

from fenolite.backends.kicad.cli import KicadCli


def sheet(ident: str, *children: str) -> context.SheetInput:
    """The generated graph fragments are authored CC0-1.0 fixture data."""
    refs = "".join(
        f'(sheet (uuid "{uuid5(NAMESPACE_URL, ident + str(n))}") (property "Sheetfile" "{child}.kicad_sch"))'
        for n, child in enumerate(children)
    )
    data = f'(kicad_sch (uuid "{uuid5(NAMESPACE_URL, ident)}") {refs})'.encode()
    return context.SheetInput(ident, f"authored/{ident}.kicad_sch", hashlib.sha256(data).hexdigest(), data)


def test_child_keeps_both_root_owners_and_repeated_instances() -> None:
    root_a, root_b, leaf = sheet("root-a", "leaf", "leaf"), sheet("root-b", "leaf"), sheet("leaf")
    index = context.Contexts((root_a, root_b, leaf), (root_a.id, root_b.id))
    owners = index.for_row(leaf.id)
    assert [owner.root.id for owner in owners] == [root_a.id, root_b.id]
    assert [owner.data(leaf.id)["target_instances"] for owner in owners] == [2, 1]
    assert not any(owner.errors for owner in owners)
    encoded = json.dumps([owner.data(leaf.id) for owner in owners])
    assert "authored/" not in encoded and ".kicad_sch" not in encoded
    paths = [i["instance_path_sha256"] for owner in owners for i in owner.data(leaf.id)["instances"]]
    assert len(paths) == len(set(paths)) == 5
    assert index.for_row(root_b.id)[0].root.id == root_b.id


def test_unowned_row_remains_an_explicit_standalone_case() -> None:
    leaf = sheet("leaf")
    (owner,) = context.Contexts((leaf,), ()).for_row(leaf.id)
    assert owner.root == leaf and not owner.registered and not owner.errors
    assert owner.data(leaf.id)["scope"] == "standalone-unowned"


def test_both_native_jobs_fetch_declared_owner_projects() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for job in ("kicad-9", "kicad-10"):
        block = workflow.split(f"  {job}:\n", 1)[1]
        block = re.split(r"\n  \S", block, maxsplit=1)[0]
        assert any("--uses project" in line for line in block.splitlines() if "corpus_fetch.py" in line)


def test_all_hashes_precede_every_parser_call(monkeypatch) -> None:
    root, leaf = sheet("root", "leaf"), sheet("leaf")
    monkeypatch.setattr(
        context, "parse_bytes", lambda *a, **k: pytest.fail("unchecked source reached parser")
    )
    with pytest.raises(ValueError, match="^context-sha256$"):
        context.Contexts((root, replace(leaf, data=b"Authored corrupt payload")), (root.id,))


@pytest.mark.parametrize("defect", ("missing", "undeclared", "cycle", "outside"))
def test_context_refuses_missing_cycles_and_path_escape(defect: str) -> None:
    root, leaf = sheet("root", "leaf"), sheet("leaf")
    expected = "context-missing-input"
    if defect == "missing":
        leaf = replace(leaf, data=None)
    elif defect == "undeclared":
        root = sheet("root", "unknown")
        expected = "context-undeclared-input"
    elif defect == "cycle":
        leaf = sheet("leaf", "root")
        expected = "context-sheet-cycle"
    elif defect == "outside":
        root = sheet("root", "../leaf")
        leaf = replace(leaf, path="leaf.kicad_sch")
        expected = "context-outside-project"
    owner = context.Contexts((root, leaf), (root.id,)).for_row(root.id)[0]
    assert owner.errors == (expected,)


def test_missing_owner_cannot_turn_child_into_a_fake_root() -> None:
    root, leaf = replace(sheet("root", "leaf"), data=None), sheet("leaf")
    (owner,) = context.Contexts((root, leaf), (root.id,)).for_row(leaf.id)
    assert owner.root.id == root.id and owner.registered
    assert owner.errors == ("context-missing-input",) and owner.data(leaf.id)["target_instances"] == 0


@pytest.mark.parametrize(("name", "instances"), (("hier", 1), ("repeat", 2)))
def test_authored_owner_uses_complete_annotation_and_pin_universe(
    name, instances, tmp_path, monkeypatch
) -> None:
    output, files, child, owner = context.authored(name, 9)
    _, own, circuit = _drawn.resolved(output)
    references = {c.properties["fenolite.path"]: c.ref for c in circuit.components}
    native = {
        net.name or f"AuthoredUnnamed{n}": {(references[path], number) for path, number in net.members}
        for n, net in enumerate(own.nets)
    }
    roots = []

    def exported(cli, root, source):
        roots.append(root)
        return native

    monkeypatch.setattr(census._erc, "netlist", exported)
    inputs = []
    for file, data in files.items():
        path = tmp_path / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        inputs.append(census.Input(file, file, hashlib.sha256(data).hexdigest()))
    report = census.measure(
        tmp_path,
        owner.root.id,
        inputs,
        KicadCli(Path("authored-stub")),
        ident=child.id,
        major=9,
        native_version="authored-stub",
    )
    assert report["status"] == "equal", report
    assert roots == [owner.root.id, owner.root.id]
    assert owner.data(child.id)["target_instances"] == instances
    for key in ("partition", "lowered_partition", "lowered_native_partition"):
        assert report[key]["equal"] and report[key]["drawn_pins"] == len(own.pins)
        assert report[key]["native_only_pins"] == 0


@pytest.mark.parametrize("missing_project", (False, True))
def test_actual_corpus_dispatch_uses_owner_root_and_requires_project(tmp_path, monkeypatch, missing_project):
    output, files, child, owner = context.authored("repeat", 9)
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "authored_context_driver", root / "tests/kicad/schematic/test_drawn_corpus.py"
    )
    assert spec and spec.loader
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    cache = tmp_path / "authored-cache"
    cache.mkdir()
    project_name = owner.root.id.removesuffix(".kicad_sch") + ".kicad_pro"
    files[project_name] = output.files[project_name]
    declared, catalog, rows = {}, {}, {}
    for file, data in files.items():
        path = cache / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        declared[file] = {"sha256": hashlib.sha256(data).hexdigest()}
        catalog[f"authored/{file}"] = SimpleNamespace(id=file, file=path)
        if file.endswith(".kicad_sch"):
            rows[file] = SimpleNamespace(
                id=file, file=path, ref="authored", path=f"authored/{file}", tags=("9.0.9.1",)
            )
    if missing_project:
        (cache / project_name).unlink()
    monkeypatch.setattr(driver, "DECLARED", declared)
    monkeypatch.setattr(driver, "BY_ID", rows)
    monkeypatch.setattr(
        driver,
        "contexts",
        lambda major: context.Contexts(
            tuple(
                context.SheetInput(file, f"authored/{file}", declared[file]["sha256"], data)
                for file, data in files.items()
                if file.endswith(".kicad_sch")
            ),
            (owner.root.id,),
        ),
    )
    monkeypatch.setattr(driver._schprojects, "_at_tag", lambda tag: catalog)
    monkeypatch.setattr(driver, "manifest_items", lambda tag: list(rows.values()))
    monkeypatch.setattr(driver, "require", lambda row: row.file)
    _, own, circuit = _drawn.resolved(output)
    references = {c.properties["fenolite.path"]: c.ref for c in circuit.components}
    native = {
        net.name or f"AuthoredNet{n}": {(references[path], pin) for path, pin in net.members}
        for n, net in enumerate(own.nets)
    }
    exports = []

    def exported(cli, root_file, inputs):
        exports.append((root_file, inputs))
        return native

    monkeypatch.setattr(census._erc, "netlist", exported)
    case = tmp_path / "case"
    case.mkdir()
    args = rows[child.id], case, (KicadCli(Path("authored-stub")), "authored-stub", 9)
    if missing_project:
        with pytest.raises(AssertionError):
            driver.test_demo_drawn_census(*args)
    else:
        driver.test_demo_drawn_census(*args)
    report = json.loads((case / "drawn-census.json").read_text(encoding="utf-8"))
    assert report["id"] == child.id
    (owner_report,) = report["contexts"]
    assert owner_report["context"]["owner_id"] == owner.root.id
    assert owner_report["context"]["target_instances"] == 2
    assert report["status"] == ("missing-cache" if missing_project else "equal")
    assert len(exports) == (0 if missing_project else 2)
    if exports:
        assert all(root_file == owner.root.id for root_file, _ in exports)
        assert project_name in exports[0][1]
    assert not list(case.rglob("*.kicad_sch"))
