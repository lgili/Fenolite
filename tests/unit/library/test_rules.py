# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Adversarial authored geometry and records for H-G-LIBRARY-RULES (c0262)."""

from dataclasses import replace

import pytest

from fenolite.catalog import records
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.core.quantities import LengthRange
from fenolite.library import rules
from fenolite.model.board import Graphic, Pad
from fenolite.model.library import FootprintDef, SymbolDef, SymbolPin


def footprint() -> FootprintDef:
    pads = tuple(
        Pad(
            id=f"p{i}",
            number=str(i),
            shape="rect",
            size=Size(600_000, 600_000),
            position=Point(x, y),
            layers=("F.Cu",),
        )
        for i, (x, y) in enumerate(
            (
                (-1_000_000, -1_000_000),
                (-1_000_000, 1_000_000),
                (1_000_000, 1_000_000),
                (1_000_000, -1_000_000),
            ),
            1,
        )
    )
    graphics = (
        Graphic(
            id="court",
            kind="rect",
            layer="F.CrtYd",
            points=(Point(-2_000_000, -2_000_000), Point(2_000_000, 2_000_000)),
            width=50_000,
        ),
        Graphic(
            id="marker",
            kind="line",
            layer="F.Fab",
            points=(Point(-1_500_000, -1_000_000), Point(-1_500_000, -500_000)),
            width=50_000,
        ),
    )
    return FootprintDef(id="fp", name="Synthetic", library="Rules", pads=pads, graphics=graphics)


def codes(found):
    return {f.code for f in found}


def test_footprint_good_and_count():
    fp = footprint()
    assert rules.check_footprint(fp, pins=4) == []
    finding = rules.check_footprint(fp, pins=3)
    assert codes(finding) == {"library.pad-count"}
    assert "4" in finding[0].message


def test_footprint_pin1_centroid_and_marker():
    fp = footprint()
    turned = replace(
        fp, pads=tuple(replace(p, position=Point(-p.position.x, -p.position.y)) for p in fp.pads)
    )
    assert "library.pin1-location" in codes(rules.check_footprint(turned))
    assert "library.pin1-marker" in codes(rules.check_footprint(replace(fp, graphics=fp.graphics[:1])))
    assert "library.pin1-location" not in codes(rules.check_footprint(replace(fp, pads=fp.pads[:2])))


def test_footprint_courtyard_missing_containment_and_clearance():
    fp = footprint()
    assert "library.courtyard-missing" in codes(rules.check_footprint(replace(fp, graphics=())))
    outside = replace(fp, pads=(replace(fp.pads[0], position=Point(-3_000_000, -1_000_000)), *fp.pads[1:]))
    assert "library.courtyard-containment" in codes(rules.check_footprint(outside))
    touching = replace(fp, pads=(fp.pads[0], replace(fp.pads[1], position=Point(-400_000, -1_000_000))))
    assert "library.pad-clearance" in codes(rules.check_footprint(touching))
    separate_layers = replace(touching, pads=(touching.pads[0], replace(touching.pads[1], layers=("B.Cu",))))
    assert "library.pad-clearance" not in codes(rules.check_footprint(separate_layers))


def test_footprint_line_chain_courtyard_and_round_copper():
    fp = footprint()
    ring = (
        Point(-2_000_000, -2_000_000),
        Point(2_000_000, -2_000_000),
        Point(2_000_000, 2_000_000),
        Point(-2_000_000, 2_000_000),
    )
    graphics = tuple(
        Graphic(id=f"g{i}", kind="line", layer="F.CrtYd", points=(ring[i], ring[(i + 1) % 4]), width=50_000)
        for i in range(4)
    )
    circle = replace(fp.pads[0], shape="circle", position=Point(-1_800_000, 0))
    assert "library.courtyard-missing" not in codes(rules.check_footprint(replace(fp, graphics=graphics)))
    assert "library.courtyard-containment" in codes(rules.check_footprint(replace(fp, pads=(circle,))))


