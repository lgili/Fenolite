# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The issues of a conversion agree with its report for every kind (capability design-conversion, "Report
and issues agree"; change c0429): one ``convert.lossy`` per row with lost items, whatever its loss class,
one ``convert.changed`` per changed row and one ``convert.kept`` per kept row. A ``refuse`` loss still needs
``allow_lossy``; a ``report`` loss warns without a refusal."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import TWO_LAYER

import fenolite.convert as convert_module
from fenolite.convert import LossyConversionError, convert_project, report_issues
from fenolite.convert.direction import Options, Written
from fenolite.convert.report import BY_NAME, DOWNGRADE_KINDS, KINDS, ConversionReport, merge
from fenolite.convert.sources import SourceProject

EVERY_KIND = tuple(row.name for row in (*KINDS, *DOWNGRADE_KINDS))


def _by_code(report: ConversionReport) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {"convert.lossy": [], "convert.changed": [], "convert.kept": []}
    for found_issue in report_issues(report):
        found[found_issue.code].append(found_issue.where)
    return found


def _expected(report: ConversionReport) -> dict[str, list[str]]:
    return {
        "convert.lossy": [row.kind for row in report.rows if row.lost],
        "convert.changed": [row.kind for row in report.rows if row.changed],
        "convert.kept": [row.kind for row in report.rows if row.kept],
    }


@pytest.mark.parametrize("kind", EVERY_KIND)
def test_every_kind_lost_changed_and_kept(kind: str) -> None:
    """Scenario "Every kind": one lost, one changed and one kept item of the kind give exactly one issue
    of each code, with the kind as ``where`` and the reason in the message."""
    report = ConversionReport.of(
        source={kind: 4},
        lost={kind: {"authored loss": [f"{kind}/1"]}},
        changed={kind: {"authored change": [f"{kind}/2"]}},
        kept={kind: {"authored limit": [f"{kind}/3"]}},
    )
    assert _by_code(report) == {"convert.lossy": [kind], "convert.changed": [kind], "convert.kept": [kind]}
    lossy, changed, kept = report_issues(report)
    assert lossy.severity == "warning" and lossy.message.startswith(f"1 of 4 {kind} item(s)")
    assert "1 authored loss" in lossy.message
    assert changed.severity == "info" and "1 authored change" in changed.message
    assert kept.severity == "info" and "1 authored limit" in kept.message


@pytest.mark.parametrize("kind", EVERY_KIND)
def test_a_kept_row_has_no_issue(kind: str) -> None:
    """Negative case: a row whose items were all written has no ``convert.*`` issue."""
    report = ConversionReport.of(source={kind: 3}, written={kind: 3})
    assert report.rows and report_issues(report) == ()


def test_every_kind_at_once_in_report_order() -> None:
    """All kinds in one report, each with a different outcome by its place in the table: the issues name
    the same kinds as the rows, in report order."""
    lost: dict[str, dict[str, list[str]]] = {}
    changed: dict[str, dict[str, list[str]]] = {}
    kept: dict[str, dict[str, list[str]]] = {}
    for index, kind in enumerate(EVERY_KIND):
        into = (lost, changed, kept, {})[index % 4]
        into[kind] = {"authored": [f"{kind}/1"]}
    report = ConversionReport.of(source=dict.fromkeys(EVERY_KIND, 2), lost=lost, changed=changed, kept=kept)
    assert _by_code(report) == _expected(report)
    assert set(_by_code(report)["convert.lossy"]) == set(lost)
    assert report.refused == tuple(
        kind for kind in _by_code(report)["convert.lossy"] if BY_NAME[kind].loss == "refuse"
    )


def _with_rows(monkeypatch: pytest.MonkeyPatch, extra: ConversionReport) -> None:
    """The KiCad to Altium direction with ``extra`` merged into the report of each write."""
    key = ("kicad", "altium")
    direction = convert_module.DIRECTIONS[key]

    def write(read: SourceProject, options: Options) -> Written:
        written = direction.write(read, options)
        return dataclasses.replace(written, report=merge(written.report, extra))

    monkeypatch.setitem(convert_module.DIRECTIONS, key, dataclasses.replace(direction, write=write))


REPORT_KINDS = ("rule", "body", "model", "schematic", "graphic")
"""The ``report`` kinds the reference sweep found lost without an issue (S-1880 to S-1889)."""


@pytest.mark.parametrize("kind", REPORT_KINDS)
def test_a_report_loss_warns_without_refusing(monkeypatch: pytest.MonkeyPatch, kind: str) -> None:
    """Scenario "A lost report kind warns": no ``allow_lossy`` needed, and one ``convert.lossy`` names it."""
    assert BY_NAME[kind].loss == "report"
    _with_rows(
        monkeypatch, ConversionReport.of(source={kind: 1}, lost={kind: {"authored loss": [f"{kind}/1"]}})
    )
    conversion = convert_project(TWO_LAYER, to="altium", pour="outline")
    assert conversion.report.refused == ()
    lossy = [found.where for found in conversion.issues if found.code == "convert.lossy"]
    assert lossy == [row.kind for row in conversion.report.rows if row.lost]
    assert kind in lossy


def test_a_refuse_loss_still_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative case: a ``refuse`` loss refuses without ``allow_lossy``; the refusal names the refused
    kinds and lists every loss that consent would accept, the ``report`` ones too (change c0434); with
    consent, every lost kind warns."""
    extra = ConversionReport.of(
        source={"pad": 1, "rule": 1},
        lost={"pad": {"authored loss": ["pad/1"]}, "rule": {"authored loss": ["rule/1"]}},
    )
    _with_rows(monkeypatch, extra)
    with pytest.raises(LossyConversionError) as refused:
        convert_project(TWO_LAYER, to="altium", pour="outline")
    assert [found.where for found in refused.value.issues] == ["pad", "rule"]
    assert refused.value.refused == ("pad",)
    assert str(refused.value) == (  # the per-kind list of change c0495 follows the refused kinds
        "the conversion would lose 2 item(s) of the source (pad); --allow-lossy also loses items of rule: "
        "pad: 1 (1 authored loss); rule: 1 (1 authored loss)"
    )
    conversion = convert_project(TWO_LAYER, to="altium", pour="outline", allow_lossy=True)
    lossy = [found.where for found in conversion.issues if found.code == "convert.lossy"]
    assert lossy == ["pad", "rule"] == [row.kind for row in conversion.report.rows if row.lost]


def test_the_conversion_issues_are_the_report_issues() -> None:
    """The ``convert.*`` issues of a real conversion are ``report_issues`` of its report, nothing more."""
    conversion = convert_project(TWO_LAYER, to="altium", pour="outline")
    ledger = tuple(found for found in conversion.issues if found.code in _expected(conversion.report))
    assert ledger == report_issues(conversion.report)
    assert _by_code(conversion.report) == _expected(conversion.report)
