# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Vendored catalog records are read without executing their package code (c0273)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from _checkcli import run

from fenolite.cli.blocksrc import find_blocks
from fenolite.cli.blockvendored import find_vendored
from fenolite.dsl.blockitem import from_record
from fenolite.dsl.record import BlockRecord, Header, describe, record_data

ITEM = Path(__file__).resolve().parents[2] / "data/library_repo/block_items/blocks/cc0/Demo/led"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    destination = tmp_path / "fenolite_library/blocks/Demo/led"
    shutil.copytree(ITEM, destination)
    (tmp_path / "design.py").write_text("# Authored catalog fixture; not executed.\n")
    return tmp_path


def package(project: Path) -> Path:
    return project / "fenolite_library/blocks/Demo/led"


def test_static_discovery_and_commands_do_not_import(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    source = package(project) / "__init__.py"
    source.write_text('raise RuntimeError("catalog must not execute this package")\n')
    paths = {"tests": "tests/test_led.py", "usage": "usage/led.py", "golden": "golden/led.json"}
    for relative in paths.values():
        file = package(project) / relative
        file.parent.mkdir(exist_ok=True)
        file.write_text("# Authored convention path control; never executed.\n")
    before = {
        name for name in sys.modules if name == "fenolite_library" or name.startswith("fenolite_library.")
    }
    (entry,) = find_vendored(project)
    assert entry.module == "fenolite_library.blocks.Demo.led"
    assert (entry.id, entry.version, entry.namespace) == ("Demo:led", "1.0.0", "Demo")
    for verb, target in (("list", ()), ("show", ("Demo:led",)), ("doc", ("Demo:led",))):
        code, result, error, _ = run(monkeypatch, project, "blocks", verb, *target, "--script", "design.py")
        assert code == 0, error
        if verb == "list":
            (row,) = [r for r in result["result"]["blocks"] if r["source"] == "library"]
            assert row["id"] == "Demo:led" and row["version"] == "1.0.0"
        elif verb == "show":
            block = result["result"]["block"]
            assert block["id"] == "Demo:led" and block["layout"] is None
            assert {kind: block[kind] for kind in paths} == paths
        else:
            assert result["result"]["text"].startswith("# Demo:led 1.0.0")
    after = {
        name for name in sys.modules if name == "fenolite_library" or name.startswith("fenolite_library.")
    }
    assert after == before


def test_library_block_tests_accept_script_catalog(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    for relative, text in (
        (
            "tests/test_led.py",
            "from fenolite_library.blocks.Demo.led import led\n"
            'def test_package():\n    assert led.name == "Demo:led"\n',
        ),
        ("usage/led.py", "# Authored usage path control; --only tests does not build it.\n"),
        ("golden/led.json", "{}\n"),
    ):
        file = package(project) / relative
        file.parent.mkdir(exist_ok=True)
        file.write_text(text)
    code, result, error, _ = run(
        monkeypatch,
        project.parent,
        "blocks",
        "test",
        "Demo:led",
        "--script",
        str(project / "design.py"),
        "--only",
        "tests",
    )
    assert code == 0, error
    (block,) = result["result"]["blocks"]
    assert block["id"] == "Demo:led" and block["tests"][0]["status"] == "passed"


def test_library_usage_keeps_namespace_and_binds_dependency_bytes(
    monkeypatch: pytest.MonkeyPatch, project: Path
) -> None:
    from fenolite.cli._blocks_index import exported_block, item_module

    root = package(project)
    source = root / "__init__.py"
    source.write_text(
        source.read_text()
        .replace('"Mini:Mini_R"', '"Fenolite:Resistor"')
        .replace('"Mini:Mini_R_0603"', '"Fenolite:Chip_0603"')
    )
    with item_module(root) as module:
        record = from_record(describe(exported_block(module)))
    (root / "block.json").write_text(record.text())
    dependency = project / "fenolite_library/shared.py"
    dependency.write_text('VALUE = "chosen"\n')
    usage = """from fenolite.dsl import Design, Net, Part, connect, mm
from fenolite_library.blocks.Demo.led import led
from fenolite_library.shared import VALUE
assert VALUE == "chosen"
design = Design("library_usage")
design.board(mm(40), mm(20))
dut = design.use(led, "dut")
header = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
design.add(header)
for pin, name in enumerate(("POS", "NEG"), 1):
    net = Net(name)
    design.add(net)
    connect(net, dut.port(name), header[pin])
dut.part("R").place(mm(10), mm(10))
header.place(mm(20), mm(10))
"""
    for relative, text in (
        ("usage/led.py", usage),
        (
            "tests/test_led.py",
            "from fenolite_library.blocks.Demo.led import led\n"
            "from fenolite_library.shared import VALUE\n"
            'def test_package():\n    assert led.name == "Demo:led" and VALUE == "chosen"\n',
        ),
        ("golden/led.json", "{}\n"),
    ):
        file = root / relative
        file.parent.mkdir(exist_ok=True)
        file.write_text(text)
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    args = ("blocks", "test", "Demo:led", "--script", str(project / "design.py"), "--golden")
    code, result, error, _ = run(monkeypatch, project.parent, *args, "--dry-run")
    assert code == 0, (result.get("issues"), error)
    (block,) = result["result"]["blocks"]
    assert block["usage"] == "passed" and block["tests"][0]["status"] == "passed"
    assert {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
    dependency.write_text('VALUE = "changed after review"\n')
    code, _, error, _ = run(
        monkeypatch, project.parent, *args, "--confirm", "--plan", result["result"]["plan_id"]
    )
    assert code == 4 and error["code"] == "FEN-4002"
    assert (root / "golden/led.json").read_text() == "{}\n"


def test_default_script_and_explicit_other_folder(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    code, result, error, _ = run(monkeypatch, project, "blocks", "list")
    assert code == 0, error
    assert any(r["id"] == "Demo:led" for r in result["result"]["blocks"])
    code, result, error, _ = run(
        monkeypatch, project.parent, "blocks", "show", "Demo:led", "--script", str(project / "design.py")
    )
    assert code == 0, error
    assert result["result"]["block"]["source"] == "library"


@pytest.mark.parametrize(
    "problem", ["missing-index", "broken-json", "wrong-schema", "no-package", "wrong-item-version"]
)
def test_broken_items_are_named(monkeypatch: pytest.MonkeyPatch, project: Path, problem: str) -> None:
    root = package(project)
    if problem == "missing-index":
        (root / "block.json").unlink()
    elif problem == "broken-json":
        (root / "block.json").write_text("{")
    elif problem == "wrong-schema":
        table = json.loads((root / "block.json").read_text())
        table["schema"] = "future"
        (root / "block.json").write_text(json.dumps(table))
    elif problem == "no-package":
        (root / "__init__.py").unlink()
    else:
        table = json.loads((root / "item.json").read_text())
        table["version"] = "1.1.0"
        (root / "item.json").write_text(json.dumps(table))
    code, result, error, _ = run(monkeypatch, project, "blocks", "list")
    assert code == 0, error
    assert not any(r["id"] == "Demo:led" for r in result["result"]["blocks"])
    (found,) = result["issues"]
    assert (found["code"], found["severity"], found["where"]) == (
        "blocks.item-broken",
        "warning",
        "fenolite_library/blocks/Demo/led",
    )


def test_reserved_namespace_is_an_error(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    target = project / "fenolite_library/blocks/Fenolite/led"
    target.parent.mkdir()
    shutil.move(str(package(project)), target)
    record = BlockRecord(
        "Fenolite:led", Header("Fenolite:led", "1.0.0", "authored reserved control", sources=("S-0001",)), ()
    )
    (target / "block.json").write_text(from_record(record).text())
    manifest = json.loads((target / "item.json").read_text())
    manifest["id"] = "Fenolite:led"
    (target / "item.json").write_text(json.dumps(manifest))
    code, result, error, _ = run(monkeypatch, project, "blocks", "list")
    assert code == 5, error
    assert [i["code"] for i in result["issues"]] == ["blocks.namespace-reserved"]
    assert not any(r["source"] == "library" for r in result["result"]["blocks"])
    code, result, error, _ = run(monkeypatch, project, "blocks", "test", "--only", "tests")
    assert code == 5, error
    assert [i["code"] for i in result["issues"]] == ["blocks.namespace-reserved"]


def test_library_and_file_duplicate_id(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    shutil.copy(package(project) / "__init__.py", project / "own.py")
    code, result, error, _ = run(monkeypatch, project, "blocks", "list", "--from", "own.py")
    assert code == 5, error
    assert [i["code"] for i in result["issues"]] == ["blocks.duplicate-id"]
    assert {r["source"] for r in result["result"]["blocks"] if r["id"] == "Demo:led"} == {"library", "file"}


def test_explicit_definition_access_is_lazy_execution(project: Path) -> None:
    (entry,) = [e for e in find_blocks(script_dir=project) if e.source == "library"]
    assert entry.item_root == package(project) and entry.source_file == package(project) / "__init__.py"
    assert entry.id == "Demo:led"
    assert record_data(describe(entry.definition)) == record_data(entry.record)
    source = package(project) / "__init__.py"
    source.write_text(source.read_text().replace('param("1k"', 'param("7k"'))
    (updated,) = [e for e in find_blocks(script_dir=project) if e.source == "library"]
    assert record_data(describe(updated.definition)) != record_data(updated.record)


def test_doc_review_binds_static_record(monkeypatch: pytest.MonkeyPatch, project: Path) -> None:
    code, result, error, _ = run(
        monkeypatch, project, "blocks", "doc", "Demo:led", "--out", "docs", "--dry-run"
    )
    assert code == 0, error
    target = package(project) / "block.json"
    target.write_text(target.read_text() + " ")
    code, _, error, _ = run(
        monkeypatch,
        project,
        "blocks",
        "doc",
        "Demo:led",
        "--out",
        "docs",
        "--confirm",
        "--plan",
        result["result"]["plan_id"],
    )
    assert code == 4 and error["code"] == "FEN-4002"
