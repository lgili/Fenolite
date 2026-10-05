# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading KiCad ERC reports and locating their items (capability kicad-file-backend, "ERC report
reading"; kicad-oracle, "ERC oracle"; change c0062)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.kicad import erc
from fenolite.backends.kicad.erc import REQUIRED_KEYS, item_locations, located, read_erc_report
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Level

DATA = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad"
TEN = (DATA / "erc" / "report_10.json").read_text(encoding="utf-8")
NINE = (DATA / "erc" / "report_9.json").read_text(encoding="utf-8")
MULTI = DATA / "schematic" / "multi"


def edited(text: str = TEN, **changes: object) -> str:
    data = json.loads(text)
    for key, value in changes.items():
        if value is None:
            del data[key]
        else:
            data[key] = value
    return json.dumps(data)


def test_report_of_10() -> None:
    report = read_erc_report(TEN)
    first = report.violations[0]
    assert (first.type, first.sheet, first.severity) == ("pin_not_connected", "/", "error")
    assert first.items[0].position == Point(139_700_000, 59_690_000)
    assert first.items[0].uuid == "22222222-0000-4000-8000-000000000002" and first.items[0].where == ""
    assert first.sheet_id == "/11111111-0000-4000-8000-000000000001"
    assert report.ignored_checks == ("footprint_filter",)
    assert report.included_severities == ("error", "warning", "exclusion")
    assert (report.source, report.kicad_version, report.coordinate_units) == (
        "authored.kicad_sch",
        "10.0.6",
        "mm",
    )


def test_sheets_and_order() -> None:
    report = read_erc_report(TEN)
    assert report.sheets == ("/", "/Child/")
    assert [(v.sheet, v.type, v.excluded) for v in report.violations] == [
        ("/", "pin_not_connected", False),
        ("/", "lib_symbol_issues", True),
        ("/Child/", "isolated_pin_label", False),
    ]
    assert report.violations[2].sheet_id.endswith("/11111111-0000-4000-8000-000000000002")


def test_report_of_9() -> None:
    report = read_erc_report(NINE)
    assert report.ignored_checks == () and report.sheets == ("/",)
    assert report.violations[0].items[0].position == Point(139_700_000, 59_690_000)
    assert report.of_type("global_label_dangling")[0].severity == "warning"


@pytest.mark.parametrize(
    "key", [*REQUIRED_KEYS["report"], *REQUIRED_KEYS["sheet"], *REQUIRED_KEYS["violation"]]
)
def test_missing_required_key(key: str) -> None:
    data: dict[str, Any] = json.loads(TEN)
    if key in REQUIRED_KEYS["report"]:
        del data[key]
    elif key in REQUIRED_KEYS["sheet"]:
        del data["sheets"][0][key]
    else:
        del data["sheets"][0]["violations"][0][key]
    with pytest.raises(FormatError, match=key):
        read_erc_report(json.dumps(data), file="erc.json")


def test_required_keys_are_the_documented_ones() -> None:
    assert dict(REQUIRED_KEYS) == {
        "report": ("source", "date", "kicad_version", "sheets"),
        "sheet": ("path", "uuid_path", "violations"),
        "violation": ("type", "description", "severity", "items"),
    }


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_strict_number_rejected(constant: str) -> None:
    text = TEN.replace('"x": 1.397', f'"x": {constant}')
    assert text != TEN
    with pytest.raises(FormatError, match="strict JSON"):
        read_erc_report(text)


def test_unknown_major_stays_unscaled() -> None:
    issues: list[Issue] = []
    report = read_erc_report(edited(kicad_version="11.0.0"), file="erc.json", issues=issues)
    assert report.violations[0].items[0].position == Point(1_397_000, 596_900)
    assert [(i.code, i.severity) for i in issues] == [("kicad.erc.position-unscaled", "info")]
    assert "11.0.0" in issues[0].message
    read_erc_report(edited(kicad_version="11.0.0"))  # without a list nothing is reported


