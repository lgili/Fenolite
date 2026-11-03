# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project curve configuration is exact, managed and visibly compared (c0340)."""

from __future__ import annotations

import dataclasses

import pytest

from fenolite.backends.kicad import pro
from fenolite.backends.kicad._json import JsonNumber
from fenolite.checks.equivalence.rules import level_rules
from fenolite.core.errors import FormatError
from fenolite.dsl import Design, mm, to_model


def authored(error: str | None = None):
    design = Design("authored_geometry")
    design.board(mm(30), mm(20), max_curve_error=mm(error) if error is not None else None)
    return to_model(design)


@pytest.mark.parametrize("target", (9, 10))
def test_explicit_curve_error_writes_and_reads_native_project(target: int) -> None:
    design = authored("0.01")
    text = pro.synthesize_project(design, board_name="authored_geometry", target=target)
    data = pro.read_project_text(text)
    assert data["board"]["design_settings"]["rules"]["max_error"] == JsonNumber("0.01")
    read = pro.apply_project(authored(), pro.read_project(text, file="authored.kicad_pro"))
    assert read.board is not None and read.board.max_curve_error == 10_000


@pytest.mark.parametrize("target", (9, 10))
@pytest.mark.parametrize("missing", (False, True))
def test_proved_native_default_is_effective_absence(target: int, missing: bool) -> None:
    data = pro.template(target)
    if missing:
        data["board"]["design_settings"]["rules"].pop("max_error")
    read = pro.apply_project(authored(), pro.read_project(pro.write_project_text(data)))
    assert read.board is not None and read.board.max_curve_error is None


def test_update_manages_only_requested_setting_and_keeps_equal_number_spelling() -> None:
    data = pro.template(10)
    data["board"]["design_settings"]["rules"]["max_error"] = JsonNumber("0.010000")
    data["authored_unknown_setting"] = {"kept": True}
    text = pro.write_project_text(data)
    output = pro.update_project(text, authored("0.01"), target=10)
    after = pro.read_project_text(output)
    assert after["board"]["design_settings"]["rules"]["max_error"] == JsonNumber("0.010000")
    assert after["authored_unknown_setting"] == {"kept": True}
    unchanged = pro.update_project(text, authored(), target=10)
    assert pro.read_project_text(unchanged)["board"]["design_settings"]["rules"]["max_error"] == JsonNumber(
        "0.010000"
    )


@pytest.mark.parametrize(
    "value", (None, True, False, "0.01", JsonNumber("0"), JsonNumber("-0.01"), JsonNumber("0.0000001"))
)
def test_malformed_project_curve_error_refuses_with_pointer(value: object) -> None:
    data = pro.template(10)
    data["board"]["design_settings"]["rules"]["max_error"] = value
    with pytest.raises(FormatError) as caught:
        pro.read_project(pro.write_project_text(data), file="authored.kicad_pro")
    assert caught.value.file == "authored.kicad_pro"
    assert caught.value.locator == "/board/design_settings/rules/max_error"


def test_curve_configuration_is_compared_at_level6() -> None:
    one, other = authored("0.01"), authored("0.02")
    result = level_rules(one, other)
    assert [(found.kind, found.where, found.field, found.a, found.b) for found in result.differences] == [
        ("rule-field", "board", "max_curve_error", "10000", "20000")
    ]
    assert result.summary["project_geometry"] == 1
    default = level_rules(authored(), authored())
    assert "project_geometry" not in default.summary
    assert default.differences == ()
    assert one.board is not None
    exact_copy = dataclasses.replace(one, board=dataclasses.replace(one.board))
    assert level_rules(one, exact_copy).differences == ()
