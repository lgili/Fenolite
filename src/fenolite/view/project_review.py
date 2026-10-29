# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Recorded checks and operation reports, with explicit scope for viewer review (c0239).

This is presentation of supplied evidence. It neither runs checks nor certifies a project. A matching
input hash binds only the named document, never every file of a multi-document project.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import Any, cast

from fenolite.core.errors import FormatError
from fenolite.view.check_overlay import STAGE_OF

_HASH = re.compile(r"[0-9a-f]{64}\Z")
CATEGORIES = (
    ("connectivity", "Netlist connectivity", ("parity", "netlist.assignment_compare")),
    ("erc", "Electrical rules (ERC)", ("erc.kicad",)),
    ("drc", "Board rules (DRC)", ("drc.kicad",)),
    ("clearance", "Copper clearance", ("copper.clearance",)),
    ("placement", "Placement rules", ("placement.rules",)),
    ("fill", "Zone fill", ("zone.fill",)),
    ("model", "Model validation", ("model.validate",)),
)


def _dict(value: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return cast("list[Any]", value) if isinstance(value, list) else []


def evidence(value: Any) -> str:
    """A report's original evidence label, without upgrading it."""
    data = _dict(value)
    level, oracle = str(data.get("level") or "UNKNOWN"), data.get("oracle")
    return f"{level}({oracle})" if oracle and "(" not in level else level


def read_report(data: Any, *, name: str = "") -> dict[str, Any]:
    """Validate a complete recorded convert/export envelope; never execute its command."""
    reply = _dict(data)
    if (
        reply.get("command") not in ("convert", "export")
        or type(reply.get("ok")) is not bool
        or not isinstance(reply.get("result"), dict)
        or not isinstance(reply.get("issues"), list)
        or not all(isinstance(item, dict) for item in reply["issues"])
    ):
        raise FormatError(f"{name or 'the report'} is not a complete convert or export reply", file=name)
    return reply


def _binding(reply: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    source, meta = _dict(reply.get("input")), _dict(scene.get("meta"))
    path, digest = str(source.get("path") or ""), str(source.get("sha256") or "")
    name = PurePosixPath(path.replace("\\", "/")).name
    matched = bool(
        _HASH.fullmatch(digest)
        and digest == meta.get("sha256")
        and name.casefold() == str(meta.get("name") or "").casefold()
    )
    if matched:
        note = "Matches this document's bytes only; other project files were not bound by this hash."
    elif digest:
        note = "Report input does not match this document and revision; results are historical."
    else:
        note = "Report has no input hash; its connection to this revision is unverified."
    return {"matched": matched, "path": path, "sha256": digest, "note": note}


def _issue_stage(issue: dict[str, Any]) -> str:
    code = str(issue.get("code") or "")
    if code == "check.report-limit":
        return "drc.kicad"
    return next((stage for prefix, stage in STAGE_OF if code.startswith(prefix)), "")


def _stages(reply: dict[str, Any], bound: dict[str, Any]) -> list[dict[str, Any]]:
    issues = [_dict(item) for item in _list(reply.get("issues"))]
    out: list[dict[str, Any]] = []
    recorded = [_dict(raw) for raw in _list(_dict(reply.get("result")).get("stages"))]
    names = [stage.get("name") for stage in recorded]
    for issue in issues:
        name = _issue_stage(issue)
        if name and name not in names:
            recorded.append(
                {"name": name, "reason": "A finding names this stage, but its stage record is missing."}
            )
            names.append(name)
    for raw in recorded:
        stage = _dict(raw)
        name = str(stage.get("name") or "")
        if not name:
            continue
        own = [item for item in issues if _issue_stage(item) == name]
        counts = {
            level: sum(item.get("severity") == level for item in own)
            for level in ("error", "warning", "info")
        }
        status, label = stage.get("status"), evidence(stage.get("evidence"))
        limits = _dict(stage.get("summary")).get("limits")
        reasons = [str(stage["reason"])] if stage.get("reason") else []
        if not bound["matched"]:
            reasons.append(bound["note"])
        if limits:
            reasons.append("Report counts are lower bounds; this stage was capped.")
        if label in {"UNKNOWN", "UNVERIFIED"}:
            reasons.append("Stage evidence is not available.")
        if counts["warning"]:
            reasons.append(f"{counts['warning']} warning(s) require review.")
        if status not in ("ok", "errors", "skipped"):
            reasons.append("The stage status is absent or unknown.")
        if status == "skipped":
            reasons.append("Stage was skipped; it was not a passing check.")
        state = "failed" if status == "errors" or counts["error"] else "limited" if reasons else "passed"
        out.append(
            {
                "name": name,
                "state": state,
                "status": status,
                "evidence": label,
                "reasons": reasons,
                "counts": counts,
                "limits": limits,
                "summary": _dict(stage.get("summary")),
            }
        )
    return out


def _card(key: str, title: str, required: tuple[str, ...], stages: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [stage for stage in stages if stage["name"] in required]
    missing = [name for name in required if not any(stage["name"] == name for stage in selected)]
    if not selected:
        state = "not-run"
    elif any(stage["state"] == "failed" for stage in selected):
        state = "failed"
    elif missing or any(stage["state"] != "passed" for stage in selected):
        state = "limited"
    else:
        state = "passed"
    return {"id": key, "title": title, "state": state, "stages": selected, "missing": missing}


def _operation(reply: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    command, result = reply["command"], _dict(reply.get("result"))
    bound = _binding(reply, scene)
    issues = [_dict(item) for item in _list(reply.get("issues"))]
    reasons = [] if bound["matched"] else [bound["note"]]
    label = evidence(reply.get("evidence"))
    if label in {"UNKNOWN", "UNVERIFIED"}:
        reasons.append("Report evidence is not available.")
    if not _dict(reply.get("receipt")).get("files"):
        reasons.append("No completed write receipt; this may be a dry-run plan.")
    if any(item.get("severity") == "warning" for item in issues):
        reasons.append("The operation reported warnings.")
    if command == "convert":
        equivalence = _dict(result.get("equivalence"))
        if not equivalence:
            reasons.append("Conversion equivalence was not verified.")
        if result.get("experimental") is not False:
            reasons.append("This conversion direction is experimental or unspecified.")
        if _dict(result.get("report")).get("lossy") is not False:
            reasons.append("The conversion reports losses or does not state its loss status.")
        if equivalence.get("unexplained") != 0:
            reasons.append("Unexplained conversion differences are present or unspecified.")
    else:
        reasons.append("Artifact generation does not attest successful readback or fabrication readiness.")
    failed = reply.get("ok") is False or any(item.get("severity") == "error" for item in issues)
    return {
        "id": command,
        "title": "Conversion" if command == "convert" else "Fabrication export",
        "state": "failed" if failed else "limited" if reasons else "passed",
        "stages": [],
        "missing": [],
        "evidence": label,
        "binding": bound,
        "reasons": reasons,
    }


def status(
    scene: dict[str, Any], check: dict[str, Any] | None = None, reports: Sequence[dict[str, Any]] = ()
) -> dict[str, Any]:
    """Status scoped to the current scene and supplied evidence; no absent check is a pass."""
    bound = _binding(check, scene) if check is not None else None
    stages = _stages(check, cast("dict[str, Any]", bound)) if check is not None else []
    meta = _dict(scene.get("meta"))
    cards = [
        {
            "id": "read",
            "title": "Read document",
            "state": "passed",
            "stages": [],
            "missing": [],
            "evidence": str(meta.get("evidence") or "UNKNOWN"),
            "reasons": ["The displayed document was read; this is not an electrical check."],
        }
    ]
    cards += [_card(key, title, required, stages) for key, title, required in CATEGORIES]
    for command in ("convert", "export"):
        reply = next((item for item in reports if item["command"] == command), None)
        cards.append(
            _operation(reply, scene)
            if reply is not None
            else {
                "id": command,
                "title": "Conversion" if command == "convert" else "Fabrication export",
                "state": "not-run",
                "stages": [],
                "missing": [],
            }
        )
    known = {name for _, _, names in CATEGORIES for name in names}
    cards.extend(
        _card(stage["name"], stage["name"], (stage["name"],), stages)
        for stage in stages
        if stage["name"] not in known
    )
    operation_findings: list[dict[str, Any]] = []
    for report in reports:
        for item in _list(report.get("issues")):
            issue = _dict(item)
            operation_findings.append(
                {
                    "code": str(issue.get("code") or ""),
                    "severity": str(issue.get("severity") or "info"),
                    "message": str(issue.get("message") or ""),
                    "hint": str(issue.get("hint") or ""),
                    "where": str(issue.get("where") or ""),
                    "stage": report["command"],
                    "evidence": evidence(report.get("evidence")),
                    "at": None,
                    "box": None,
                }
            )
    return {
        "cards": cards,
        "binding": bound,
        "stages": stages,
        "operation_findings": operation_findings,
        "note": "Recorded results for this document; no overall fabrication approval is implied.",
    }


__all__ = ["CATEGORIES", "read_report", "status"]
