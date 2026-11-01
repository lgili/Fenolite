# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stable accepted content and review freshness (c0262, H-G-LIBRARY-REVIEW)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fenolite.model import canonical

_FREE_MAPS = frozenset({"properties", "native_ids", "attributes", "sources", "sources_by"})


def content_data(value: object) -> Any:
    """Normalize parsed values, omitting trust metadata rather than hashing presentation changes."""
    return _content_data(canonical.to_data(value), ())


def _content_data(data: Any, path: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        data = cast(dict[str, Any], data)
        free_map = any(part in _FREE_MAPS for part in path)
        envelope = path in {(), ("header",)}
        evidence_context = (
            envelope
            or path[-1:] in {("device",), ("provenance",)}
            or any(part in {"interface", "interfaces"} for part in path)
        )
        return {
            key: _content_data(member, (*path, key))
            for key, member in sorted(data.items())
            if free_map
            or not (
                (envelope and key in {"review", "reviewed_by", "previous_evidence"})
                or (evidence_context and key == "evidence")
            )
        }
    if isinstance(data, (list, tuple)):
        return [_content_data(member, (*path, "[]")) for member in cast(list[Any], data)]
    return data


def digest(
    value: object, *, definitions: Sequence[object] = (), dependencies: Mapping[str, str] | None = None
) -> str:
    """Hash canonical parsed content, exact generated geometry and referenced content digests."""
    payload = {
        "record": content_data(value),
        "definitions": [content_data(d) for d in definitions],
        "dependencies": dict(sorted((dependencies or {}).items())),
    }
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sheet_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def matches_sheet(prefix: str, current: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{12,64}", prefix)) and current.startswith(prefix.lower())


def is_stale(review: Mapping[str, Any], current_digest: str, current_sheet: str) -> bool:
    return review.get("digest") != current_digest or bool(
        review.get("sheet_sha256") and review["sheet_sha256"] != current_sheet
    )
