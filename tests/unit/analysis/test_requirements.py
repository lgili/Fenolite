# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The requirements file (capability board-analyses, "Requirement tables supplied by the user"; c0047)."""

from __future__ import annotations

from pathlib import Path

import pytest
from _coppercheck import Copper

from fenolite.analysis.requirements import SCHEMA, load_requirements
from fenolite.core.errors import FormatError
from fenolite.model.circuit import Circuit

ROOT = Path(__file__).resolve().parents[3]
HEAD = f'schema = "{SCHEMA}"\n'
STEPS = (
    "[[step]]\nup_to_mv = 50000\ncreepage_nm = 1000000\n[[step]]\nup_to_mv = 300000\ncreepage_nm = 3000000\n"
)


def circuit(*nets: tuple[str, str | None]) -> tuple[Circuit, Copper]:
    made = Copper()
    made.netclass("Mains", None)
    for name, netclass in nets:
        made.net(name, netclass)
    return made.build().circuit, made


def pair(text: str, a: str = "L", b: str = "N") -> tuple[int | None, int | None, int | None]:
    found, made = circuit((a, None), (b, None))
    return load_requirements(text).distance_for(made.nets[a], made.nets[b], found)


def distance(millivolts: int) -> str:
    return f'[[distance]]\na = {{ net = "L" }}\nb = {{ net = "N" }}\nmillivolts = {millivolts}\n'


def test_step_lookup_without_interpolation() -> None:
    assert pair(HEAD + distance(230_000) + STEPS) == (None, 3_000_000, None)
    assert pair(HEAD + distance(50_000) + STEPS) == (None, 1_000_000, None)
    assert pair(HEAD + distance(50_001) + STEPS) == (None, 3_000_000, None)
    requirements = load_requirements(HEAD + distance(400_000) + STEPS)
    assert pair(HEAD + distance(400_000) + STEPS) == (None, None, None)
    assert requirements.values(requirements.distances[0]) is None


def test_floats_refused() -> None:
    text = HEAD + '[[current]]\nselect = { net = "VBUS" }\nmilliamps = 2.5\ntemp_rise_mk = 20000\n'
    with pytest.raises(FormatError) as info:
        load_requirements(text, file="req.toml")
    assert info.value.locator == "current[0].milliamps" and info.value.file == "req.toml"


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ('schema = "other"\n', "schema"),
        ("", "schema"),
        (HEAD + "extra = 1\n", "extra"),
        (HEAD + '[[current]]\nselect = { net = "A" }\nmilliamps = 5\n', "current[0].temp_rise_mk"),
        (HEAD + "[[current]]\nmilliamps = 5\ntemp_rise_mk = 1\n", "current[0].select"),
        (HEAD + '[[current]]\nselect = { net = "A", netclass = "B" }\nmilliamps = 5\ntemp_rise_mk = 1\n',
         "current[0].select"),
        (HEAD + '[[current]]\nselect = { ref = "A" }\nmilliamps = 5\ntemp_rise_mk = 1\n',
         "current[0].select.ref"),
        (HEAD + '[[distance]]\na = { net = "A" }\nb = { net = "B" }\n', "distance[0]"),
        (HEAD + '[[distance]]\na = { net = "A" }\nb = { net = "B" }\nmillivolts = 5\ncreepage_nm = 1\n',
         "distance[0]"),
        (HEAD + '[[distance]]\na = { net = "A" }\nb = { net = "B" }\nvolts = 5\n', "distance[0].volts"),
        (HEAD + "[[step]]\nup_to_mv = 5\n", "step[0]"),
        (HEAD + "[[step]]\nup_to_mv = -5\ncreepage_nm = 1\n", "step[0].up_to_mv"),
        (HEAD + "current = 3\n", "current"),
    ],
)  # fmt: skip
def test_malformed_documents_name_the_key(text: str, key: str) -> None:
    with pytest.raises(FormatError) as info:
        load_requirements(text, file="req.toml")
    assert info.value.locator == key


def test_invalid_toml() -> None:
    with pytest.raises(FormatError, match="not valid TOML"):
        load_requirements("schema = [", file="req.toml")


def test_largest_row_governs() -> None:
    rows = "".join(
        f'[[distance]]\na = {{ net = "{a}" }}\nb = {{ net = "{b}" }}\ncreepage_nm = {value}\n'
        for a, b, value in (("L", "N", 2_000_000), ("N", "L*", 4_000_000), ("X", "N", 9_000_000))
    )
    assert pair(HEAD + rows) == (None, 4_000_000, None)