def test_major_argument_overrides_the_report() -> None:
    issues: list[Issue] = []
    report = read_erc_report(edited(kicad_version="11.0.0"), major=10, issues=issues)
    assert report.violations[0].items[0].position == Point(139_700_000, 59_690_000) and not issues
    report = read_erc_report(TEN, major=11, issues=issues)
    assert report.violations[0].items[0].position == Point(1_397_000, 596_900) and len(issues) == 1


def test_known_major_gives_no_issue() -> None:
    issues: list[Issue] = []
    read_erc_report(TEN, issues=issues)
    read_erc_report(NINE, issues=issues)
    assert not issues


def test_units() -> None:
    assert read_erc_report(edited(coordinate_units=None)).coordinate_units == "mm"
    mils = read_erc_report(edited(coordinate_units="mils"))
    assert mils.violations[0].items[0].position == Point(3_548_380, 1_516_126)
    inches = read_erc_report(edited(coordinate_units="in"))
    assert inches.violations[0].items[0].position == Point(3_548_380_000, 1_516_126_000)
    with pytest.raises(FormatError, match="coordinate_units"):
        read_erc_report(edited(coordinate_units="furlong"))


def test_unknown_keys_ignored_and_defaults() -> None:
    data = json.loads(NINE)
    data["later"] = {"a": 1}
    data["sheets"][0]["later"] = 1
    data["sheets"][0]["violations"][0]["later"] = [1]
    report = read_erc_report(json.dumps(data))
    assert not report.violations[0].excluded and report.included_severities
    assert read_erc_report(edited(NINE, included_severities=None)).included_severities == ()


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["sheets"][0]["violations"][0].__setitem__("excluded", "yes"),
        lambda d: d["sheets"][0]["violations"][0]["items"][0].pop("pos"),
        lambda d: d["sheets"][0]["violations"][0]["items"][0]["pos"].pop("y"),
        lambda d: d["sheets"][0]["violations"][0]["items"][0]["pos"].__setitem__("x", "1"),
        lambda d: d["sheets"][0]["violations"][0].__setitem__("type", 3),
        lambda d: d.__setitem__("sheets", {}),
        lambda d: d.__setitem__("included_severities", [1]),
        lambda d: d["sheets"].__setitem__(0, []),
    ],
)
def test_malformed_values_refused(change: Any) -> None:
    data = json.loads(TEN)
    change(data)
    with pytest.raises(FormatError):
        read_erc_report(json.dumps(data))


def test_not_json() -> None:
    with pytest.raises(FormatError, match="strict JSON"):
        read_erc_report("{")
    with pytest.raises(FormatError):
        read_erc_report("[]")


def test_no_float_is_created() -> None:
    report = read_erc_report(TEN)
    for violation in report.violations:
        for item in violation.items:
            assert type(item.position.x) is int and type(item.position.y) is int


def test_evidence_names_the_three_hypotheses() -> None:
    assert set(erc.EVIDENCE.hypotheses) == {"H-K-ERC-JSON", "H-K-ERC-POS", "H-K-ERC-COPYSET"}
    assert erc.EVIDENCE.level in (Level.INFERRED, Level.KICAD_VERIFIED)


# -- item locations

SHEET = """(kicad_sch (version 20250114) (generator "authored") (uuid "aaaaaaaa-0000-4000-8000-000000000001")
  (symbol (lib_id "A:B") (at 0 0 0) (uuid "AAAAAAAA-0000-4000-8000-0000000000A1")
    (property "Reference" "U?" (at 0 0 0))
    (pin "1" (uuid "aaaaaaaa-0000-4000-8000-0000000000b1"))
    (pin "2" (uuid "aaaaaaaa-0000-4000-8000-0000000000b2"))
    (instances
      (project "other" (path "/aaaaaaaa-0000-4000-8000-000000000001" (reference "X9") (unit 1)))
      (project "demo" (path "/aaaaaaaa-0000-4000-8000-000000000001" (reference "U1") (unit 1)))))
  (symbol (lib_id "A:C") (at 0 0 0) (uuid "aaaaaaaa-0000-4000-8000-0000000000a2")
    (pin "" (uuid "aaaaaaaa-0000-4000-8000-0000000000b3"))
    (instances (project "far" (path "/aaaaaaaa-0000-4000-8000-000000000001" (reference "R7") (unit 1)))))
  (symbol (lib_id "A:D") (at 0 0 0) (uuid "aaaaaaaa-0000-4000-8000-0000000000a3"))
  (label "LOCAL" (at 1 1 0) (uuid "aaaaaaaa-0000-4000-8000-0000000000c1"))
  (global_label "SENSE" (shape input) (at 1 1 0) (uuid "aaaaaaaa-0000-4000-8000-0000000000c2"))
  (hierarchical_label "IN" (shape input) (at 1 1 0) (uuid "aaaaaaaa-0000-4000-8000-0000000000c3"))
  (wire (pts (xy 0 0) (xy 1 1)) (uuid "aaaaaaaa-0000-4000-8000-0000000000d1")))
"""
ROOT = "/aaaaaaaa-0000-4000-8000-000000000001"


