# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nexar basic search mapping (S-1223..S-1226); production rights remain gated."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fenolite.core.partquery import PartQuery
from fenolite.suppliers._oauth import bearer
from fenolite.suppliers.base import SupplierPlugin, array_at, object_at, text_at
from fenolite.suppliers.credentials import Secret, hint
from fenolite.suppliers.errors import CredentialsRejected, ResponseShapeError
from fenolite.suppliers.http import Client, Request
from fenolite.suppliers.rows import Candidate


class Nexar(SupplierPlugin):
    name = "nexar"

    def search(
        self, query: PartQuery, limit: int, client: Client, keys: Mapping[str, Secret]
    ) -> tuple[Candidate, ...]:
        token = bearer(client, keys, "https://identity.nexar.com/connect/token", scope="supply.domain")
        # JSON string quoting also quotes a GraphQL string literal; user text cannot add selections.
        document = (
            "query FenoliteSupplier { supSearch(q: "
            + json.dumps(query.text())
            + ", limit: "
            + str(limit)
            + ") { results { part { mpn manufacturer { name } "
            "sellers { company { name } offers { inventoryLevel prices { quantity price currency } } } "
            "} } } }"
        )
        data = client.request_json(
            Request(
                "https://api.nexar.com/graphql",
                "POST",
                {"Content-Type": "application/json", "Authorization": "Bearer " + token.reveal()},
                json.dumps({"query": document}).encode("utf-8"),
            )
        )
        errors = array_at(data, "errors", self.name) if "errors" in data else []
        if errors:
            if any(
                isinstance(error.get("extensions"), dict)
                and error["extensions"].get("code") in ("AuthInvalidToken", "AuthExpiredToken")
                for error in errors
            ):
                raise CredentialsRejected("nexar: access token was refused", hint=hint(self.name))
            raise ResponseShapeError("nexar: GraphQL response contains source errors")
        found = object_at(object_at(data, "data", self.name), "supSearch", self.name)
        result: list[Candidate] = []
        for row in array_at(found, "results", self.name)[:limit]:
            part = object_at(row, "part", self.name)
            sellers = array_at(part, "sellers", self.name)
            for seller in sellers:
                text_at(object_at(seller, "company", self.name), "name", self.name)
                for offer in array_at(seller, "offers", self.name):
                    array_at(offer, "prices", self.name)
            result.append(
                Candidate(
                    text_at(part, "mpn", self.name),
                    text_at(object_at(part, "manufacturer", self.name), "name", self.name),
                    offer={"sellers": sellers},
                )
            )
        return tuple(result)
