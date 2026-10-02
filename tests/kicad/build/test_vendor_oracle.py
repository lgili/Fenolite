# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Vendored projects and user properties pass the oracle (capability kicad-oracle, "Vendored projects and
user properties pass the oracle"; hypotheses H-K-VENDOR-GLOBAL, -SHADOW, -PROPS and -DUPNAME; change
c0027), on builds made by ``build_design(vendor=…)``. Configuration folders reach ``kicad-cli`` only as the
``KICAD_CONFIG_HOME`` entry of ``KicadCli.run``."""

from __future__ import annotations

import _vendorcases as vc
import pytest
from _buildcases import upgraded

from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


def _report(files: dict[str, str | bytes], **kwargs: object) -> tuple[int, int]:
    found = vc.counts(vc.drc(files, **kwargs))  # type: ignore[arg-type]
    assert found is not None, "kicad-cli wrote no DRC report"
    return found


@pytest.mark.parametrize("target", TARGETS)
def test_global_vendored(target: int) -> None:
    assert _report(vc.built_files(target, "project")) == (len(vc.USED), 0)
    assert _report(vc.built_files(target, "all")) == (0, 0)


@pytest.mark.parametrize("target", TARGETS)
def test_shadow(target: int) -> None:
    alt = vc.bench().config_alt
    assert _report(vc.built_files(target, "project"), config=alt) == (0, 1), (
        "control: the global table was read"
    )
    assert _report(vc.built_files(target, "all"), config=alt) == (0, 0)


@pytest.mark.parametrize("target", TARGETS)
def test_hidden_items(target: int) -> None:
    config = vc.bench().config
    assert _report(vc.built_files(target, "project"), config=config) == (0, 0), "control"
    hidden = vc.drc(vc.without(vc.built_files(target, "all"), "Mini_LED_THT_3mm"), config=config)
    assert hidden is not None
    issues = [v for v in hidden.violations if v.type == "lib_footprint_issues"]
    assert vc.counts(hidden) == (1, 0) and any(i.description == "Footprint D1" for i in issues[0].items)


@pytest.mark.parametrize("target", TARGETS)
def test_user_properties(target: int) -> None:
    files = vc.built_files(target, "all", properties=True)
    assert _report(files) == (0, 0)
    if vc.major() < 10:
        return
    back = {c.ref: c.properties for c in read_board(upgraded(files, vc.BOARD)).circuit.components}
    for ref, props in vc.PROPERTIES.items():
        assert {k: back[ref].get(k) for k in props} == dict(props)
    text = upgraded(files, vc.BOARD)
    nodes = vc._user_nodes(text)  # noqa: SLF001
    for ref, props in vc.PROPERTIES.items():
        for key in props:
            (node,) = [p for p in nodes[ref] if p.atoms()[0].value == key]
            assert node.find("hide") is not None


@pytest.mark.kicad_min_major(10)
def test_duplicate_field_name() -> None:
    assert vc.dupname_case() == "present"
