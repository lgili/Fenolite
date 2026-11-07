# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Record and source rules for data-only library items (c0266, docs/library-devices.md)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fenolite.catalog.records import (
    DeviceRecord,
    PinsRecord,
    ProposalOrigin,
    Record,
    kind_of,
    parse_header,
    parse_record,
    record_digest,
)
from fenolite.core.errors import FormatError, Issue
from fenolite.library.codes import issue
from fenolite.library.importer.shipping import shippable
from fenolite.library.proposals import proposal_outputs_current

if TYPE_CHECKING:
    from fenolite.library.audit import Found

RECORD_KINDS = {"symbol": "pins", "footprint": "package", "device": "device"}
SOURCE_FIELDS = ("title", "url", "licence", "retrieved", "used")


def _proposal_issues(record: Record, folder: Path) -> list[Issue]:
    """c0265 proposals require both current human review and the proposal module's exact seal check.

    Reuse the proposal module's normalization and exact output hashes; never approximate its seals.
    """
    if not isinstance(record.header.origin, ProposalOrigin):
        return []
    header = record.header
    reviewed = any(
        review.version == header.version and (review.record_sha256 or review.digest) == record_digest(record)
        for review in header.reviewed_by
    )
    if not reviewed:
        return [
            issue(
                "library.not-shippable",
                f"{header.id}: a proposal requires current digest-bound human review",
                where=header.id,
            )
        ]
    context = record if isinstance(record, DeviceRecord) else None
    if context is None and kind_of(record) in {"pins", "package"}:
        try:
            canonical = parse_record((folder / f"{kind_of(record)}.toml").read_text(encoding="utf-8"))
            candidate = parse_record((folder / "device.toml").read_text(encoding="utf-8"))
            if record_digest(canonical) == record_digest(record) and isinstance(candidate, DeviceRecord):
                context = candidate
        except (FormatError, OSError, UnicodeError):
            pass
    current = context is not None and proposal_outputs_current(context, folder)
    if not current:
        return [
            issue(
                "library.not-shippable",
                f"{header.id}: proposal output seals are missing, stale or unavailable",
                where=header.id,
            )
        ]
    return []


def source_ids(root: Path) -> frozenset[str]:
    """Validate the external library's D-id register; never consult the shipped S-id register."""
    path = root / "sources.toml"
    if not path.is_file():
        return frozenset()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        sources = raw.get("sources", {})
        if not isinstance(sources, dict):
            raise ValueError("sources must be a table")
        sources = cast(dict[str, object], sources)
        for key, value in sources.items():
            if not re.fullmatch(r"D-\d{4}", key) or not isinstance(value, dict):
                raise ValueError(f"{key}: expected D-NNNN source table")
            row = cast(dict[str, object], value)
            if row.get("id", key) != key or any(
                not isinstance(row.get(f), str) or not row[f] for f in SOURCE_FIELDS
            ):
                raise ValueError(f"{key}: requires id, {', '.join(SOURCE_FIELDS)}")
        return frozenset(sources)
    except (ValueError, OSError, UnicodeError) as exc:
        raise FormatError(f"sources.toml: {exc}", file="sources.toml") from None


def record_issues(root: Path, found: Found, registered: frozenset[str]) -> list[Issue]:
    """Validate one record payload and its item identity, dependencies and registered sources."""
    item = found.item
    if item is None or item.kind not in RECORD_KINDS:
        return []
    issues: list[Issue] = []
    where = found.path
    payloads = [
        (name, data)
        for name, data in found.files.items()
        if name.endswith(".toml") and name != "VERSIONS.toml"
    ]
    if len(payloads) != 1:
        return [issue("library.provenance-invalid", f"{where}: one record payload is required", where=where)]
    name, data = payloads[0]
    path = f"{where}/{name}"
    try:
        raw = tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        return [issue("library.provenance-invalid", f"{path}: {exc}", where=path)]
    if not shippable(raw):
        return [
            issue(
                "library.not-shippable",
                f"{path}: local imported or source-terms data cannot enter a release",
                where=path,
            )
        ]
    if str(raw.get("id", "")).startswith("Fenolite:") or item.id.startswith("Fenolite:"):
        return [
            issue(
                "library.provenance-invalid",
                f"{path}: the namespace Fenolite is reserved for the shipped catalog",
                where=path,
            )
        ]
    try:
        family = item.kind == "device" and raw.get("schema") in {"fenolite.family.v0", "fenolite.family.v1"}
        if family:
            record = None
            header = parse_header(raw, "device", file=path)
            actual_kind = "device"
        else:
            record = parse_record(data.decode("utf-8"), file=path)
            header = record.header
            actual_kind = kind_of(record)
    except FormatError as exc:
        return [issue("library.provenance-invalid", f"{path}: {exc}", where=path)]
    if (actual_kind, header.id, header.version, header.licence) != (
        RECORD_KINDS[item.kind],
        item.id,
        item.version,
        item.spdx,
    ):
        issues.append(
            issue(
                "library.provenance-invalid",
                f"{path}: record kind/id/version/licence must equal its item",
                where=path,
            )
        )
    sources = (*header.sources, *(s for ids in header.sources_by.values() for s in ids))
    for source in sources:
        if source not in registered:
            raise FormatError(
                f"{header.id}: unregistered source {source} in {path}", file=path, locator="sources"
            )
    provenance: Mapping[str, object] = found.provenance or {}
    if provenance.get("origin") == "authored":
        if item.spdx != "CC0-1.0" or found.family != "cc0" or not sources:
            issues.append(
                issue(
                    "library.provenance-invalid",
                    f"{path}: authored device-kind data requires CC0-1.0, cc0 and registered D- sources",
                    where=path,
                )
            )
    if isinstance(record, PinsRecord) and record.symbol is None:
        issues.append(
            issue("library.provenance-invalid", f"{path}: symbol item requires [symbol] drawing", where=path)
        )
    if record is not None:
        issues += _proposal_issues(record, root / found.path)
    if isinstance(record, DeviceRecord):
        expected = {("symbol", record.device.symbol), ("footprint", record.device.footprint)}
        actual = {(d.kind, d.id) for d in item.depends}
        if expected != actual:
            issues.append(
                issue(
                    "library.provenance-invalid",
                    f"{path}: depends must name exactly its symbol and footprint items",
                    where=path,
                )
            )
    return issues
