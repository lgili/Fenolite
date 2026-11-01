# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library records (change c0259; capability library-records, "Library record kinds" to "Review entries").
The records of ``tests/data/library`` are authored for Fenolite and illustrative."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from importlib import resources
from pathlib import Path

import pytest

from fenolite.catalog.records import (
    DeviceRecord,
    PackageRecord,
    PartRecord,
    PinsRecord,
    Review,
    footprint_def,
    kind_of,
    load_tree,
    parse_record,
    record_digest,
    record_text,
    record_uid,
    shipped_tree,
)
from fenolite.core.errors import FormatError
from fenolite.core.ids import FENOLITE_NS
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "tests" / "data" / "library"
AUTHORED = "# Authored for Fenolite"

PACKAGE = """\
schema = "fenolite.package.v0"
id = "{id}"
version = "1.0.0"
summary = "Test land"
licence = "{licence}"
evidence = "UNVERIFIED"
{extra}generator = "explicit"
kind = "smd"

[[pad]]
number = "1"
shape = "rect"
size = {size}
at = {at}
"""


def _package(
    *,
    record_id: str = "Proj:Land",
    licence: str = "CC0-1.0",
    extra: str = "",
    size: str = '["1mm", "1mm"]',
    at: str = '["0mm", "0mm"]',
) -> str:
    return PACKAGE.format(id=record_id, licence=licence, extra=extra, size=size, at=at)


def _refused(text: str, code: str = "FEN-3004") -> FormatError:
    with pytest.raises(FormatError) as caught:
        parse_record(text, file="lib/x.toml")
    assert getattr(caught.value, "code", None) == code, caught.value
    return caught.value


def _floats(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_floats(item) for item in value.values())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, list):
        return any(_floats(item) for item in value)  # pyright: ignore[reportUnknownVariableType]
    return False


def test_each_kind_is_read_kinds() -> None:
    tree = load_tree(LIBRARY)
    kinds = {kind_of(record): type(record) for record in tree.records}
    assert kinds == {"pins": PinsRecord, "package": PackageRecord, "device": DeviceRecord, "part": PartRecord}
    for record in tree.records:
        assert not _floats(json.loads(canonical.dumps(record))), record.header.id
    for path in sorted(LIBRARY.rglob("*.toml")):
        assert AUTHORED in path.read_text(encoding="utf-8").splitlines()[1], path


def test_newer_schema() -> None:
    error = _refused(_package().replace("fenolite.package.v0", "fenolite.package.v1"), "FEN-3002")
    assert "fenolite.package.v1" in str(error)


def test_unknown_header_key() -> None:
    error = _refused(_package(extra='colour = "red"\n'))
    assert "colour" in str(error) and "lib/x.toml" in str(error)


def test_missing_licence() -> None:
    text = (
        (LIBRARY / "pins" / "two_pin.toml").read_text(encoding="utf-8").replace('licence = "CC0-1.0"\n', "")
    )
    assert "licence" in str(_refused(text))


def test_mils_are_exact() -> None:
    record = parse_record(_package(size='["25mil", "50mil"]'))
    assert isinstance(record, PackageRecord)
    assert (record.pads[0].size.w, record.pads[0].size.h) == (635_000, 1_270_000)


def test_sub_nanometre_length_refused() -> None:
    assert "at" in str(_refused(_package(at='["0.0000001mm", "0mm"]')))
    _refused(_package(size='["1", "1mm"]'))
    _refused(_package(extra='body = { length = "2mm..1mm" }\n'))


def test_regeneration_keeps_the_uid() -> None:
    first = record_uid("package", "Fenolite:Chip_0603")
    assert first == record_uid("package", "Fenolite:Chip_0603")
    assert first != record_uid("pins", "Fenolite:Chip_0603")
    import uuid

    assert first == str(uuid.uuid5(FENOLITE_NS, "fenolite.library:package:Fenolite:Chip_0603"))
    assert "uid" not in (LIBRARY / "packages" / "two_pad.toml").read_text(encoding="utf-8")


def test_round_trip() -> None:
    folder = resources.files("fenolite.catalog") / "data"
    tree = shipped_tree()
    assert len(tree.records) >= 159
    for (kind, record_id), name in tree.files.items():
        record = tree.get(kind, record_id)  # type: ignore[arg-type]
        assert record is not None
        relative = name.removeprefix("fenolite/catalog/data/")
        text = (folder / relative).read_text(encoding="utf-8")
        assert record_text(record) == text, name
        assert parse_record(record_text(record)) == record, name
    for record in load_tree(LIBRARY).records:
        assert parse_record(record_text(record)) == record, record.header.id


def test_a_review_does_not_change_the_digest() -> None:
    record = parse_record((LIBRARY / "packages" / "two_pad.toml").read_text(encoding="utf-8"))
    review = Review("maintainer", "2026-10-29", "1.0.0", record_digest(record), "UNVERIFIED")
    reviewed = replace(record, header=replace(record.header, reviewed_by=(review,)))
    assert record_digest(reviewed) == record_digest(record)
    assert parse_record(record_text(reviewed)) == reviewed


