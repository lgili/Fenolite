# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source-documented Mouser keyword mapping (S-1104); production rights gate stays closed."""

from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.parse import urlencode

from fenolite.core.partquery import PartQuery
from fenolite.suppliers.base import SupplierPlugin, array_at, object_at, text_at
from fenolite.suppliers.credentials import Secret
from fenolite.suppliers.http import Client, Request
from fenolite.suppliers.rows import Candidate


class Mouser(SupplierPlugin):
    name = "mouser"

    def search(
        self, query: PartQuery, limit: int, client: Client, keys: Mapping[str, Secret]
    ) -> tuple[Candidate, ...]:
        url = "https://api.mouser.com/api/v1/search/keyword?" + urlencode(
            {"apiKey": keys["API_KEY"].reveal()}
        )
        body = json.dumps(
            {"SearchByKeywordRequest": {"keyword": query.text(), "records": limit, "startingRecord": 0}}
        ).encode()
        data = client.request_json(Request(url, "POST", {"Content-Type": "application/json"}, body))
        found = object_at(data, "SearchResults", self.name)
        rows = array_at(found, "Parts", self.name)
        return tuple(
            Candidate(
                text_at(part, "ManufacturerPartNumber", self.name),
                text_at(part, "Manufacturer", self.name, optional=True),
                text_at(part, "DataSheetUrl", self.name, optional=True),
                {"ProductAttributes": object_at(part, "ProductAttributes", self.name)}
                if "ProductAttributes" in part
                else {},
                {key: part[key] for key in ("Availability", "PriceBreaks", "LifecycleStatus") if key in part},
            )
            for part in rows[:limit]
        )
