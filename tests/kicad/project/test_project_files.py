# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project files survive kicad-cli runs (capability kicad-oracle, "Project files survive kicad-cli runs";
hypothesis H-K-PRO-PRL; change c0010): ``pcb drc`` and ``pcb export svg`` on the target-9 bench set,
judged from ``CliRun.outputs``, the files each run created or changed in its temporary copy."""

from __future__ import annotations

import _procases as pc
import pytest
from _probes import major, run

pytestmark = pytest.mark.needs_kicad


def test_prl_and_pro() -> None:
    runs = pc.file_runs()
    for name, result in runs.items():
        assert result.ok, f"{name}: {result.stderr}"
        assert pc.PROJECT not in result.outputs, f"kicad-cli {name} rewrote the project file"
        assert run(f"pro-file-{name}") == "equal"
        prl = "present" if pc.PRL in result.outputs else "absent"
        print(f"KiCad {major()}: {name} {'writes' if prl == 'present' else 'does not write'} bench.kicad_prl")
        assert run(f"pro-prl-{name}") == prl
