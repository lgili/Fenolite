# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0264: the authored local import adds no ERC/DRC finding versus its plain definition control."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

import pytest
from _kicad import cli, supported_version

from fenolite.api import run

pytestmark = pytest.mark.needs_kicad
EXAMPLE = Path(__file__).resolve().parents[3] / "examples/library_import"


@pytest.mark.parametrize("target", [pytest.param(10, marks=pytest.mark.kicad_min_major(10)), 9])
def test_imported_device_has_no_new_erc_or_drc_findings(
    tmp_path: Path, target: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    supported_version()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "isolated-config"))
    imported, plain = tmp_path / "imported", tmp_path / "plain"
    shutil.copytree(EXAMPLE, imported)
    shutil.copytree(EXAMPLE, plain)
    (plain / "devices/Imported/EXB6202/device.toml").unlink()
    script = plain / "design.py"
    script.write_text(
        script.read_text().replace(
            'device="Imported:EXB6202"', 'lib_id="Imported:EXB6202", footprint="Imported:EXB6202"'
        )
    )

    def findings(folder: Path, output: str) -> Counter[str]:
        built = run(
            "build",
            str(folder / "design.py"),
            "--out",
            output,
            "--confirm",
            "--kicad-version",
            str(target),
            cwd=tmp_path,
        )
        assert built.exit_code == 0, built.error
        checked = run("check", output, "--kicad-cli", cli(), cwd=tmp_path)
        assert checked.exit_code in (0, 5), checked.error
        assert checked.envelope is not None
        return Counter(
            issue["code"]
            for issue in checked.envelope["issues"]
            if issue["code"].startswith(("kicad.erc.", "kicad.drc."))
        )

    assert not findings(imported, "out-imported") - findings(plain, "out-plain")
