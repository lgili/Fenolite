# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block records in the DSL (capability design-dsl, "Block records in the DSL"; capability block-library,
"Block record fields", "Block categories" and "Reserved block namespace"; change c0268)."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

from fenolite.dsl import Design, DslError, block, to_model
from fenolite.dsl.lock import needs_lock
from fenolite.dsl.record import CATEGORIES
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "blocks" / "design.py"


def body(b: Any) -> None:
    b.port("IN", direction="in")


def test_record_header() -> None:
    made = block(id="Acme:div", version="1.2.3", summary="d", licence="MIT", category="analog")(body)
    assert made.name == "Acme:div" and made.version == "1.2.3"
    header = made.header
    assert header is not None and header.namespace == "Acme" and header.pin == "Acme:div@1.2.3"
    assert (header.evidence, header.sources, header.replaces, header.deprecated) == (
        "INFERRED",
        (),
        None,
        None,
    )


@pytest.mark.parametrize("version", ["1.0", "1.0.0.0", "01.0.0", "1.a.0", "v1.0.0"])
def test_version_form(version: str) -> None:
    """Scenario "Version form"."""
    with pytest.raises(DslError, match=r"version .*MAJOR\.MINOR\.PATCH"):
        block(id="Acme:div", version=version, summary="d", licence="MIT")(body)


def test_major_stays_one() -> None:
    with pytest.raises(DslError, match="MAJOR stays 1"):
        block(id="Acme:div", version="2.0.0", summary="d", licence="MIT")(body)


def test_id_without_version() -> None:
    """Scenario "Id without version"."""
    with pytest.raises(DslError, match="id and version go together"):
        block(id="Acme:div")(body)  # type: ignore[call-overload]
    with pytest.raises(DslError, match="id and version go together"):
        block(version="1.0.0")(body)  # type: ignore[call-overload]


def test_unknown_category() -> None:
    """Scenario "Unknown category"."""
    with pytest.raises(DslError) as raised:
        block(id="Acme:div", version="1.0.0", summary="d", licence="MIT", category="sensors")(body)
    assert all(name in str(raised.value) for name in CATEGORIES) and len(CATEGORIES) == 8


def test_reserved_namespace_in_a_project() -> None:
    """Scenario "Reserved namespace in a project"."""
    with pytest.raises(DslError, match="namespace Fenolite"):
        block(id="Fenolite:mine", version="1.0.0", summary="d", sources=("S-0001",))(body)


def test_reserved_namespace_inside_the_package() -> None:
    body.__module__ = "fenolite.blocks.demo"
    try:
        made = block(id="Fenolite:mine", version="1.0.0", summary="d", sources=("S-0001",))(body)
        assert made.header is not None and made.header.licence == "Apache-2.0"
        with pytest.raises(DslError, match="Apache-2.0"):
            block(id="Fenolite:mine", version="1.0.0", summary="d", licence="MIT", sources=("S-0001",))(body)
        with pytest.raises(DslError, match="at least one source"):
            block(id="Fenolite:mine", version="1.0.0", summary="d")(body)
        with pytest.raises(DslError, match="S- id"):
            block(id="Fenolite:mine", version="1.0.0", summary="d", sources=("a book",))(body)
    finally:
        body.__module__ = __name__


def test_name_and_id_together() -> None:
    """Scenario "Name and id together"."""
    with pytest.raises(DslError, match="name or id") as raised:
        block(name="div", id="Acme:div", version="1.0.0", summary="d", licence="MIT")(body)
    assert "name" in str(raised.value) and "id" in str(raised.value)


@pytest.mark.parametrize(
    ("keywords", "named"),
    [
        ({"id": "Acme"}, "id"),
        ({"id": "Acme:a b"}, "id"),
        ({"summary": ""}, "summary"),
        ({"summary": "a\nb"}, "summary"),
        ({"summary": "x" * 121}, "summary"),
        ({"licence": None}, "licence"),
        ({"licence": "not a licence!"}, "licence"),
        ({"evidence": "TRUSTED"}, "evidence"),
        ({"sources": "S-0001"}, "sources"),
        ({"replaces": "div"}, "replaces"),
        ({"deprecated": {"by": "Acme:x"}}, "deprecated"),
        ({"deprecated": {"by": "Acme:x", "since": "1.1", "reason": "r"}}, "deprecated.since"),
    ],
)
def test_bad_header_keyword(keywords: dict[str, object], named: str) -> None:
    given: dict[str, object] = {"id": "Acme:div", "version": "1.0.0", "summary": "d", "licence": "MIT"}
    with pytest.raises(DslError, match=named):
        block(**{**given, **keywords})(body)  # type: ignore[call-overload]


def test_record_keywords_need_an_id() -> None:
    with pytest.raises(DslError, match="need an id"):
        block(summary="d")(body)  # type: ignore[call-overload]


def test_project_block_unchanged() -> None:
    """Scenario "Project block unchanged": the c0251 example has no record, so its model has no
    ``block_version`` and the design needs the lock for its refs only."""
    design: Design = runpy.run_path(str(EXAMPLE))["design"]
    texts = canonical.dump_texts(
        to_model(design, refs={p: f"X{i}" for i, p in enumerate(sorted(design.parts))})
    )
    assert "block_version" not in texts["circuit.json"]
    assert needs_lock(design)
    assert all(m.definition.header is None for m in design.modules.values() if hasattr(m, "definition"))
