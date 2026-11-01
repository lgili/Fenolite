# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Post-build family facts keep reviewed project precedence and ignore proposed candidates."""

import dataclasses
from importlib import resources

from fenolite.cli._contracts import devices_of
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

ID = "Fenolite:R_0603_E96_1pct@137k"


def model():
    return dataclasses.replace(
        Design.new("family_facts", seed=0),
        circuit=Circuit(components=(Component(id="r", ref="R1", properties={"fenolite.device": ID}),)),
    )


def family(summary):
    # Only an authored description changes; all public electrical facts remain intact.
    text = resources.files("fenolite.catalog").joinpath("families/r_0603_e96_1pct.toml").read_text()
    return (
        "\n".join(
            f'summary = "{summary}"' if line.startswith("summary =") else line for line in text.splitlines()
        )
        + "\n"
    )


def test_reviewed_parent_then_nearer_project_facts(tmp_path):
    build = tmp_path / "out"
    parent = tmp_path / "devices"
    parent.mkdir()
    (parent / "r.toml").write_text(family("Authored parent override"))
    assert devices_of(model(), build)[ID].summary.startswith("Authored parent override")
    near = build / "devices"
    near.mkdir(parents=True)
    (near / "r.toml").write_text(family("Authored nearby override"))
    assert devices_of(model(), build)[ID].summary.startswith("Authored nearby override")


def test_proposed_family_is_not_a_source_of_check_facts(tmp_path):
    build = tmp_path / "out"
    proposed = build / "devices/proposed"
    proposed.mkdir(parents=True)
    (proposed / "r.toml").write_text(family("Unreviewed candidate"))
    found = devices_of(model(), build)[ID]
    assert found.summary.startswith("Generic thick-film chip resistor, 0603")
