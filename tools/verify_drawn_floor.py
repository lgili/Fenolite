# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Require same-commit native9/native10 complete floor-copy bridge artifacts (c0347)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tomllib
from pathlib import Path

SIGNATURE = ("pins", "groups", "pins_sha256", "partition_sha256", "named_sha256")
COMPARISONS = ("partition", "lowered_partition", "lowered_native_partition")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify(folder: Path, manifest: Path, commit: str) -> int:
    data = manifest.read_bytes()
    manifest_sha = hashlib.sha256(data).hexdigest()
    declarations = {item["id"]: item for item in tomllib.loads(data.decode())["file"]}
    expected = {
        key
        for key, value in declarations.items()
        if "sch-old" in value.get("uses", []) and "origin:kicad-demos" in value.get("uses", [])
    }
    require(bool(expected), "no declared floor rows")
    records = {}
    for path in folder.rglob("drawn-floor.json"):
        for record in json.loads(path.read_text(encoding="utf-8")):
            ident = record["id"]
            require(
                ident in expected and record["schema"] == "fenolite.drawn-floor.v0", "unexpected floor record"
            )
            require(record["code_commit"] == commit, f"{ident}: code commit differs")
            require(record["manifest_sha256"] == manifest_sha, f"{ident}: manifest differs")
            require(record["originals_unchanged"] is True, f"{ident}: changed originals")
            require(record["major"] in (9, 10), f"{ident}: unknown native major")
            require(
                record["native_version"].startswith(f"{record['major']}."), f"{ident}: native version differs"
            )
            require(
                record["original"]["status"] == "refused"
                and record["original"]["expectation"] == "original-reader-floor"
                and record["original"]["refusal"]["code"] == "FEN-3003",
                f"{ident}: missing original refusal",
            )
            require(
                record["original"]["input_sha256"] == declarations[ident]["sha256"],
                f"{ident}: original digest",
            )
            inputs = record["inputs"]
            require(len({item["id"] for item in inputs}) == len(inputs), f"{ident}: duplicate inputs")
            for item in inputs:
                require(
                    item["id"] in declarations and item["sha256"] == declarations[item["id"]]["sha256"],
                    f"{ident}: unchecked input",
                )
            context = record["context"]
            require(not context["errors"] and context["target_instances"] > 0, f"{ident}: incomplete context")
            mapped = {item["id"]: item["sha256"] for item in inputs}
            require(mapped.get(context["owner_id"]) == context["owner_sha256"], f"{ident}: missing owner")
            require(
                all(mapped.get(item["input_id"]) == item["input_sha256"] for item in context["instances"]),
                f"{ident}: missing instance input",
            )
            key = (ident, record["major"], context["owner_id"])
            require(key not in records, f"{ident}: duplicate owner proof")
            records[key] = record
    require({key[0] for key in records} == expected, "missing declared floor row artifacts")
    owners = {(key[0], key[2]) for key in records}
    for ident, owner in owners:
        require(
            (ident, 9, owner) in records and (ident, 10, owner) in records, f"{ident}: missing native bridge"
        )
        old, new = records[ident, 9, owner], records[ident, 10, owner]
        require(
            old["status"] == "original/refused" and old["upgrade_capability"] is False,
            f"{ident}: invalid native9 claim",
        )
        require(
            new["status"] == "upgraded/equal" and new["upgrade_capability"] is True,
            f"{ident}: upgraded probe incomplete",
        )
        require(
            old["inputs"] == new["inputs"] and old["context"] == new["context"], f"{ident}: context differs"
        )
        for field in SIGNATURE:
            require(
                field in old["original_native"]
                and old["original_native"][field]
                == new["original_native"].get(field)
                == new["upgraded_native"].get(field),
                f"{ident}: complete native bridge differs ({field})",
            )
        census = new["upgraded_census"]
        require(census["status"] == "equal", f"{ident}: incomplete upgraded census")
        for name in COMPARISONS:
            part = census.get(name, {})
            require(
                part.get("equal") is True
                and part.get("naming_equal") is True
                and part.get("name_differences")
                == part.get("native_only_pins")
                == part.get("drawn_unlisted_pins")
                == 0,
                f"{ident}: incomplete pin/partition/name proof ({name})",
            )
        upgrades = new["upgrades"]
        require(bool(upgrades), f"{ident}: no upgrade receipts")
        before = {item["relative"]: item for item in new["inputs"]}
        require(len({item["relative"] for item in upgrades}) == len(upgrades), f"{ident}: duplicate upgrades")
        expected_after = {item["id"]: item["sha256"] for item in new["inputs"]}
        for item in upgrades:
            source = before.get(item["relative"])
            require(
                source is not None
                and item["sha256_before"] == source["sha256"]
                and item["tool"] == "kicad-cli"
                and item["tool_version"] == new["native_version"]
                and item["from_version"] < 20231120 <= item["to_version"]
                and bool(re.fullmatch("[0-9a-f]{64}", item["sha256_after"])),
                f"{ident}: invalid upgrade provenance",
            )
            expected_after[source["id"]] = item["sha256_after"]
        require(
            {item["id"]: item["sha256"] for item in census["inputs"]} == expected_after,
            f"{ident}: upgraded output digest differs",
        )
    return len(owners)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("tests/corpus/manifest.toml"))
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    try:
        count = verify(args.reports, args.manifest, args.commit)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"drawn-floor bridge refused: {error}\n")
    print(f"drawn-floor: {count} complete same-commit native9/native10 owner bridges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
