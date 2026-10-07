# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which ``rule_severities`` keys KiCad applies, and a script's severity in KiCad's report
(``H-K-PRO-SEV-KEYS``; capability kicad-oracle, "Severity keys are probed"; change c0114).

10.0.6 lists the checks it ignores, so its key set is read from a run. 9.0.9 lists nothing: there the
claim is only that the keys of the packaged template silence every check the bench fires.
"""

from __future__ import annotations

import _exclcases as ex
import pytest
from _probes import major, run

from fenolite.backends.kicad.pro import SEVERITY_KEYS

pytestmark = pytest.mark.needs_kicad
ALL = {*ex.BENCH_TYPES, "lib_footprint_issues"}


def test_keys_control_fires_every_bench_check() -> None:
    """The control of both key probes: under a ``{}`` project the bench has an entry of each check."""
    assert ex.bench_types(ex.report(ex.project_text(), "severity")) == ALL


def test_keys_of_major_10() -> None:
    """``pro-sev-keys-10``: every template key at ``ignore``, with two keys outside the template."""
    if major() != 10:
        pytest.skip("10.0 lists its ignored checks; 9.0 lists none")
    project = ex.all_ignored(10, *ex.UNKNOWN_KEYS)
    assert set(ex.ignored_checks(project)) == set(SEVERITY_KEYS[10])
    assert len(SEVERITY_KEYS[10]) == 62 and not set(ex.UNKNOWN_KEYS) & set(ex.ignored_checks(project))
    found = ex.report(project, "severity")
    assert not found.violations and not found.unconnected_items  # no entry remains
    assert run("pro-sev-keys-10") == "equal"


def test_keys_of_major_9_on_the_bench() -> None:
    """``pro-sev-keys-9-bench``: the template keys silence every check the bench fires."""
    if major() != 9:
        pytest.skip("the bench claim is that of 9.0, whose report lists no ignored check")
    assert not ex.bench_types(ex.report(ex.all_ignored(9), "severity"))
    assert run("pro-sev-keys-9-bench") == "absent"


# --- a script's severity (task 5.2) ---------------------------------------------------------------


def test_script_severity_reaches_the_report() -> None:
    """``pro-sev-script``: the severity of the script, written by the project writer, is the severity of
    KiCad's entry."""
    assert [entry.severity for entry in ex.via_entries(ex.triad_report(False))] == ["warning"]
    assert [entry.severity for entry in ex.via_entries(ex.triad_report(True))] == ["error"]
    assert run("pro-sev-script") == "equal"
