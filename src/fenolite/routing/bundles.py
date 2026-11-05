# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical identity of atomic route alternatives; no decision may detach a member."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

from fenolite.core.ids import content_hash
from fenolite.model.canonical import to_data
from fenolite.routing.protocol import Bundle, Candidate


def make(members: Sequence[Candidate], fingerprint: str) -> Bundle:
    """Bind complete member payloads to an input digest; independent of generation order."""
    if re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise ValueError("bundle input fingerprint must be SHA-256")
    ordered = tuple(sorted(members, key=lambda candidate: (candidate.subject, candidate.id)))
    if len(ordered) < 2 or len({c.subject for c in ordered}) != len(ordered):
        raise ValueError("a bundle needs at least two distinct subjects")
    if len({c.id for c in ordered}) != len(ordered):
        raise ValueError("bundle candidate ids must be distinct")
    if any(c.bundle for c in ordered):
        raise ValueError("nested or already assigned bundle members are refused")
    payload = [to_data(c) for c in ordered]
    ident = "b-" + content_hash("fenolite.route-bundle.v0", fingerprint, payload)[:16]
    return Bundle(ident, fingerprint, tuple(replace(c, bundle=ident) for c in ordered))


def data(bundle: Bundle) -> dict[str, Any]:
    """Additive proposal metadata; member geometry remains in the existing candidate rows."""
    return {
        "id": bundle.id,
        "fingerprint": bundle.fingerprint,
        "members": [c.id for c in bundle.members],
        "subjects": [c.subject for c in bundle.members],
    }
