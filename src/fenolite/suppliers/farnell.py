# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Source-documented element14 keyword mapping (S-1108); production rights gate stays closed."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode

from fenolite.core.partquery import PartQuery
from fenolite.suppliers.base import SupplierPlugin, array_at, object_at, text_at
from fenolite.suppliers.credentials import Secret
from fenolite.suppliers.errors import ResponseShapeError
from fenolite.suppliers.http import Client, Request
from fenolite.suppliers.rows import Candidate


class Farnell(SupplierPlugin):
    name = "farnell"

    def search(
        self, query: PartQuery, limit: int, client: Client, keys: Mapping[str, Secret]
    ) -> tuple[Candidate, ...]:
        parameters = {
            "term": "any:" + query.text(),
            "storeInfo.id": "uk.farnell.com",
            "callInfo.apiKey": keys["API_KEY"].reveal(),
            "callInfo.responseDataFormat": "json",
            "resultsSettings.offset": "0",
            "resultsSettings.numberOfResults": str(limit),
            "resultsSettings.responseGroup": "medium",
        }
        data = client.request_json(
            Request("https://api.element14.com/catalog/products?" + urlencode(parameters))
        )
        rows = array_at(object_at(data, "keywordSearchReturn", self.name), "products", self.name)
        result: list[Candidate] = []
        for part in rows[:limit]:
            sheets = array_at(part, "datasheets", self.name) if "datasheets" in part else []
            datasheet = text_at(sheets[0], "url", self.name) if sheets else ""
            offer: dict[str, object] = {}
            if "stock" in part:
                if not isinstance(part["stock"], dict):
                    raise ResponseShapeError("farnell: documented field stock is not an object")
                offer["stock"] = part["stock"]
            if "prices" in part:
                offer["prices"] = array_at(part, "prices", self.name)
            if "productStatus" in part:
                offer["productStatus"] = text_at(part, "productStatus", self.name, optional=True)
            result.append(
                Candidate(
                    text_at(part, "translatedManufacturerPartNumber", self.name),
                    text_at(part, "brandName", self.name, optional=True),
                    datasheet,
                    {"attributes": array_at(part, "attributes", self.name)} if "attributes" in part else {},
                    offer,
                )
            )
        return tuple(result)
