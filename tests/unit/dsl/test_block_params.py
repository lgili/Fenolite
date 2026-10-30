# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block parameters: binding, defaults and the recorded forms (capability design-dsl, "Block parameters";
change c0251)."""

from __future__ import annotations

from typing import Any

import pytest

from fenolite.dsl import Design, DslError, amp, block, mm, to_model, volt
from fenolite.model import BlockParam

CALLS: list[str] = []


@block
def buck(b: Any, *, vout: object = volt("3.3"), current: object = amp(2)) -> None:
    CALLS.append(b.path)


def params(design: Design, path: str) -> tuple[BlockParam, ...]:
    module = next(m for m in to_model(design).circuit.modules if m.path == path)
    return module.params


def test_defaults_recorded() -> None:
    design = Design("t")
    design.use(buck, "buck1", current=amp(1))
    module = next(m for m in to_model(design).circuit.modules if m.path == "buck1")
    assert module.block == "buck"
    assert module.params == (BlockParam("current", "quantity", "1A"), BlockParam("vout", "quantity", "3.3V"))


def test_recorded_forms() -> None:
    @block
    def forms(
        b: Any, *, on: bool = True, n: int = 3, tag: str = "a", gap: object = mm(1), note: object = None
    ) -> None: ...

    design = Design("t")
    design.use(forms, "f")
    assert params(design, "f") == (
        BlockParam("gap", "length", "1000000"),
        BlockParam("n", "int", "3"),
        BlockParam("note", "none", ""),
        BlockParam("on", "bool", "true"),
        BlockParam("tag", "str", "a"),
    )


def test_unrecordable_parameter() -> None:
    CALLS.clear()
    with pytest.raises(DslError, match=r"vout.*float"):
        Design("t").use(buck, "buck1", vout=3.3)
    assert CALLS == []


def test_unrecordable_default() -> None:
    def bad(b: object, *, parts: object = ()) -> None: ...

    with pytest.raises(DslError, match=r"parts.*tuple"):
        block(bad)


def test_unknown_and_missing_parameters() -> None:
    @block
    def needs(b: Any, *, n: int) -> None: ...

    with pytest.raises(DslError, match=r"needs.*'n'.*missing"):
        Design("t").use(needs, "x")
    with pytest.raises(DslError, match=r"needs.*unknown parameter 'm'"):
        Design("t").use(needs, "x", n=1, m=2)
    design = Design("t")
    design.use(needs, "x", n=4)
    assert params(design, "x") == (BlockParam("n", "int", "4"),)


def test_plain_module_records_nothing() -> None:
    from fenolite.dsl import Module

    design = Design("t")
    design.add(Module("m"))
    module = to_model(design).circuit.modules[0]
    assert module.block == "" and module.params == ()


def test_range_recorded() -> None:
    @block
    def reg(b: Any, *, vout: object = volt("3.3").pct(3)) -> None: ...

    design = Design("t")
    design.use(reg, "r1")
    assert params(design, "r1") == (BlockParam("vout", "range", "3.3V (3.201V..3.399V)"),)
