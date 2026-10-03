# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DRC finding facts per major (capability kicad-oracle, "DRC finding facts proved per major"):
``H-K-DRC-TYPES``, ``H-K-PRO-SEV`` and ``H-K-DRC-UUID`` on 9.0.9 and 10.0.6, through the ``drc-*`` probes
of ``_drccases``. ``tests/kicad/test_probe_results.py`` pins the outcomes per version."""

from __future__ import annotations

import pytest
from _drccases import TYPES, pad_names, project, report
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def _slug(type_: str) -> str:
    return type_.replace("_", "-")


@pytest.mark.parametrize("type_", TYPES)
def test_types(type_: str) -> None:
    assert run(f"drc-type-{_slug(type_)}") == "present"
    assert run(f"drc-type-{_slug(type_)}-ignored") == "absent"


@pytest.mark.parametrize("type_", TYPES)
def test_severities(type_: str) -> None:
    assert run(f"drc-sev-{_slug(type_)}-warning") == "equal"
    assert run(f"drc-sev-{_slug(type_)}-error") == "equal"
    if major() >= 10:
        assert run(f"drc-ignored-checks-{_slug(type_)}") == "present"


def test_severity_reaches_the_issue() -> None:
    from fenolite.checks.drc_json import finding_issues

    found = report("shorting_items", "warning")
    assert found is not None
    issues = finding_issues(found, oracle="kicad", design=None)
    issues = tuple(i for i in issues if i.code == "kicad.drc.shorting-items")
    assert issues and all(i.severity == "warning" for i in issues)


def test_item_uuids() -> None:
    assert run("drc-item-uuids") == "equal"
    for type_, pads in (("shorting_items", ("R1-2",)), ("unconnected_items", ("R1-2", "D1-2"))):
        found = report(type_)
        assert found is not None
        names = pad_names(project(type_))
        located = {names[i.uuid] for v in found.of_type(type_) for i in v.items if i.uuid in names}
        assert set(pads) <= located
