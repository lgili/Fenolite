# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parameter metadata and port documentation of blocks (capability design-dsl, "Block parameter metadata"
and "Port documentation"; change c0268)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from fenolite.dsl import REQUIRED, Design, DslError, Rail, block, describe, mm, param, to_model
from fenolite.dsl.quantity import amp, volt
from fenolite.dsl.units import Length

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "blocks"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"_c0268_{name}", DATA / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    exec(compile(Path(spec.origin).read_bytes(), spec.origin, "exec"), module.__dict__)
    return module


DIVIDER = load("divider").divider


def test_param_unwrapped() -> None:
    assert DIVIDER.keywords["current"] == amp("100u")
    meta = DIVIDER.params["current"]
    assert (meta.doc, meta.unit, meta.min, meta.max) == (
        "bias current at nominal input",
        "ampere",
        amp("1u"),
        amp("10m"),
    )
    assert DIVIDER.params["series"].choices == ("E24", "E96")


def test_value_outside_the_range() -> None:
    """Scenario "Value outside the range": refused before the function runs."""
    design = Design("d")
    with pytest.raises(DslError) as raised:
        design.use(DIVIDER, "d1", current=amp("20m"))
    assert all(text in str(raised.value) for text in ("current", "20mA", "1uA to 10mA"))
    assert design.modules == {}


def test_wrong_unit() -> None:
    """Scenario "Wrong unit"."""
    with pytest.raises(DslError) as raised:
        Design("d").use(DIVIDER, "d1", current=volt(1))
    assert all(text in str(raised.value) for text in ("current", "volt", "amp"))


def test_range_ends_are_checked() -> None:
    with pytest.raises(DslError, match="outside the range"):
        Design("d").use(DIVIDER, "d1", current=amp("5m").pct(300))
    Design("d").use(DIVIDER, "d1", current=amp("5m").pct(10))


def test_not_a_choice() -> None:
    with pytest.raises(DslError, match="not one of the choices E24, E96"):
        Design("d").use(DIVIDER, "d1", series="E12")


def test_default_not_a_choice() -> None:
    """Scenario "Default not a choice"."""
    with pytest.raises(DslError) as raised:

        @block
        def bad(b: Any, *, series: object = param("E12", choices=("E24", "E96"))) -> None: ...

    assert "series" in str(raised.value) and "E24, E96" in str(raised.value)


@pytest.mark.parametrize(
    ("made", "message"),
    [
        (lambda: param(amp("1"), unit="volt"), "differs from the unit"),
        (lambda: param(amp("1"), unit="furlong"), "unit 'furlong'"),
        (lambda: param(amp("1"), min=volt(1)), "not in the unit ampere"),
        (lambda: param(amp("1"), min=amp("2"), max=amp("1")), "above max"),
        (lambda: param(amp("1"), min=amp("2")), "outside at least 2A"),
        (lambda: param(3, min=mm(1)), "type of the default"),
        (lambda: param("a", choices=("a",)), "two distinct"),
        (lambda: param("a", choices=("a", 1)), "one type"),
        (lambda: param(1, doc="x\ny"), "doc"),
        (lambda: param(1, doc="x" * 201), "doc"),
        (lambda: param(object()), "cannot be recorded"),
    ],
)
def test_bad_metadata(made: Any, message: str) -> None:
    with pytest.raises(DslError, match=message):

        @block
        def bad(b: Any, *, value: object = made()) -> None: ...


def test_required_and_length_metadata() -> None:
    @block
    def sized(
        b: Any,
        *,
        width: object = param(REQUIRED, unit="length", min=mm(1), max=mm(5)),
        n: object = param(doc="count"),
    ) -> None: ...

    assert sized.params["width"].type == "length" and sized.params["n"].type == "any"
    design = Design("d")
    with pytest.raises(DslError, match="width"):
        design.use(sized, "a", n=1)
    with pytest.raises(DslError, match="the unit is length"):
        design.use(sized, "a", width=3, n=1)
    with pytest.raises(DslError, match="6mm is outside the range 1mm to 5mm"):
        design.use(sized, "a", width=mm(6), n=1)
    design.use(sized, "a", width=Length(2_000_000), n=1)


def test_port_doc_in_the_record() -> None:
    """Scenario "Port doc in the record": the record has it, the model's port has no doc field."""
    record = describe(DIVIDER)
    assert {port.name: port.doc for port in record.ports or ()}["HI"] == "input"
    design = Design("d")
    design.use(DIVIDER, "d1")
    model = to_model(design, refs={"d1/top": "R1", "d1/bot": "R2"})
    port = next(p for p in model.circuit.ports if p.name == "HI")
    assert not hasattr(port, "doc")


def test_port_doc_is_one_line() -> None:
    @block
    def noisy(b: Any) -> None:
        b.port("A", Rail, direction="in", doc="a\nb")

    with pytest.raises(DslError, match="one line"):
        Design("d").use(noisy, "n")
