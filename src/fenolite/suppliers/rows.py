# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Identity-only supplier drafts, with optional grammar-owned review suggestions (c0267)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from fenolite.catalog.devices import device_text
from fenolite.core.errors import Issue
from fenolite.pick.grammar.candidates import candidate_record, checked
from fenolite.pick.grammar.decode import decode
from fenolite.pick.grammar.schema import GrammarFamily
from fenolite.pick.propose import SupplierDraft
from fenolite.suppliers.policy import SourcePolicy


@dataclass(frozen=True, slots=True)
class Candidate:
    mpn: str
    manufacturer: str = ""
    datasheet: str = ""
    reported: Mapping[str, Any] = field(default_factory=lambda: {})
    offer: Mapping[str, Any] = field(default_factory=lambda: {})


def proposal_row(
    candidate: Candidate,
    policy: SourcePolicy,
    *,
    query: str,
    timestamp: str,
    families: Sequence[GrammarFamily] = (),
) -> tuple[SupplierDraft, tuple[Issue, ...]]:
    if not candidate.mpn or len(candidate.mpn) > 200:
        raise ValueError("supplier identity needs a bounded nonempty MPN")
    identity = {
        key: getattr(candidate, key) for key in ("manufacturer", "mpn", "datasheet") if key in policy.persist
    }
    if "mpn" not in identity:
        raise ValueError("this source policy does not permit a durable identity draft")
    suggestion = None
    decoded_by = ""
    decoded = decode(candidate.mpn, [checked(family) for family in families])
    if len(decoded.decoded) == 1 and decoded.decoded[0].in_matrix and not decoded.decoded[0].candidate.suffix:
        found = decoded.decoded[0].candidate
        suggestion = device_text(candidate_record(found))
        decoded_by = f"{found.family.id} {found.family.version}"
    safe = re.sub(r"[^A-Za-z0-9_.+-]", "_", candidate.mpn)[:100]
    suffix = hashlib.sha256(candidate.mpn.encode("utf-8")).hexdigest()[:10]
    filename = f"{safe}-{suffix}.toml"
    values = {
        "schema": "fenolite.supplier-proposal.v0",
        "evidence": "UNVERIFIED",
        "licence": "see source terms",
        **identity,
    }
    provenance = {
        "source": f"supplier:{policy.name}",
        "query": query,
        "retrieved": timestamp,
        "attribution": policy.attribution,
    }
    if decoded_by:
        provenance["decoded_by"] = decoded_by

    def quote(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    lines = [
        "# SPDX-License-Identifier: NOASSERTION",
        "# Supplier identity proposal; review rights and datasheet before use.",
    ]
    lines += [f"{key} = {quote(value)}" for key, value in values.items()]
    lines += ["", "[provenance]", *(f"{key} = {quote(value)}" for key, value in provenance.items())]
    if suggestion is not None:
        lines += ["", "[decoded]", f"device_toml = {quote(suggestion)}"]
    persisted: dict[str, object] = {
        **identity,
        "file": filename,
        "attribution": policy.attribution,
        "complete": suggestion is not None,
        "decoded_by": decoded_by or None,
    }
    display = {**persisted, "reported": dict(candidate.reported), "offer": dict(candidate.offer)}
    issues = [Issue("supplier.proposed", "info", "identity draft planned for review", where=filename)]
    if suggestion is None:
        issues.append(
            Issue(
                "supplier.row-incomplete",
                "info",
                "review symbol, footprint, pins, kind, value and ratings",
                where=filename,
            )
        )
    if candidate.reported:
        issues.append(
            Issue(
                "supplier.unmapped", "info", "reported supplier parameters are display-only", where=filename
            )
        )
    return SupplierDraft(filename, "\n".join(lines) + "\n", display, persisted), tuple(issues)
