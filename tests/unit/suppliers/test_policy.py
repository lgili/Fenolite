# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Policies agree with primary-source review pages; authored fixtures grant no production rights."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from fenolite.pick.supplier_policy import POLICIES
from fenolite.suppliers.policy import policy_for

ROOT = Path(__file__).resolve().parents[3]


def test_policies_equal_their_review_pages() -> None:
    sources = (ROOT / "docs/evidence/sources.md").read_text(encoding="utf-8")
    for name in POLICIES:
        policy = policy_for(name)
        page = (ROOT / f"docs/formats/suppliers/{name}.md").read_text(encoding="utf-8")
        block = re.search(r"```toml\n(.*?)```", page, re.DOTALL)
        assert block is not None
        data = tomllib.loads(block.group(1))
        assert data == {
            "name": name,
            "ready": policy.ready,
            "cache": policy.cache,
            "max_age_s": policy.max_age_s,
            "terms_max_age_s": "unknown",
            "terms": list(policy.terms),
            "persist": list(policy.persist),
            "per_minute": policy.rate.per_minute,
            "per_day": policy.rate.per_day or "unknown",
            "attribution": policy.attribution,
            "evidence": policy.evidence,
        }
        assert not policy.ready and policy.persist == () and policy.cache == "none"
        assert all(source in sources for source in (*policy.terms, *POLICIES[name]["sources"]))


def test_fixtures_are_authored_and_registered() -> None:
    manifest = tomllib.loads((ROOT / "tests/data/MANIFEST.toml").read_text(encoding="utf-8"))
    registered = {row["path"] for row in manifest["file"]}
    for path in (ROOT / "tests/fixtures/suppliers").rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["_fixture"]["SPDX-License-Identifier"] == "CC0-1.0"
        assert "Authored for Fenolite" in data["_fixture"]["authored"]
        sidecar = path.with_suffix(".source.toml")
        source = tomllib.loads(sidecar.read_text(encoding="utf-8"))
        assert source["origin"] == "authored" and source["licence"] == "CC0-1.0"
        assert source["source"] in (ROOT / "docs/evidence/sources.md").read_text(encoding="utf-8")
        assert (
            path.relative_to(ROOT).as_posix() in registered
            and sidecar.relative_to(ROOT).as_posix() in registered
        )