def test_digest_changes_with_the_content() -> None:
    record = parse_record(_package())
    assert record_digest(parse_record(_package(size='["2mm", "1mm"]'))) != record_digest(record)
    assert len(record_digest(record)) == 64


def test_licence_shipped_record_with_another_licence() -> None:
    text = _package(record_id="Fenolite:X", licence="CC-BY-SA-4.0", extra='sources = ["S-0314"]\n')
    assert "licence" in str(_refused(text))
    # the maintainer's decision of 2026-10-29: shipped records are CC0-1.0, not the provisional Apache-2.0
    apache = _package(record_id="Fenolite:X", licence="Apache-2.0", extra='sources = ["S-0314"]\n')
    assert "CC0-1.0" in str(_refused(apache))
    assert parse_record(_package(record_id="Fenolite:X", extra='sources = ["S-0314"]\n'))
    assert parse_record(_package(record_id="Proj:X", licence="LicenseRef-see-source-terms"))
    _refused(_package(record_id="Fenolite:X"))  # a shipped record needs its sources


ORIGIN = 'origin = { library = "CC0 Lib", version = "1.0.0", element = "0d1c", licence = "%s" }\n'


def test_origin_unreviewed_seeded_record_claims_a_higher_label() -> None:
    text = _package(extra=ORIGIN % "CC0-1.0").replace('"UNVERIFIED"', '"CORPUS-VERIFIED"')
    assert "evidence" in str(_refused(text))
    assert parse_record(_package(extra=ORIGIN % "CC0-1.0"))


def test_origin_from_a_non_cc0_library() -> None:
    assert "origin.licence" in str(_refused(_package(extra=ORIGIN % "CC-BY-SA-4.0")))
    assert "licence" in str(_refused(_package(licence="Apache-2.0", extra=ORIGIN % "CC0-1.0")))


def test_review_supports_an_origin_record() -> None:
    record = parse_record(_package(extra=ORIGIN % "CC0-1.0"))
    # the review names the digest of the record as it is after the review: with the label it asserts
    digest = record_digest(replace(record, header=replace(record.header, evidence="CORPUS-VERIFIED")))
    review = f'\n[[reviewed_by]]\nwho = "maintainer"\ndate = "2026-10-29"\nversion = "1.0.0"\ndigest = "{digest}"\nevidence = "CORPUS-VERIFIED"\n'  # noqa: E501
    text = _package(extra=ORIGIN % "CC0-1.0").replace('"UNVERIFIED"', '"CORPUS-VERIFIED"') + review
    assert parse_record(text).header.evidence == "CORPUS-VERIFIED"
    stale = text.replace(digest, "0" * 64)
    assert "evidence" in str(_refused(stale))


def test_review_entries_are_checked() -> None:
    base = _package()
    for bad in ('who = "a@b.example"', 'date = "29/10/2026"', 'digest = "abc"'):
        fields = {"who": '"maintainer"', "date": '"2026-10-29"', "digest": '"' + "0" * 64 + '"'}
        key = bad.split(" = ")[0]
        fields[key] = bad.split(" = ")[1]
        review = "\n[[reviewed_by]]\n" + "".join(f"{k} = {v}\n" for k, v in fields.items())
        review += 'version = "1.0.0"\nevidence = "UNVERIFIED"\n'
        assert "reviewed_by" in str(_refused(base + review))


def test_versions_are_semantic() -> None:
    _refused(_package().replace('"1.0.0"', '"1.0"'))
    _refused(_package().replace('"1.0.0"', '"01.0.0"'))


def test_explicit_footprint_from_the_test_record() -> None:
    record = parse_record((LIBRARY / "packages" / "two_pad.toml").read_text(encoding="utf-8"))
    assert isinstance(record, PackageRecord)
    assert record.dimensions == {"body.length": (1_600_000,), "body.width": (800_000,)}
    footprint = footprint_def(record)
    from fenolite.core.ids import derived_id

    assert [pad.id for pad in footprint.pads] == [
        derived_id("pad", "fenolite.catalog", "Two_Pad:1"),
        derived_id("pad", "fenolite.catalog", "Two_Pad:2"),
    ]
    assert footprint.description == "Two-pad test land" and not re.search(r"INFERRED", footprint.description)


@pytest.mark.parametrize("name", ["example_buck", "grouped_ground", "stamped"])
def test_upgraded_device_round_trip(name: str) -> None:
    """``upgraded_device`` (what ``fenolite fmt`` writes for a v0 file, c0259 task 6.2): v0 → v1 → load gives
    the same device, and a v1 record is returned unchanged."""
    from fenolite.catalog.records import UPGRADED_VERSION, DeviceRecord, upgraded_device

    old = parse_record((ROOT / "tests" / "data" / "devices" / f"{name}.toml").read_text(encoding="utf-8"))
    assert isinstance(old, DeviceRecord) and old.header.schema == "fenolite.device.v0"
    new = upgraded_device(old, licence="CC0-1.0")
    again = parse_record(record_text(new))
    assert isinstance(again, DeviceRecord) and again == new and again.device == old.device
    assert (again.header.schema, again.header.version) == ("fenolite.device.v1", UPGRADED_VERSION)
    assert upgraded_device(again, licence="NOASSERTION") is again
