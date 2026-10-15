# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""H-A-ACC-V03: one cached complete acceptance for the test and versioned probe."""

from __future__ import annotations

import importlib.util
import tempfile
from functools import cache
from pathlib import Path
from typing import Any

from _resources import kicad_cli

ROOT = Path(__file__).resolve().parents[3]


@cache
def result() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "acceptance_v03_probe", ROOT / "tools" / "acceptance_v03.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("the v0.3 acceptance runner is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cli = kicad_cli()
    if cli is None:
        raise RuntimeError("the complete acceptance needs kicad-cli 10")
    with tempfile.TemporaryDirectory(prefix="fenolite-acceptance-v03-") as folder:
        return module.run(Path(folder) / "acceptance", kicad_cli=str(cli))


def outcome() -> str:
    measured = result()
    return (
        "equal"
        if measured.get("passed") and measured.get("acceptance_complete") and measured.get("mode") == "full"
        else "different"
    )
