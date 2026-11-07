# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""3D model references of a part (capability design-dsl, "3D model references in the DSL"; change c0277):
``Part.model`` names models for the part's footprint instance, the build writes them in place of the
footprint's own, and nothing is read."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.dsl import DslError, Part, mm
from fenolite.model.board import ModelRef

NAME = "${KICAD10_3DMODEL_DIR}/Package_SO.3dshapes/SOIC-8.step"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_model_by_name_in_the_part() -> None:
    """Scenario "Model by name" (the record)."""
    u1 = Part("U1", "Mini:Mini_QFP32_IC")
    u1.model(NAME, offset=(mm(0), mm(0), mm("0.1")))
    assert u1.model_refs == [ModelRef(NAME, (0, 0, 100_000))]
    for bad, word in (({"offset": (1, 0, 0)}, "offset"), ({"scale": ("1", "0", "1")}, "scale"),
                      ({"hidden": "no"}, "hidden"), ({"rotation": (0, 0)}, "rotation")):  # fmt: skip
        with pytest.raises(DslError, match=word):
            u1.model(NAME, **bad)  # type: ignore[arg-type]
    with pytest.raises(DslError, match="name"):
        u1.model("")


@pytest.mark.parametrize("target", [9, 10])
def test_model_by_name_in_the_build(tmp_path: Path, target: int) -> None:
    """Scenario "Model by name": the instance holds the reference, the board writes it in place of the
    footprint's models, and the model file is never opened (it does not exist)."""
    lines = (
        f'u1.model("{NAME}", offset=(mm(0), mm(0), mm("0.1")))\n'
        'u1.model("3dmodels/cap.step", rotation=(0, 0, 90), scale=("1", "1", "2"), hidden=True)\n'
    )
    script = blink_variant(tmp_path / "src", append=lines)
    out = tmp_path / "out"
    args = ("build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm")
    reply = run(*args, cwd=script.parent, timestamp="2026-10-30T00:00:00Z")
    assert reply.exit_code == 0, reply.error
    first = (out / "blink.kicad_pcb").read_bytes()
    root = parse(first.decode("utf-8"))

    def ref(fp) -> str:  # noqa: ANN001
        return next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference")

    u1 = next(fp for fp in root.nodes("footprint") if ref(fp) == "U1")
    models = [dumps(m, style="compact") for m in u1.nodes("model")]
    assert models == [
        f'(model "{NAME}" (offset (xyz 0 0 0.1)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))',
        '(model "3dmodels/cap.step" (hide yes) (offset (xyz 0 0 0)) (scale (xyz 1 1 2))'
        " (rotate (xyz 0 0 -90)))",
    ]
    assert run(*args, cwd=script.parent, timestamp="2026-10-30T00:00:00Z").exit_code == 0
    assert (out / "blink.kicad_pcb").read_bytes() == first
