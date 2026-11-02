# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""New drawn effects remain explicit Altium losses; no native-application claim (c0326)."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import _drawn
import pytest
from _buildhelp import LIBS, project

from fenolite import api
from fenolite.core.coords import Point, Size
from fenolite.lens.drawn import write_drawn
from fenolite.model.drawn import DrawnField, DrawnFont, DrawnSchematic, DrawnSheetProperty

CASES = (
    "field-font",
    "field-false-zero",
    "power-font",
    "local-font",
    "global-font",
    "hierarchical-font",
    "label-justify",
    "pin-font",
    "pin-justify",
    "sheet-pose",
    "sheet-font",
    "sheet-property",
)


def _styled(case: str) -> tuple[DrawnSchematic, str]:
    value = _drawn.drawn("full")
    root = value.sheets[0]
    font = DrawnFont(Size(500_000, 750_000), bold=True)
    if case.startswith("field-"):
        symbol = root.symbols[0]
        field = symbol.fields[-1]
        if case == "field-false-zero":
            font = DrawnFont(thickness=0, bold=False, italic=False)
        fields = (*symbol.fields[:-1], dataclasses.replace(field, font=font))
        root = dataclasses.replace(
            root, symbols=(dataclasses.replace(symbol, fields=fields), *root.symbols[1:])
        )
        where = f"root.symbol[0].fields.{field.name}.font"
    elif case == "power-font":
        power = root.powers[0]
        field = DrawnField("Value", Point(power.at.x, power.at.y + 2_540_000), font=font)
        root = dataclasses.replace(root, powers=(dataclasses.replace(power, fields=(field,)),))
        where = "root.power[0].fields.Value.font"
    elif case in {"pin-font", "pin-justify", "sheet-pose", "sheet-font", "sheet-property"}:
        ref = root.sheet_refs[0]
        if case == "sheet-property":
            ref = dataclasses.replace(ref, properties=(DrawnSheetProperty("Field2", "Authored", ref.at),))
            where = "root.sheet_ref.sub.properties.Field2"
        elif case.startswith("pin-"):
            pin = ref.pins[0]
            pin = (
                dataclasses.replace(pin, font=font)
                if case == "pin-font"
                else dataclasses.replace(pin, justify="")
            )
            ref = dataclasses.replace(ref, pins=(pin, *ref.pins[1:]))
            where = "root.sheet_ref.sub.pin[0]." + ("font" if case == "pin-font" else "justify")
        else:
            field = DrawnField("Sheetname", ref.at, font=font if case == "sheet-font" else None)
            ref = dataclasses.replace(ref, fields=(field,))
            where = "root.sheet_ref.sub.fields.Sheetname"
        root = dataclasses.replace(root, sheet_refs=(ref,))
    else:
        kind = "local" if case == "label-justify" else case.removesuffix("-font")
        index, sheet = next(
            (index, sheet)
            for index, sheet in enumerate(value.sheets)
            if any(label.kind == kind for label in sheet.labels)
        )
        k = next(k for k, label in enumerate(sheet.labels) if label.kind == kind)
        label = sheet.labels[k]
        label = (
            dataclasses.replace(label, justify="")
            if case == "label-justify"
            else dataclasses.replace(label, font=font)
        )
        sheet = dataclasses.replace(
            sheet, labels=tuple(label if i == k else old for i, old in enumerate(sheet.labels))
        )
        path = "root" if index == 0 else "sub"
        where = f"{path}.label[{k}]." + ("justify" if case == "label-justify" else "font")
        return dataclasses.replace(
            value, sheets=tuple(sheet if i == index else old for i, old in enumerate(value.sheets))
        ), where
    return dataclasses.replace(value, sheets=(root, *value.sheets[1:])), where


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("form", ("binary", "ascii"))
def test_unproved_styles_require_explicit_loss(case: str, form: str, tmp_path: Path) -> None:
    source = tmp_path / "source"
    shutil.copytree(_drawn.folder("full"), source)
    project(source, {"Mini": str(LIBS / "Mini_v9.pretty")}, {"Mini": str(LIBS / "Mini_v9.kicad_sym")})
    value, where = _styled(case)
    (source / "schematic.toml").write_text(write_drawn(value), encoding="utf-8")
    args = (str(source / "design.py"), "--out", "out", "--target", "altium", "--altium-format", form)
    strict = api.run("build", *args, "--dry-run", cwd=tmp_path, seed=0)
    assert strict.exit_code == 7 and strict.error and strict.error["code"] == "FEN-7001", (
        strict.error,
        strict.result,
    )
    assert where in strict.error["message"]
    assert not strict.result.get("plan") and not (tmp_path / "out").exists()
    allowed = api.run("build", *args, "--allow-lossy", "--dry-run", cwd=tmp_path, seed=0)
    assert allowed.exit_code == 0, allowed.error
    assert any(item["path"].endswith(".SchDoc") for item in allowed.result["plan"])
    assert allowed.envelope is not None
    found = [
        issue
        for issue in allowed.envelope["issues"]
        if issue["code"] == "altium.not-lowered" and issue["where"] == where
    ]
    assert len(found) == 1 and found[0]["severity"] == "info"
    assert allowed.envelope["evidence"]["level"] == "INFERRED"
    assert "H-A-DRAWN-WRITE" in allowed.envelope["evidence"]["hypotheses"]
    assert not (tmp_path / "out").exists()