def test_package_body_span_and_lead_length():
    facts = rules.PackageFacts(
        "gullwing",
        {
            "body.width": LengthRange(3_800_000, None, 6_300_000),
            "span": LengthRange(5_800_000, None, 6_200_000),
        },
    )
    assert codes(rules.check_package(facts)) == {"library.body-span"}
    good = rules.PackageFacts(
        "gullwing",
        {
            "body.width": LengthRange.exact(2_000_000),
            "span": LengthRange.exact(4_000_000),
            "lead.length": LengthRange.exact(500_000),
        },
    )
    assert rules.check_package(good) == []
    bad = replace(good, ranges={**good.ranges, "lead.length": LengthRange.exact(1_100_000)})
    assert "library.body-span" in codes(rules.check_package(bad))


def test_package_grid_names_and_depopulated():
    assert [rules.row_name(i) for i in (0, 7, 8, 19, 20, 21)] == ["A", "H", "J", "Y", "AA", "AB"]
    good = rules.PackageFacts("grid", {}, pins=96, rows=10, columns=10, depopulated=("A1", "A2", "A3", "A4"))
    assert rules.check_package(good) == []
    bad = replace(good, depopulated=good.depopulated[:3])
    found = rules.check_package(bad)
    assert codes(found) == {"library.depopulated"} and "97" in found[0].message
    assert "library.depopulated" in codes(rules.check_package(replace(good, depopulated=("I1",))))


def test_package_land_exact_generated_and_tolerated_import():
    fp = footprint()
    delta = replace(fp, pads=(replace(fp.pads[0], size=Size(650_000, 600_000)), *fp.pads[1:]))
    assert rules.check_land_pattern(delta, fp) == []
    assert rules.check_land_pattern(delta, fp, generated=True)[0].severity == "error"
    delta = replace(delta, pads=(replace(delta.pads[0], size=Size(700_000, 600_000)), *delta.pads[1:]))
    assert rules.check_land_pattern(delta, fp)[0].severity == "warning"


def symbol(*pins, **properties):
    return SymbolDef(id="s", name="Synthetic", pins=tuple(pins), properties=properties)


def pin(number="1", **kwargs):
    return SymbolPin(number, number, "passive", Point(0, 0), length=2_540_000, **kwargs)


def test_symbol_grid_hidden_power_duplicates_and_filters():
    sym = symbol(replace(pin(), position=Point(1_270_000, 0)), replace(pin("2"), position=Point(127_000, 0)))
    assert [f.severity for f in rules.check_symbol(sym)] == ["warning", "error"]
    hidden = replace(pin(), hidden=True, etype="power_in")
    assert "library.hidden-power" in codes(rules.check_symbol(symbol(hidden)))
    assert "library.duplicate-pin" in codes(rules.check_symbol(symbol(pin(), pin())))
    assert "library.duplicate-pin" not in codes(rules.check_symbol(symbol(pin(), pin()), stacked=("1",)))
    assert "library.hidden-power" not in codes(rules.check_symbol(symbol(hidden, pin("2"))))
    sym = symbol(pin(), ki_fp_filters="TSSOP*")
    assert "library.footprint-filter-miss" in codes(rules.check_symbol(sym, footprint="Demo:SOIC8"))
    assert "library.footprint-filter-broad" in codes(rules.check_symbol(symbol(pin(), ki_fp_filters="**")))
    assert "library.pin-group-type" in codes(rules.check_pin_groups([("1", "nc", "passive")]))


