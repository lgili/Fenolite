# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DRC reports are strict JSON (capability kicad-oracle, "DRC verdicts come from the JSON report";
hypothesis H-K-DRC-JSON; change c0017)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NoReturn

import _triad
import pytest
from _probes import major, run, runner

from fenolite.backends.kicad.cli import DRC_REPORT
from fenolite.backends.kicad.drc import REQUIRED_KEYS, read_drc_report

pytestmark = pytest.mark.needs_kicad


def _refuse(name: str) -> NoReturn:
    raise ValueError(f"{name} in a DRC report")


def test_drc_json_strict(tmp_path: Path) -> None:
    board = _triad.write(_triad.triad(major()), major(), tmp_path)
    drc = runner().drc(board, files=_triad.project(board))
    raw = drc.run.outputs[DRC_REPORT].decode("utf-8")
    data = json.loads(raw, parse_constant=_refuse)
    assert set(REQUIRED_KEYS) <= set(data)
    assert read_drc_report(raw) == drc.report
    assert run("pcb-drc-ignored-checks") == ("present" if "ignored_checks" in data else "absent")
