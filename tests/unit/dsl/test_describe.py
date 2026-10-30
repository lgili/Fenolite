# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Describing a block without a build, its canonical record and digests (capability block-library,
"Describing a block", "Blocks that cannot be elaborated" and "Canonical block record"; change c0268)."""

from __future__ import annotations

import builtins
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

import fenolite.catalog.devices
import fenolite.catalog.records
from fenolite.dsl import Net, block, connect, describe, param, resistor
from fenolite.dsl.block import BlockDef
from fenolite.dsl.quantity import ohm, volt
from fenolite.dsl.record import digests, record_data, record_json

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "blocks"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_c0268_describe_{name}", DATA / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DIVIDER: BlockDef = load("divider").divider


def test_ports_from_defaults() -> None:
    """Scenario "Ports from defaults"."""
    record = describe(DIVIDER)
    assert [(p.name, p.kind, p.direction, p.doc) for p in record.ports or ()] == [
        ("HI", "power", "in", "input"),
        ("LO", "power", "in", "reference, usually ground"),
        ("OUT", "power", "out", "divided output"),
    ]
    assert record.parts == ("bot", "top") and record.nets == () and record.blocks == ()
    assert record.requires is not None and record.requires.lib_ids == ("Fenolite:Resistor",)
    assert record.elaboration is None and record.id == "Acme:divider"


def test_hermetic_describe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Hermetic describe"."""

    def refuse(*args: object, **kwargs: object) -> Any:
        raise AssertionError("describe must not read a file, run a tool or load the catalog")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(fenolite.catalog.devices, "shipped_devices", refuse)
    monkeypatch.setattr(fenolite.catalog.records, "shipped_tree", refuse)
    record = describe(DIVIDER)
    assert record.elaboration is None and record.ports is not None


def test_required_parameter() -> None:
    """Scenario "Required parameter"."""

    @block
    def needs(b: Any, *, vout: object = param(unit="volt", doc="output")) -> None:
        b.port("OUT", direction="out")

    record = describe(needs)
    assert record.ports is None and record.parts is None and record.requires is None
    assert record.elaboration == {"reason": "required parameter vout"}
    data = record_data(record)
    assert data["ports"] is None and data["params"][0]["type"] == "quantity"  # type: ignore[index]


def test_failing_block_is_reported() -> None:
    @block
    def broken(b: Any) -> None:
        raise ValueError("no luck")

    record = describe(broken)
    assert record.elaboration == {"error": "ValueError: no luck"} and record.ports is None


def test_nested_blocks_and_queries() -> None:
    @block
    def inner(b: Any) -> None:
        b.net("A")
        b.part("R", device=resistor(ohm("10k")))

    @block
    def outer(b: Any) -> None:
        port = b.port("IN", direction="in")
        mid = b.net("MID")
        b.use(inner, "low")
        r = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", prefix="R", value="1k")
        connect(port, r[1])
        connect(mid, r[2])

    record = describe(outer)
    assert record.parts == ("R", "low/R") and record.nets == ("MID", "low/A")
    assert record.blocks == (("low", "inner"),)
    assert record.requires is not None and len(record.requires.queries) == 1
    assert record.requires.queries[0].startswith("resistor(")


def _divider_with(doc: str) -> BlockDef:
    @block(id="Acme:divider", version="1.0.0", summary="d", licence="MIT")
    def divider(b: Any, *, vout: object = param(volt("3.3"), doc="out")) -> None:
        b.port("HI", Net, direction="in", doc=doc)

    return divider


def test_doc_change_keeps_the_definition() -> None:
    """Scenario "Doc change keeps the definition"."""
    one, two = digests(describe(_divider_with("input"))), digests(describe(_divider_with("the input")))
    assert one["record"] != two["record"]
    assert (one["definition"], one["interface"]) == (two["definition"], two["interface"])


def test_default_change_keeps_the_interface() -> None:
    @block(id="Acme:divider", version="1.0.0", summary="d", licence="MIT")
    def divider(b: Any, *, vout: object = param(volt("5"), doc="out")) -> None:
        b.port("HI", Net, direction="in", doc="input")

    one, two = digests(describe(_divider_with("input"))), digests(describe(divider))
    assert one["definition"] != two["definition"] and one["interface"] == two["interface"]


def test_record_json_shape() -> None:
    data = json.loads(record_json(describe(DIVIDER)))
    assert data["schema"] == "fenolite.block.v0" and data["id"] == "Acme:divider"
    assert set(data["digests"]) == {"record", "definition", "interface"}
    current = next(p for p in data["params"] if p["name"] == "current")
    assert (current["default"], current["min"], current["max"], current["unit"]) == (
        "100uA",
        "1uA",
        "10mA",
        "ampere",
    )
    assert list(data) == sorted(data)


def test_stable_bytes(tmp_path: Path) -> None:
    """Scenario "Stable bytes": two processes with different hash seeds give the same text."""
    code = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('d', {str(DATA / 'divider.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "from fenolite.dsl.record import describe, record_json\n"
        "sys.stdout.write(record_json(describe(m.divider)))\n"
    )
    texts = [
        subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
            cwd=tmp_path,
        ).stdout
        for seed in ("1", "2")
    ]
    assert texts[0] == texts[1] == record_json(describe(DIVIDER)).encode("utf-8")
