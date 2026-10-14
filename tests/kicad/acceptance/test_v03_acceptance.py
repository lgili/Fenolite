# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""H-A-ACC-V03: full acceptance on the CI KiCad 10 importer; never a prepared-only pass."""

import importlib.util
import json
from pathlib import Path

import pytest
from _resources import kicad_cli

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10)]
ROOT = Path(__file__).resolve().parents[3]


def test_v03_acceptance(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "acceptance_v03_oracle", ROOT / "tools" / "acceptance_v03.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cli = kicad_cli()
    assert cli is not None
    result = module.run(tmp_path / "acceptance", kicad_cli=str(cli))
    assert result["acceptance_complete"], json.dumps(result, indent=2)
    assert all(step["passed"] for step in result["steps"])
