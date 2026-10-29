# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``generate``, ``Generated`` and the family keys (change c0260, requirements "Public per-family footprint
generators", "Family parameter keys", "Nominal density only", "Dimension consistency findings")."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from _package_records import PACKAGES, RECORDS, raw_record

from fenolite.catalog.footprints import Generated, generate, read_package
from fenolite.catalog.footprints.record import FAMILIES, Package, package_from
from fenolite.core.errors import FormatError

Record = Callable[..., Package]


def test_a_gullwing_record_is_drawn() -> None:
    text = (PACKAGES / "soic8.toml").read_text(encoding="utf-8")
    first, second = generate(read_package(text)), generate(read_package(text))
    assert isinstance(first, Generated) and first == second
    assert first.footprint is not None
    assert [pad.number for pad in first.footprint.pads] == [str(n) for n in range(1, 9)]
    assert not [i for i in first.issues if i.severity == "error"]
    assert generate(text) == first  # the text itself is read too


def test_every_family_has_a_test_record() -> None:
    families = {raw_record(stem)["family"] for stem in RECORDS}
    assert families == set(FAMILIES)


@pytest.mark.parametrize("stem", RECORDS)
def test_generation_is_pure_and_repeatable(stem: str, record: Record) -> None:
    assert generate(record(stem)) == generate(record(stem))


def test_unknown_family() -> None:
    raw = raw_record("soic8")
    raw["family"] = "spiral"
    with pytest.raises(FormatError) as raised:
        package_from(raw, file="spiral.toml")
    assert raised.value.locator == "family" and raised.value.file == "spiral.toml"


def test_generator_key_of_c0259_is_read(record: Record) -> None:
    def rename(raw: dict[str, Any]) -> None:
        raw["generator"] = raw.pop("family")

    assert record("soic8", rename).family == "gullwing"
    with pytest.raises(FormatError, match="disagree"):
        record("soic8", lambda raw: raw.update(generator="nolead"))


def test_missing_pitch(record: Record) -> None:
    with pytest.raises(FormatError) as raised:
        record("soic8", lambda raw: raw.pop("pitch"))
    assert raised.value.locator == "pitch"


@pytest.mark.parametrize(
    ("edit", "locator"),
    [
        (lambda raw: raw.update(colour="red"), "colour"),
        (lambda raw: raw["lead"].update(foot="1mm"), "lead.foot"),
        (lambda raw: raw.update(pins="8"), "pins"),
        (lambda raw: raw.update(pitch=Decimal_like()), "pitch"),
        (lambda raw: raw.update(arrangement="triple"), "arrangement"),
        (lambda raw: raw["generate"].pop("drawing"), "generate.drawing"),
        (lambda raw: raw.pop("generate"), "generate"),
        (lambda raw: raw["land"].pop("source"), "land.source"),
        (lambda raw: raw.update(evidence="PROVEN"), "evidence"),
        (lambda raw: raw.update(name="SOIC 8"), "name"),
        (lambda raw: raw.update(schema="fenolite.package.v9"), "schema"),
    ],
)
def test_wrong_keys_name_the_key(
    record: Record, edit: Callable[[dict[str, Any]], None], locator: str
) -> None:
    with pytest.raises(FormatError) as raised:
        record("soic8", edit)
    assert raised.value.locator == locator


def Decimal_like() -> object:  # noqa: N802 - a bare TOML number
    from decimal import Decimal

    return Decimal("1.27")


def test_calculator_without_a_table_version(record: Record) -> None:
    def calculated_without_version(raw: dict[str, Any]) -> None:
        raw.pop("land")
        raw["generate"].pop("lands")

    with pytest.raises(FormatError) as raised:
        record("soic8", calculated_without_version)
    assert raised.value.locator == "generate.lands"
    # With a [land] the version is not needed.
    assert generate(record("soic8", lambda raw: raw["generate"].pop("lands"))).footprint is not None


def test_unreleased_versions(record: Record) -> None:
    with pytest.raises(FormatError, match="lands/7"):
        generate(record("chip0603", lambda raw: raw["generate"].update(lands=7)))
    with pytest.raises(FormatError, match="drawing/9"):
        generate(record("soic8", lambda raw: raw["generate"].update(drawing=9)))


@pytest.mark.parametrize("density", ["compact", "robust"])
def test_reserved_density(record: Record, density: str) -> None:
    with pytest.raises(FormatError, match=f"{density}' is reserved"):
        generate(record("soic8"), density=density)
    with pytest.raises(FormatError, match="reserved"):
        record("soic8", lambda raw: raw["generate"].update(density=density))
    with pytest.raises(FormatError, match="not known"):
        generate(record("soic8"), density="dense")


def test_span_inside_the_body(record: Record) -> None:
    result = generate(record("soic8", lambda raw: raw.update(span="3.0mm..3.5mm")))
    assert result.footprint is None
    errors = [i for i in result.issues if i.severity == "error"]
    assert [i.code for i in errors] == ["package.dimensions-inconsistent"]
    assert errors[0].where.endswith(":span")


def test_pin_count_and_row_length(record: Record) -> None:
    odd = generate(record("soic8", lambda raw: raw.update(pins=7, name="SOIC7")))
    assert [i.code for i in odd.issues] == ["package.pin-count"] and odd.footprint is None
    long_row = generate(record("soic8", lambda raw: raw.update(pins=16, name="SOIC16")))
    assert "package.dimensions-inconsistent" in [i.code for i in long_row.issues]
    sides = generate(record("sot23_5", lambda raw: raw.update(pins=6, name="SOT6")))
    assert [i.code for i in sides.issues if i.severity == "error"] == ["package.pin-count"]


def test_connector_positions(record: Record) -> None:
    series = record("connector_xh")
    assert generate(series).name == "CONN3_XH_P2.5"
    five = generate(series, positions=5)
    assert five.name == "CONN5_XH_P2.5" and five.footprint is not None
    assert [p.number for p in five.footprint.pads] == ["1", "2", "3", "4", "5"]
    with pytest.raises(FormatError, match="outside the series"):
        generate(series, positions=17)
    with pytest.raises(FormatError, match="connector series"):
        generate(record("soic8"), positions=3)


def test_library_and_ids(record: Record) -> None:
    local = generate(record("soic8")).footprint
    assert local is not None and local.lib_id == "Local:SOIC8_B4.9x3.9_P1.27"
    own = generate(record("soic8", lambda raw: raw.update(id="Acme:SOIC8_B4.9x3.9_P1.27"))).footprint
    assert own is not None and own.library == "Acme" and own.id != local.id
    assert generate(record("soic8"), library="Mine").footprint.library == "Mine"  # type: ignore[union-attr]
