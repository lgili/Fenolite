# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library table rules settled by ``kicad-cli`` (capability kicad-oracle, "Library table probes"; change
c0021): relative uris, the versioned fallback, nested tables, the configuration folder of the major and
the path variables of ``kicad_common.json`` (``H-K-LIB-RELPATH-2``, ``-FALLBACK``, ``-NESTED``,
``-CONFIGHOME``, ``-COMMON``).

The 10.0.6 criteria are asserted here. On 9.0.9 only ``test_nested`` asserts; every other 9.0.9 outcome is
pinned by ``tests/kicad/test_probe_results.py``.
"""

from __future__ import annotations

from pathlib import Path

import _libtables
import pytest
from _boards import census
from _probes import major, run, runner

pytestmark = pytest.mark.needs_kicad


def _expect(layout: str, wanted: str) -> None:
    found = run(_libtables.probe_id(layout))
    if found == "inconclusive":
        pytest.fail(
            f"{_libtables.probe_id(layout)}: the library check reported nothing for a board without a "
            "table, so no library probe can be judged (H-K-LIB-DRC)",
            pytrace=False,
        )
    if major() >= 10:
        assert found == wanted, _libtables.probe_id(layout)


def test_relpath() -> None:
    """A relative uri resolves against the working directory of ``kicad-cli``, in a project, a nested and
    a global table; neither the folder of the table nor the project folder counts
    (``H-K-LIB-RELPATH-2``)."""
    _expect("relpath-project", "absent")
    _expect("relpath-nested", "absent")
    _expect("relpath-nested-folder", "present")
    _expect("relpath-global", "absent")
    _expect("relpath-cwd", "absent")
    _expect("relpath-project-folder", "present")


def test_fallback() -> None:
    _expect("fallback", "absent")
    _expect("fallback-defined", "present")


def test_nested() -> None:
    found = run(_libtables.probe_id("nested"))
    assert found != "inconclusive", "the library check reported nothing (H-K-LIB-DRC)"
    # 10.0 expands a nested table; 9.0 does not read `Table` rows
    assert found == ("absent" if major() >= 10 else "present")


def test_config_home() -> None:
    _expect("confighome", "absent")
    _expect("confighome-flat", "present")


def test_common_vars() -> None:
    _expect("common", "absent")
    _expect("common-env", "present")


def test_common_file_layout(tmp_path: Path) -> None:
    """An observation: what ``kicad-cli`` writes into an empty configuration folder (key names only)."""
    config = tmp_path / "config"
    config.mkdir()
    seen = _libtables.observe_common(runner(), config, tmp_path / "work")
    census("libtables", f"common-layout-{major()}", seen)