def test_record_evidence_sources_waivers_and_effective_evidence():
    assert "library.source-unknown" in codes(rules.check_envelope("INFERRED", ("S-1234",), set()))
    assert "library.sources-unchecked" in codes(rules.check_envelope("INFERRED", (), None))
    assert "library.evidence-claim" in codes(
        rules.check_envelope("CORPUS-VERIFIED (review 2026-11-01)", (), set())
    )
    found, used = rules.apply_waivers(
        [rules.issue("library.pin1-location", "custom")], {"library.pin1-location": "cable end"}
    )
    assert used == {"library.pin1-location"} and found[0].severity == "info"
    assert "library.waiver-unused" in codes(
        rules.apply_waivers([], {"library.pin1-location": "cable end"})[0]
    )
    with pytest.raises(FormatError):
        rules.apply_waivers([], {"library.review-stale": "ignore"})
    assert (
        rules.effective_evidence("CORPUS-VERIFIED (review 2026-11-01)", ["INFERRED"], reviewed=True)
        == "INFERRED"
    )
    assert (
        rules.effective_evidence("CORPUS-VERIFIED", reviewed=True, stale=True, previous_evidence="INFERRED")
        == "INFERRED"
    )


def lands(*rows: tuple[str, int, int, int, int]) -> FootprintDef:
    """A footprint of ``(number, x, y, w, h)`` pads in micrometres, with a courtyard around them."""
    pads = tuple(
        Pad(
            id=f"q{i}",
            number=number,
            shape="rect",
            size=Size(w * 1000, h * 1000),
            position=Point(x * 1000, y * 1000),
            layers=("F.Cu",),
        )
        for i, (number, x, y, w, h) in enumerate(rows)
    )
    return FootprintDef(id="fp", name="Order", library="Rules", pads=pads)


def mirrored(fp: FootprintDef) -> FootprintDef:
    """``fp`` mirrored about its X axis: the land of the same part seen from below."""
    return replace(fp, pads=tuple(replace(p, position=Point(p.position.x, -p.position.y)) for p in fp.pads))


SOT23 = lands(("1", -1050, -950, 1300, 600), ("2", -1050, 950, 1300, 600), ("3", 1050, 0, 1300, 600))
SOIC8 = lands(
    *((str(i + 1), -2700, -1905 + 1270 * i, 1550, 600) for i in range(4)),
    *((str(8 - i), 2700, -1905 + 1270 * i, 1550, 600) for i in range(4)),
)
QFN8_EP = lands(
    *((str(i + 1), -1000, -500 + 1000 * i, 600, 300) for i in range(2)),
    *((str(3 + i), -500 + 1000 * i, 1000, 300, 600) for i in range(2)),
    *((str(5 + i), 1000, 500 - 1000 * i, 600, 300) for i in range(2)),
    *((str(7 + i), 500 - 1000 * i, -1000, 300, 600) for i in range(2)),
    ("9", 0, 0, 1200, 1200),
)
SOT89 = lands(
    ("1", -1500, 1450, 580, 1630),
    ("2", 0, 1490, 760, 1550),
    ("3", 1500, 1450, 580, 1630),
    ("2", 0, -750, 1933, 3030),
)
TO252 = lands(("1", -2286, 4050, 1060, 2600), ("3", 2286, 4050, 1060, 2600), ("2", 0, -2500, 5632, 5700))


@pytest.mark.parametrize(
    "fp", [SOT23, SOIC8, QFN8_EP, SOT89, TO252], ids=["sot23", "soic8", "qfn", "sot89", "to252"]
)
def test_pin_order_counter_clockwise_passes_and_its_mirror_is_refused(fp):
    assert rules.pin_order(fp) == "counter-clockwise"
    assert "library.pin-order" not in codes(rules.check_footprint(fp))
    assert rules.pin_order(mirrored(fp)) == "clockwise"
    found = [f for f in rules.check_footprint(mirrored(fp)) if f.code == "library.pin-order"]
    assert len(found) == 1 and found[0].severity == "error"


def test_pin_order_turning_the_land_keeps_its_order():
    turned = replace(
        SOIC8, pads=tuple(replace(p, position=Point(-p.position.x, -p.position.y)) for p in SOIC8.pads)
    )
    quarter = replace(
        SOIC8, pads=tuple(replace(p, position=Point(-p.position.y, p.position.x)) for p in SOIC8.pads)
    )
    assert rules.pin_order(turned) == rules.pin_order(quarter) == "counter-clockwise"


