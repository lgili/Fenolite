# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DigiKey v4 keyword mapping (S-1100/S-1220); production rights remain gated."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fenolite.core.partquery import PartQuery
from fenolite.suppliers._oauth import bearer
from fenolite.suppliers.base import SupplierPlugin, array_at, text_at
from fenolite.suppliers.credentials import Secret
from fenolite.suppliers.errors import ResponseShapeError
from fenolite.suppliers.http import Client, Request
from fenolite.suppliers.rows import Candidate


class DigiKey(SupplierPlugin):
    name = "digikey"

    def search(
        self, query: PartQuery, limit: int, client: Client, keys: Mapping[str, Secret]
    ) -> tuple[Candidate, ...]:
        keywords = query.text()
        if len(keywords) > 250:
            raise ValueError("digikey: canonical query exceeds the documented 250-character limit")
        token = bearer(client, keys, "https://api.digikey.com/v1/oauth2/token")
        data = client.request_json(
            Request(
                "https://api.digikey.com/products/v4/search/keyword",
                "POST",
                {
                    "Content-Type": "application/json",
                    "X-DIGIKEY-Client-Id": keys["CLIENT_ID"].reveal(),
                    "Authorization": "Bearer " + token.reveal(),
                },
                json.dumps({"Keywords": keywords, "Limit": limit, "Offset": 0}).encode("utf-8"),
            )
        )
        result: list[Candidate] = []
        for part in array_at(data, "Products", self.name)[:limit]:
            manufacturer = part.get("Manufacturer")
            offer = {
                key: part[key] for key in ("UnitPrice", "QuantityAvailable", "ProductStatus") if key in part
            }
            if "ProductStatus" in offer and not isinstance(offer["ProductStatus"], dict):
                raise ResponseShapeError("digikey: documented field ProductStatus is not an object")
            if "ProductVariations" in part:
                offer["ProductVariations"] = array_at(part, "ProductVariations", self.name)
            result.append(
                Candidate(
                    text_at(part, "ManufacturerProductNumber", self.name),
                    text_at(manufacturer, "Name", self.name, optional=True)
                    if manufacturer is not None
                    else "",
                    text_at(part, "DatasheetUrl", self.name, optional=True),
                    {"Parameters": array_at(part, "Parameters", self.name)} if "Parameters" in part else {},
                    offer,
                )
            )
        return tuple(result)