def test_selectors_and_the_default_class() -> None:
    found, made = circuit(("L", "Mains"), ("SIG", None), ("GND", None))
    text = HEAD + (
        '[[distance]]\na = { netclass = "Mains" }\nb = { netclass = "Default" }\nclearance_nm = 3000000\n'
        '[[current]]\nselect = { net = "S*" }\nmilliamps = 100\ntemp_rise_mk = 10000\n'
        '[[current]]\nselect = { netclass = "Default" }\nmilliamps = 500\ntemp_rise_mk = 20000\n'
    )
    requirements = load_requirements(text)
    nets = made.nets
    assert requirements.distance_for(nets["L"], nets["SIG"], found) == (3_000_000, None, None)
    assert requirements.distance_for(nets["SIG"], nets["GND"], found) == (None, None, None)
    assert requirements.distance_for(nets["L"], nets["L"], found) == (None, None, None)
    governing = requirements.current_for(nets["SIG"], found)
    assert governing is not None and (governing.milliamps, governing.temp_rise_mk) == (500, 20_000)
    assert requirements.current_for(nets["L"], found) is None


def test_example_file_loads() -> None:
    path = ROOT / "tests" / "data" / "analysis" / "requirements_example.toml"
    requirements = load_requirements(path.read_text(encoding="utf-8"), file=path.name)
    assert len(requirements.currents) == 1 and len(requirements.distances) == 2
    assert [step.up_to_mv for step in requirements.steps] == [50_000, 300_000]


# --- change c0115: path rows, insulation and groove keys --------------------------------------------

PATH = (
    '[[path]]\nfrom = ["J1-1"]\nto = ["Q1-2", "Q2-2"]\n'  # one path row
    "milliamps = 20000\ntemp_rise_mk = 10000\ndrop_mv = 50\n"
)


def test_path_rows() -> None:
    """Scenario "Path rows"."""
    (row,) = load_requirements(HEAD + PATH).paths
    assert (row.start, row.end) == (("J1-1",), ("Q1-2", "Q2-2"))
    assert (row.milliamps, row.temp_rise_mk, row.drop_mv) == (20_000, 10_000, 50)
    assert load_requirements(HEAD + PATH.replace("drop_mv = 50\n", "")).paths[0].drop_mv is None
    for bad in (
        "from = []",
        'from = ["J1"]',
        'from = ["-1"]',
        'from = ["J1-"]',
        'from = "J1-1"',
        "from = [1]",
    ):
        with pytest.raises(FormatError) as caught:
            load_requirements(HEAD + PATH.replace('from = ["J1-1"]', bad), file="req.toml")
        assert caught.value.locator == "path[0].from"
    with pytest.raises(FormatError) as caught:
        load_requirements(HEAD + PATH.replace("milliamps = 20000", "milliamps = 2.5"))
    assert caught.value.locator == "path[0].milliamps"
    with pytest.raises(FormatError) as caught:
        load_requirements(HEAD + PATH + "ohms = 1\n")
    assert caught.value.locator == "path[0].ohms"
    assert load_requirements(HEAD).paths == ()
    assert load_requirements(HEAD + PATH.replace("J1-1", "J-1-A-2")).paths[0].start == ("J-1-A-2",)


def test_insulation_and_groove_keys() -> None:
    """Scenario "Insulation and groove keys"."""
    text = (
        HEAD
        + '[[distance]]\na = { net = "HV" }\nb = { net = "LV" }\n'
        + "insulation_nm = 400000\ngroove_nm = 1000000\n"
        + '[[distance]]\na = { net = "HV" }\nb = { net = "LV" }\nmillivolts = 230000\n'
        + "[[step]]\nup_to_mv = 300000\ninsulation_nm = 200000\n"
    )
    found, made = circuit(("HV", None), ("LV", None), ("X", None))
    loaded = load_requirements(text)
    hv, lv, other = made.nets["HV"], made.nets["LV"], made.nets["X"]
    assert loaded.insulation_for(hv, lv, found) == 400_000
    assert loaded.groove_for(lv, hv, found) == 1_000_000
    assert loaded.distance_for(hv, lv, found) == (None, None, None)
    assert loaded.insulation_for(hv, other, found) is None and loaded.groove_for(hv, other, found) is None
    # the step governs when it is the larger one
    larger = load_requirements(text.replace("insulation_nm = 200000", "insulation_nm = 900000"))
    assert larger.insulation_for(hv, lv, found) == 900_000
    with pytest.raises(FormatError):
        load_requirements(
            HEAD + '[[distance]]\na = { net = "HV" }\nb = { net = "LV" }\ngroove_nm = 1000000\n'
        )
    # every file of the earlier schema loads as before
    assert pair(HEAD + STEPS + distance(230_000)) == (None, 3_000_000, None)