def test_locations_of_a_flat_sheet() -> None:
    found = item_locations({"demo.kicad_sch": parse(SHEET)}, "demo")
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000a1")] == "U1"  # lower case, the named project
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000b1")] == "U1-1"
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000b2")] == "U1-2"
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000a2")] == "R7"  # another project's use, by path
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000b3")] == "R7"  # a pin without a number
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000c1")] == "LOCAL"
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000c2")] == "SENSE"
    assert found[(ROOT, "aaaaaaaa-0000-4000-8000-0000000000c3")] == "IN"
    assert not [key for key in found if key[1].endswith("d1") or key[1].endswith("a3")]
    assert found[(erc.ROOT_PATH, "aaaaaaaa-0000-4000-8000-0000000000b2")] == "U1-2"


def _multi() -> dict[str, Any]:
    return {
        "top.kicad_sch": parse((MULTI / "top.kicad_sch").read_text(encoding="utf-8")),
        "cell.kicad_sch": parse((MULTI / "cell.kicad_sch").read_text(encoding="utf-8")),
    }


def test_two_uses_of_one_sheet_give_two_references() -> None:
    trees = _multi()
    found = item_locations(trees, "top")
    cell = trees["cell.kicad_sch"]
    symbol = next(s for s in cell.nodes("symbol") if s.find("instances") is not None)
    uuid = symbol.find("uuid").atoms()[0].value.lower()  # type: ignore[union-attr]
    references = {path: where for (path, key), where in found.items() if key == uuid and path}
    assert len(references) == 2 and len(set(references.values())) == 2
    assert (erc.ROOT_PATH, uuid) not in found  # the two uses disagree, so no location without a sheet
    root_uuid = trees["top.kicad_sch"].find("uuid").atoms()[0].value  # type: ignore[union-attr]
    assert all(path.startswith(f"/{root_uuid}/") for path in references)


def test_labels_of_a_shared_sheet_are_located_on_every_use() -> None:
    trees = _multi()
    found = item_locations(trees, "top")
    labels = [c for c in trees["cell.kicad_sch"].nodes() if c.name in erc.LABEL_HEADS]
    if not labels:
        pytest.skip("the authored cell has no label")
    uuid = labels[0].find("uuid").atoms()[0].value.lower()  # type: ignore[union-attr]
    assert len([key for key in found if key[1] == uuid and key[0]]) == 2
    assert found[(erc.ROOT_PATH, uuid)] == labels[0].atoms()[0].value


def test_located_fills_where_by_sheet_then_everywhere() -> None:
    report = read_erc_report(TEN)
    pin, symbol, label = (v.items[0].uuid for v in report.violations)
    locations = {
        (report.violations[0].sheet_id, pin): "U1-2",
        (erc.ROOT_PATH, label): "SENSE",
        ("/somewhere-else", symbol): "U9",
    }
    done = located(report, locations)
    assert [v.items[0].where for v in done.violations] == ["U1-2", "", "SENSE"]
    assert done.entries() == report.entries() and done.sheets == report.sheets


def test_missing_root_gives_only_symbol_locations() -> None:
    found = item_locations({"child.kicad_sch": parse(SHEET)}, "demo")
    assert (ROOT, "aaaaaaaa-0000-4000-8000-0000000000b1") in found
    assert not [key for key in found if key[1].endswith("c1")]  # no use of the file is known
