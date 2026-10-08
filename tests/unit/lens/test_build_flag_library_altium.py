# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium build of the design of change c0143 (capability kicad-schematic, "Generated sheet content",
scenario "Altium build unchanged"): catalog parts and a ``Power`` interface. The KiCad build of the design
is in ``test_build_flag_library.py``; this file needs ``build_altium`` with ``authored_symbols`` (change
c0086), which the releases 0.2.x do not have."""

from __future__ import annotations

import pytest
from _buildhelp import resolver
from _flagdesign import catalog_definitions, regulator_design

from fenolite.backends.kicad import symembed
from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_the_altium_build_does_not_change(form: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Altium build unchanged": an Altium build writes no flag, so the choice of the flag's
    library reaches none of its files."""

    def altium() -> dict[str, bytes]:
        design = regulator_design()
        output = build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            form=form,  # type: ignore[arg-type]
            resolver=resolver(10),
            **catalog_definitions(),  # type: ignore[arg-type]
        )
        assert [issue.code for issue in output.issues if issue.severity == "error"] == []
        return dict(output.files)

    files = altium()
    assert files and not [name for name in files if "PWR_FLAG" in files[name].decode("latin-1")]
    monkeypatch.setattr(symembed, "flag_library", lambda libraries: symembed.FLAG_LIBRARY)
    assert altium() == files
