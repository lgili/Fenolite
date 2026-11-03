# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Narrow state-plus-issue receipts for existing conservative replies (c0219).

These predicates preserve an existing UNVERIFIED limitation. No marker alone, generic boolean or
arbitrary command can opt out of the evidence contract. Complete results still require evidence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any, cast, get_args

from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence


def _map(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def _rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(_map(item) for item in cast(tuple[object, ...], value))


def _positive(value: object) -> bool:
    return type(value) is int and value > 0


def _counts(value: object) -> bool:
    return any(_positive(count) for count in _map(value).values())


def conservative_inputs(command: str, result: Mapping[str, Any], evidence: Evidence) -> bool:
    """An actual pin choice references a declared, digested unverified input device."""
    if command != "build" or "H-G-PIN-SOLVE-DETERMINISTIC" not in evidence.hypotheses:
        return False
    parts: set[str] = set()
    for device in _rows(result.get("devices")):
        digest = device.get("sha256")
        paths = device.get("parts")
        if (
            device.get("evidence") == "UNVERIFIED"
            and isinstance(device.get("id"), str)
            and bool(device["id"])
            and isinstance(digest, str)
            and re.fullmatch(r"[a-f0-9]{64}", digest)
            and isinstance(paths, (list, tuple))
        ):
            parts.update(
                path
                for path in cast(list[object] | tuple[object, ...], paths)
                if isinstance(path, str) and path
            )
    for row in _rows(result.get("pins")):
        key = row.get("key")
        pins = _map(row.get("pins"))
        if (
            isinstance(key, str)
            and any(key.startswith(part + "/") for part in parts)
            and all(isinstance(row.get(name), str) and bool(row[name]) for name in ("kind", "option"))
            and type(row.get("alternative")) is int
            and row["alternative"] >= 0
            and row.get("source") in ("solved", "locked")
            and pins
            and all(isinstance(value, str) and bool(value) for value in pins.values())
        ):
            return True
    return False


def _analysis(result: Mapping[str, Any], issues: tuple[Issue, ...]) -> bool:
    codes = {issue.code for issue in issues}
    summary = _map(result.get("summary"))
    current = _map(summary.get("current"))
    power = _map(summary.get("power"))
    length = _map(summary.get("length"))
    distances = _map(summary.get("distances"))
    if "analysis.input-missing" in codes:
        if (
            _positive(current.get("skipped"))
            or _counts(power.get("missing"))
            or _counts(distances.get("missing"))
        ):
            return True
        if "nets" in length and type(length["nets"]) is int:
            if length["nets"] == 0 and result.get("lengths") == []:
                return True
            if (
                length["nets"] > 0
                and "major" in length
                and length["major"] is None
                and length.get("stackup") is None
            ):
                return True
        inputs = _map(result.get("inputs"))
        pairs = _rows(result.get("distances"))
        if (
            "board thickness" in {i.where for i in issues if i.code == "analysis.input-missing"}
            and _positive(distances.get("pairs"))
            and distances.get("pairs") == len(pairs)
            and "board_thickness" in inputs
            and inputs["board_thickness"] is None
            and "board_thickness_source" in inputs
            and inputs["board_thickness_source"] is None
            and isinstance(inputs.get("kinds"), (list, tuple))
            and "creepage" in inputs["kinds"]
            and any(
                isinstance(row.get("net_a"), str)
                and bool(row["net_a"])
                and isinstance(row.get("net_b"), str)
                and bool(row["net_b"])
                and row["net_a"] != row["net_b"]
                and "creepage" in row
                and row["creepage"] is None
                for row in pairs
            )
        ):
            return True
        places = {issue.where for issue in issues if issue.code == "analysis.input-missing"}
        if "pair selection" in places and distances.get("pairs") == 0 and result.get("distances") == []:
            return True
    if "analysis.item-unsupported" in codes and _counts(distances.get("unsupported")):
        return True
    # These named analysis reports expose explicit counts of unmeasured/unsolved rows.
    for name in (
        "ties",
        "domains",
        "crossings",
        "returns",
        "decoupling",
        "connectivity",
        "bodies",
        "relief",
        "dead",
        "coupling",
        "necks",
        "loops",
        "balance",
        "split",
    ):
        state = _map(summary.get(name))
        if codes & {"analysis.input-missing", "analysis.item-unsupported", "analysis.split-unconverged"}:
            if (
                any(_positive(state.get(key)) for key in ("skipped", "not_judged", "unsolved", "unknown"))
                or _counts(state.get("unsupported"))
                or _counts(state.get("missing"))
            ):
                return True
    return False


def _stage_limits(stages: object, issues: tuple[Issue, ...]) -> bool:
    codes = {issue.code for issue in issues}
    for stage in _rows(stages):
        if _map(stage.get("evidence")).get("level") != "UNVERIFIED":
            continue
        name, status = stage.get("name"), stage.get("status")
        state = _map(stage.get("summary"))
        if name == "circuit.rules" and "H-G-CIRCUIT-RULES" in _map(stage.get("evidence")).get(
            "hypotheses", ()
        ):
            for requirement in _rows(state.get("requirements")):
                limit = _map(requirement.get("limit"))
                if (
                    "circuit.value-unknown" in codes
                    and requirement.get("status") == "unknown"
                    and "value" in requirement
                    and requirement["value"] is None
                    and isinstance(requirement.get("missing"), str)
                    and bool(requirement["missing"])
                ):
                    return True
                if (
                    limit.get("source") == "device"
                    and limit.get("evidence") == "UNVERIFIED"
                    and isinstance(limit.get("basis"), str)
                    and bool(limit["basis"])
                    and bool(_map(limit.get("range")))
                ):
                    return True
        if name == "copper.clearance":
            if "copper.clearance-unset" in codes and _positive(state.get("unset_pairs")):
                return True
            if "copper.item-unsupported" in codes and (
                _positive(state.get("unpoured")) or _counts(state.get("unsupported"))
            ):
                return True
            rules = _map(state.get("rules"))
            if (
                "copper.rules-incomplete" in codes
                and rules
                and (
                    rules.get("min_clearance") is None
                    or bool(rules.get("unread"))
                    or _positive(rules.get("opaque_clearance_rules"))
                )
            ):
                return True
        if name == "length.rules" and "length.input-missing" in codes:
            if "major" in state and state["major"] is None or "stackup" in state and state["stackup"] is None:
                return True
        if (
            name == "topology.rules"
            and "topology.input-missing" in codes
            and _positive(state.get("not_judged"))
        ):
            return True
        if name == "zone.fill":
            if (
                "zone.unfilled" in codes
                and _positive(state.get("unfilled"))
                or "zone.fill-stale" in codes
                and _positive(state.get("stale"))
            ):
                return True
            if (
                "zone.fill-unchecked" in codes
                and status == "skipped"
                and stage.get("reason") in ("oracle-unsupported", "oracle-unstable")
            ):
                return True
        if name == "drc.kicad":
            if "check.oracle-failed" in codes and state.get("violations_judged") is False:
                return True
            if state.get("canary") in ("absent", "unknown") and any(
                code.endswith((".drc.rules-not-loaded", ".drc.rules-unchecked")) for code in codes
            ):
                return True
        if (
            name == "roundtrip.rt2"
            and state.get("judged") is False
            and codes & {"check.rt2-unstable", "check.oracle-failed"}
        ):
            return True
        if (
            name == "render"
            and "render.failed" in codes
            and "views" in state
            and len(_rows(state["views"])) < 4
        ):
            return True
        # A named failed oracle/copy stage is an explicitly unjudged report, not a DRC finding.
        if status == "errors":
            if (
                name in ("erc.kicad", "zone.fill", "netlist.assignment_compare", "parity")
                and "check.oracle-failed" in codes
            ):
                return True
            if name == "roundtrip.rta0" and "check.rta0-failed" in codes:
                return True
    return False


def _all_skipped(stages: object) -> bool:
    """CheckReport serialises only selected stages; wholly skipped reports claim no judgment."""
    from fenolite.checks.documents import ALL_DOCUMENT_STAGES
    from fenolite.checks.stages import STAGE_ORDER, StageSkip

    rows = _rows(stages)
    if not rows:
        return False
    names = {row.get("name") for row in rows if isinstance(row.get("name"), str)}
    if len(names) != len(rows) or not names <= set((*STAGE_ORDER, *ALL_DOCUMENT_STAGES)):
        return False
    reasons = get_args(StageSkip)
    return all(
        row.get("status") == "skipped"
        and row.get("reason") in reasons
        and row.get("summary") == {}
        and row.get("evidence") == {"level": "UNVERIFIED", "oracle": None, "hypotheses": []}
        for row in rows
    )


def _conversion_losses(result: Mapping[str, Any], issues: tuple[Issue, ...]) -> bool:
    report = _map(result.get("report"))
    kinds = {issue.where for issue in issues if issue.code == "convert.lossy"}
    return report.get("lossy") is True and any(
        isinstance(row.get("kind"), str)
        and row["kind"] in kinds
        and _positive(row.get("lost"))
        and any(
            reason.get("outcome") == "lost"
            and _positive(reason.get("count"))
            and isinstance(reason.get("reason"), str)
            and bool(reason["reason"])
            for reason in _rows(row.get("reasons"))
        )
        for row in _rows(report.get("rows"))
    )


def _pick_rows(result: Mapping[str, Any], issues: tuple[Issue, ...]) -> bool:
    limited = {issue.where for issue in issues if issue.code == "pick.row-unverified"}
    for key in ("picks", "candidates"):
        if any(
            isinstance(row.get("row"), str)
            and row["row"] in limited
            and row.get("evidence") in ("UNKNOWN", "UNVERIFIED")
            for row in _rows(result.get(key))
        ):
            return True
    return any(
        isinstance(row.get("id"), str)
        and row["id"] in limited
        and isinstance(row.get("file"), str)
        and "/devices/proposed/" in "/" + row["file"]
        and row["file"].endswith(".toml")
        for row in _rows(result.get("proposed"))
    )


def _seed(result: Mapping[str, Any], issues: tuple[Issue, ...]) -> bool:
    source = result.get("source")
    items = result.get("items")
    if (
        result.get("schema") != "fenolite.library-seed.v0"
        or result.get("evidence") != "UNVERIFIED"
        or not isinstance(source, str)
        or re.fullmatch(r"D-\d{4}", source) is None
        or not isinstance(items, (list, tuple))
        or not any(issue.code == "library.seed-unverified" and issue.where == source for issue in issues)
    ):
        return False
    rows = _rows(result.get("items"))
    if not rows:
        return any(issue.code == "library.seed-skipped" for issue in issues)
    return all(
        row.get("kind") in ("symbol", "footprint", "device")
        and all(isinstance(row.get(key), str) and bool(row[key]) for key in ("id", "version", "element"))
        for row in rows
    )


def _finite_budget(value: object, *, positive: bool) -> bool:
    if type(value) not in (int, float):
        return False
    number = cast(int | float, value)
    return math.isfinite(number) and (number > 0 if positive else number >= 0)


def _route(result: Mapping[str, Any], issues: tuple[Issue, ...]) -> bool:
    """An actual open connection or unattempted/exhausted run with its existing limitation issue."""
    places = {issue.where for issue in issues if issue.code == "route.unrouted"}
    if _positive(_map(result.get("connections")).get("after")) and any(
        isinstance(row.get("net"), str) and row["net"] in places and bool(_rows(row.get("connections")))
        for row in _rows(result.get("open"))
    ):
        return True
    if not any(issue.code == "route.budget-exhausted" for issue in issues):
        return False
    remaining, selected = result.get("not_attempted"), result.get("selected")
    if (
        isinstance(remaining, (list, tuple))
        and remaining
        and isinstance(selected, (list, tuple))
        and all(
            isinstance(net, str) and bool(net) and net in cast(list[object] | tuple[object, ...], selected)
            for net in cast(list[object] | tuple[object, ...], remaining)
        )
    ):
        return True
    budget = _map(result.get("budget"))
    return (
        budget.get("exhausted") is True
        and _finite_budget(budget.get("seconds"), positive=True)
        and _finite_budget(budget.get("spent"), positive=False)
    )


def incomplete_reply(command: str, result: Mapping[str, Any], issues: tuple[Issue, ...]) -> bool:
    """State plus its existing issue, or the explicitly wholly skipped check receipt."""
    if command == "route":
        return _route(result, issues)
    if command == "analyze":
        return _analysis(result, issues)
    if command in ("check", "ready"):
        stages = result.get("stages" if command == "check" else "checks")
        return _stage_limits(stages, issues) or command == "check" and _all_skipped(stages)
    if command == "pick":
        return _pick_rows(result, issues)
    if command == "library":
        return _seed(result, issues)
    codes = {issue.code for issue in issues}
    if command == "convert":
        return (
            "convert.no-verify" in codes and "equivalence" in result and result["equivalence"] is None
        ) or _conversion_losses(result, issues)
    if command == "family":
        return "family.suffix-opaque" in codes and any(
            isinstance(row.get("suffix"), str) and bool(row["suffix"]) for row in _rows(result.get("decoded"))
        )
    if command == "impedance":
        return (
            "impedance.no-stackup" in codes
            and _positive(_map(result.get("counts")).get("left_out"))
            and any(
                "mohm" in _map(row.get("estimate")) and _map(row.get("estimate"))["mohm"] is None
                for row in _rows(result.get("rows"))
            )
        )
    return False


__all__ = ["conservative_inputs", "incomplete_reply"]
