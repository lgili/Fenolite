# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bind human acceptance to current proposals, their document and generated files (c0265)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fenolite.catalog.records import DeviceRecord, ProposalOrigin, parse_record
from fenolite.core.errors import FormatError, Issue
from fenolite.library.codes import issue
from fenolite.library.proposals.agreement import agreement
from fenolite.library.proposals.checks import bind, self_check
from fenolite.library.proposals.convert import GenerationRefused, convert, seal
from fenolite.library.proposals.schema import Proposal, datasheet_bytes, parse_proposal


def proposal_outputs_current(record: DeviceRecord, folder: Path) -> bool:
    """Check the three canonical record seals and raw-byte output hashes; no PDF or review is needed."""
    origin = record.header.origin
    if not isinstance(origin, ProposalOrigin):
        return False
    try:
        if seal(record).header.origin != origin:
            return False
        expected = {"proposal.toml", f"{record.header.name}.kicad_sym", f"{record.header.name}.kicad_mod"}
        if len(origin.proposer) == 2:
            expected.add("proposal-2.toml")
        if not expected <= {output.file for output in origin.output}:
            return False
        for name in ("device.toml", "pins.toml", "package.toml"):
            current = parse_record((folder / name).read_text(), allow_stale_reviews=True)
            provenance = current.header.origin
            if not isinstance(provenance, ProposalOrigin) or seal(current).header.origin != provenance:
                return False
            if name == "device.toml" and provenance != origin:
                return False
        for output in origin.output:
            path = folder / output.file
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != output.sha256:
                return False
    except (OSError, ValueError, FormatError):
        return False
    return True


def review_gate(folder: Path, datasheet: Path | None, *, checked: bool = True) -> list[Issue]:
    found: list[Issue] = []
    try:
        device = parse_record((folder / "device.toml").read_text(), allow_stale_reviews=True)
        if not isinstance(device, DeviceRecord) or not isinstance(device.header.origin, ProposalOrigin):
            return []
        origin = device.header.origin
        try:
            pdf = datasheet_bytes(datasheet) if datasheet is not None else None
        except (OSError, FormatError):
            pdf = None
        if pdf is None or hashlib.sha256(pdf).hexdigest() != origin.datasheet_sha256:
            found.append(
                issue(
                    "proposal.review-datasheet",
                    "review needs the exact datasheet supplied to the proposal",
                    where=origin.datasheet,
                )
            )
        proposals: list[Proposal] = []
        for name in ("proposal.toml", "proposal-2.toml"):
            path = folder / name
            if not path.is_file():
                continue
            proposal = parse_proposal(path.read_text(), file=name)
            proposals.append(proposal)
            if proposal.data.get("doubt"):
                found.append(
                    issue(
                        "proposal.review-doubt",
                        "open doubts must be resolved against the datasheet",
                        where=name,
                    )
                )
            if proposal.uncited:
                found.append(
                    issue("proposal.review-uncited", f"uncited rows: {proposal.uncited}", where=name)
                )
            if any(i.severity == "error" for i in self_check(proposal)) or (
                pdf is not None and bind(proposal, pdf)
            ):
                checked = False
        if not proposals or (proposals and any(i.severity == "error" for i in agreement(proposals))):
            checked = False
        if checked and pdf is not None:
            try:
                generated = convert(proposals, pdf, date=origin.date, licence=device.header.licence)
                if any(i.severity == "error" for i in generated.issues):
                    checked = False
            except GenerationRefused:
                checked = False
        checked = checked and proposal_outputs_current(device, folder)
    except (OSError, ValueError, FormatError) as error:
        checked = False
        found.append(
            issue(
                "proposal.review-unchecked",
                f"current proposal folder is not valid: {error}",
                where=folder.name,
            )
        )
    if not checked and not any(i.code == "proposal.review-unchecked" for i in found):
        found.append(
            issue(
                "proposal.review-unchecked",
                "current records and proposals must pass checks and retain their recorded content",
                where=folder.name,
            )
        )
    return found