def test_pin_order_ignores_lands_without_a_perimeter_numbering():
    zigzag = lands(
        *(
            (str(2 * r + c + 1), -1270 + 2540 * c, -2540 + 2540 * r, 1800, 1800)
            for r in range(3)
            for c in range(2)
        )
    )
    zigzag_even = lands(
        *(
            (str(2 * r + c + 1), -1270 + 2540 * c, -3810 + 2540 * r, 1800, 1800)
            for r in range(4)
            for c in range(2)
        )
    )
    row = lands(*((str(i + 1), -3750 + 2500 * i, 0, 1800, 1800) for i in range(4)))
    same_way = lands(
        *((str(i + 1), -3750 + 2500 * i, -1250, 1000, 1000) for i in range(4)),
        *((str(i + 5), -3750 + 2500 * i, 1250, 1000, 1000) for i in range(4)),
    )
    switch = lands(
        ("1", -3500, 1500, 2000, 1400),
        ("2", 3500, 1500, 2000, 1400),
        ("3", -3500, -1500, 2000, 1400),
        ("4", 3500, -1500, 2000, 1400),
    )
    grid = lands(
        ("A1", -500, -500, 300, 300),
        ("A2", 500, -500, 300, 300),
        ("B1", -500, 500, 300, 300),
        ("B2", 500, 500, 300, 300),
    )
    two = lands(("1", -1000, 0, 600, 600), ("2", 1000, 0, 600, 600))
    two_mounts = lands(
        *((str(i + 1), -1500 + 1000 * i, -2000, 600, 1500) for i in range(4)),
        ("5", -3000, 1000, 1200, 1800),
        ("6", 3000, 1000, 1200, 1800),
    )
    staggered = lands(("1", 0, 0, 1300, 1300), ("2", 1270, -1270, 1300, 1300), ("3", 2540, 0, 1300, 1300))
    terminal_block = lands(
        *((str(i + 1), -5000 + 2500 * i, 0, 1500, 1500) for i in range(5)),
        *((str(i + 1), -5000 + 2500 * i, 5000, 1500, 1500) for i in range(5)),
    )
    cases = (zigzag, zigzag_even, row, same_way, switch, grid, two, two_mounts, staggered, terminal_block)
    for fp in cases:
        for case in (fp, mirrored(fp)):
            assert rules.pin_order(case) is None, case.pads
            assert "library.pin-order" not in codes(rules.check_footprint(case))


def test_pin_order_is_a_warning_for_a_plain_library_item():
    found = [
        f for f in rules.check_footprint(mirrored(SOIC8), recorded=False) if f.code == "library.pin-order"
    ]
    assert len(found) == 1 and found[0].severity == "warning"
    assert "warning" in rules.ISSUE_CODES["library.pin-order"]


def test_pin_order_waiver_must_name_its_source():
    finding = rules.issue("library.pin-order", "clockwise")
    with pytest.raises(FormatError, match="S- or D- source"):
        rules.apply_waivers([finding], {"library.pin-order": "Legacy drawing keeps its orientation."})
    found, used = rules.apply_waivers(
        [finding], {"library.pin-order": "S-0410 page 2 numbers this connector clockwise in the top view."}
    )
    assert used == {"library.pin-order"} and found[0].severity == "info"


def test_shipped_catalog_rules_have_no_unexplained_findings():
    tree = records.shipped_tree()
    for record in tree.records:
        found = []
        if isinstance(record, records.PackageRecord):
            found = rules.check_footprint(records.footprint_def(record))
        elif isinstance(record, records.PinsRecord):
            found = rules.check_symbol(records.symbol_def(record))
        found, _ = rules.apply_waivers(
            found, {w.code: w.reason for w in record.header.waivers}, record_id=record.header.id
        )
        assert not [f for f in found if f.severity in {"error", "warning"}], (record.header.id, found)
