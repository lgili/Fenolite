# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Explicit supplier lookups, guarded by documented policy and per-run credentials (c0267)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fenolite.core.errors import Issue
from fenolite.core.partquery import PartQuery
from fenolite.pick.grammar.schema import GrammarFamily
from fenolite.pick.propose import RICH_SUPPLIER_API, SupplierDraft, SupplierLookup
from fenolite.suppliers import credentials
from fenolite.suppliers.cache import ProcessCache
from fenolite.suppliers.credentials import Secret
from fenolite.suppliers.errors import CredentialsMissing, ResponseShapeError, SupplierError
from fenolite.suppliers.http import Client, Transport
from fenolite.suppliers.policy import policy_for
from fenolite.suppliers.rows import Candidate, proposal_row


class SupplierPlugin:
    name = ""
    sends_data_offsite = True
    proposal_api = RICH_SUPPLIER_API

    def __init__(self) -> None:
        self.policy = policy_for(self.name)
        self.cache: ProcessCache[tuple[Candidate, ...]] = ProcessCache(self.policy)

    def available(self) -> bool:
        return self.policy.ready

    def search(
        self, query: PartQuery, limit: int, client: Client, keys: Mapping[str, Secret]
    ) -> tuple[Candidate, ...]:
        raise CredentialsMissing(f"{self.name}: documented response mapping is unavailable")

    def lookup(
        self,
        query: PartQuery,
        *,
        limit: int = 20,
        timeout: float = 30,
        timestamp: str,
        families: Sequence[GrammarFamily] = (),
        transport: Transport | None = None,
    ) -> SupplierLookup:
        if not self.policy.ready:
            raise CredentialsMissing(
                f"{self.name}: {self.policy.reason}",
                hint="see docs/formats/suppliers/ before enabling this source",
            )
        if not 1 <= limit <= 50:
            raise ValueError("supplier result limit must be between 1 and 50")
        keys = credentials.lookup(self.name)
        client = Client(self.policy, transport, timeout=timeout)
        client.secrets.extend(keys.values())
        cache_key = f"{query.text()}:{limit}"
        candidates = self.cache.get(cache_key)
        if candidates is None:
            try:
                candidates = self.search(query, limit, client, keys)
            except SupplierError as error:
                # Mapping errors follow successful HTTP replies too (for example GraphQL errors).
                # Retain any earlier pacing warning just as the HTTP error paths do.
                error.issues = tuple(client.issues) + tuple(
                    issue for issue in error.issues if issue not in client.issues
                )
                raise
        drafts: list[SupplierDraft] = []
        issues = list(client.issues)
        clean_candidates: list[Candidate] = []
        for item in candidates[:limit]:
            # A response may echo a credential. Filter all identity, offer and reported strings too.
            data = {
                "mpn": item.mpn,
                "manufacturer": item.manufacturer,
                "datasheet": item.datasheet,
                "reported": dict(item.reported),
                "offer": dict(item.offer),
            }
            clean: dict[str, Any] = json.loads(credentials.redact(json.dumps(data), client.secrets))
            candidate = Candidate(**clean)
            clean_candidates.append(candidate)
            draft, found = proposal_row(
                candidate, self.policy, query=query.text(), timestamp=timestamp, families=families
            )
            drafts.append(draft)
            issues.extend(found)
        self.cache.put(cache_key, tuple(clean_candidates))
        if not candidates:
            issues.append(Issue("supplier.no-results", "info", f"{self.name}: no results"))
        return SupplierLookup(tuple(drafts), tuple(issues), self.policy.sends)

    def propose(self, query: PartQuery) -> Sequence[Mapping[str, str]]:
        # Existing third-party Supplier.propose implementations remain accepted by the CLI.
        raise CredentialsMissing(f"{self.name}: use the explicit rich supplier proposal command")


def object_at(data: Any, key: str, source: str) -> Any:
    if not isinstance(data, dict) or key not in data:
        raise ResponseShapeError(f"{source}: response is missing documented key {key}")
    return cast(dict[str, Any], data)[key]


def text_at(data: Any, key: str, source: str, *, optional: bool = False) -> str:
    if optional and isinstance(data, dict) and cast(dict[str, Any], data).get(key) in (None, ""):
        return ""
    value = object_at(data, key, source)
    if not isinstance(value, str):
        raise ResponseShapeError(f"{source}: documented field {key} is not text")
    return value


def array_at(data: Any, key: str, source: str) -> list[dict[str, Any]]:
    value = object_at(data, key, source)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in cast(list[Any], value)):
        raise ResponseShapeError(f"{source}: documented field {key} is not an object array")
    return cast(list[dict[str, Any]], value)
