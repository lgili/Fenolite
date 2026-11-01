# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generate native definitions and canonical records from cited parameters (c0265)."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any, cast

from fenolite.backends.step import write_bodies
from fenolite.catalog.devices import stamped
from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.record import FAMILY_KEYS, Keys, Package, package_from
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.catalog.records import (
    DeviceRecord,
    ImportOutput,
    ImportSource,
    PackageRecord,
    PartEntry,
    PinsRecord,
    ProposalAuthor,
    ProposalOrigin,
    Record,
    record_text,
)
from fenolite.core.errors import Issue
from fenolite.core.quantities import LengthRange, micro_units
from fenolite.library.importer.records import Imported, make_records
from fenolite.library.importer.sources import Selection, Source
from fenolite.library.proposals.agreement import agreement
from fenolite.library.proposals.checks import bind, expected_numbers, self_check
from fenolite.library.proposals.schema import RATING_UNITS, Proposal, proposal_text
from fenolite.library.rules import (
    PackageFacts,
    check_device_map,
    check_footprint,
    check_land_pattern,
    check_package,
    check_pin_groups,
    check_symbol,
    issue,
    manufacturer_land,
    row_name,
)
from fenolite.model.circuit import PinType
from fenolite.model.library import PinGroup, PinRow, PinShape, PinSide, PinTable, Rating

TOOL = "fenolite library propose"


def seal(record: Record) -> Record:
    origin = record.header.origin
    assert isinstance(origin, ProposalOrigin)
    blank = replace(
        record,
        header=replace(
            record.header, origin=replace(origin, content_sha256=""), evidence="UNVERIFIED", reviewed_by=()
        ),
    )
    checksum = hashlib.sha256(record_text(blank).encode()).hexdigest()
    return replace(record, header=replace(record.header, origin=replace(origin, content_sha256=checksum)))


def package_of(proposal: Proposal, licence: str = "see source terms") -> tuple[Package, dict[str, str]]:
    raw = proposal.data["package"]
    data = {key: value for key, value in raw.items() if key in FAMILY_KEYS[proposal.family]}
    names: dict[str, str] = {}
    if proposal.family == "grid":
        names = {
            f"{row_name(i)}{c + 1}": f"{label}{c + 1}"
            for i, label in enumerate(raw["row_labels"])
            for c in range(raw["columns"])
        }
        inverse = {v: k for k, v in names.items()}
        if isinstance(data.get("depopulated"), list):
            data["depopulated"] = [inverse[number] for number in data["depopulated"]]
    if "land" in raw:
        land = {k: v for k, v in raw["land"].items() if k != "cite"}
        cite = raw["land"].get("cite", {})
        land["source"] = f"{proposal.data['datasheet']['file']} page {cite.get('page', 'uncited')}"
        data["land"] = land
    ident = proposal.data["device"]["id"]
    data.update(
        schema="fenolite.package.v0",
        id=ident,
        family=proposal.family,
        summary=proposal.data["device"].get("summary", ident),
        evidence="UNVERIFIED",
        licence=licence,
        version="0.1.0",
        generate={"lands": 1, "drawing": 1},
    )
    return package_from(data, file=proposal.file), names


def _facts(package: Package) -> PackageFacts:
    ranges: dict[str, LengthRange] = {}

    def walk(keys: Keys, prefix: str = "") -> None:
        for key, value in keys.values.items():
            path = prefix + "." + key if prefix else key
            if isinstance(value, LengthRange):
                ranges[path] = value
            elif isinstance(value, Keys):
                walk(value, path)

    walk(package.keys)
    removed = package.keys.raw("depopulated")
    rows, columns = package.keys.count("rows") or 0, package.keys.count("columns") or 0
    exclusions: tuple[str, ...] = ()
    if isinstance(removed, tuple) and removed:
        if isinstance(removed[0], str):
            exclusions = cast(tuple[str, ...], removed)
        else:
            r, c = cast(tuple[int, int], removed)
            exclusions = tuple(
                f"{row_name(i)}{j + 1}"
                for i in range((rows - r) // 2, (rows + r) // 2)
                for j in range((columns - c) // 2, (columns + c) // 2)
            )
    return PackageFacts(
        package.family,
        ranges,
        pins=rows * columns - len(exclusions) if package.family == "grid" else None,
        rows=rows,
        columns=columns,
        depopulated=exclusions,
    )


def convert(
    proposals: list[Proposal],
    datasheet: bytes,
    *,
    date: str = "1970-01-01",
    licence: str = "see source terms",
    source_digests: list[tuple[str, str]] | None = None,
    target: int = 10,
) -> Imported:
    found = [f for proposal in proposals for f in (*bind(proposal, datasheet), *self_check(proposal))]
    found += agreement(proposals)
    if any(f.severity == "error" for f in found):
        raise ValueError("convert requires proposals whose binding and self-checks passed")
    proposal = proposals[0]
    package, names = package_of(proposal, licence)
    generated = generate(package)
    found += generated.issues
    fp = generated.footprint
    if fp is None:
        # Preserve generator findings without creating any file.
        raise GenerationRefused(tuple(found))
    found += check_package(_facts(package), fp, record_id=proposal.data["device"]["id"])
    if package.land:
        found += check_land_pattern(
            fp, manufacturer_land(package, fp), generated=True, record_id=proposal.data["device"]["id"]
        )
        delta = max((abs(v) for v in generated.land.deltas.values()), default=0)
        found.append(
            issue(
                "library.land-calculator-delta",
                f"largest pattern/calculator difference {delta} nm",
                proposal.data["device"]["id"],
                "land",
            )
        )
    if names:
        fp = replace(fp, pads=tuple(replace(p, number=names.get(p.number, p.number)) for p in fp.pads))
    ident = proposal.data["device"]["id"]
    namespace, name = ident.split(":", 1)
    rows = tuple(
        PinRow(
            str(row["number"]),
            str(row["name"]),
            cast(PinType, row["type"]),
            group=cast(PinGroup, row.get("group", "")),
            side=cast(PinSide, row.get("side", "")),
            bus=str(row.get("bus", "")),
            unit=row.get("unit"),
            shape=cast(PinShape, row.get("shape", "line")),
            hidden=bool(row.get("hidden", False)),
            stacked=tuple(row.get("stacked", [])),
        )
        for row in proposal.pins
    )
    table = PinTable(
        name,
        rows,
        namespace,
        version="0.1.0",
        summary=proposal.data["device"].get("summary", name),
        licence=licence,
        evidence="UNVERIFIED",
        reference=proposal.data["device"].get("ref_prefix", "U"),
    )
    found += check_pin_groups(((r.number, r.group, r.etype) for r in table.rows), record_id=ident)
    symbol, _, symbol_issues = generate_symbol(table, library=namespace)
    found += symbol_issues
    sources = source_digests or [
        (
            p.file.rsplit("/", 1)[-1] or f"proposal-{i + 1}.toml",
            hashlib.sha256(proposal_text(p).encode()).hexdigest(),
        )
        for i, p in enumerate(proposals)
    ]
    steps = ()
    if fp.bodies:
        data = write_bodies(name, fp.bodies)
        steps = (Source(name + ".step", "", "step", hashlib.sha256(data).hexdigest(), data),)
    selection = Selection(
        symbol, fp, (), steps, tuple(Source(file, "", "proposal", sha) for file, sha in sources), (), ()
    )
    imported = make_records(
        selection,
        device_id=ident,
        date=date,
        target=target,
        family=proposal.family,
        nominal={
            "pins": (len(expected_numbers(proposal)),),
            **{
                ("span.width" if key == "package.span" else key.removeprefix("package.")): (
                    value.min,
                    value.max,
                )
                if value.min != value.max
                else (value.min,)
                for key, value in proposal.quantities.items()
                if value.min is not None
                and value.max is not None
                and key.startswith(("package.body.", "package.lead.", "package.span", "package.pitch"))
            },
        },
        manufacturer=proposal.data["device"].get("manufacturer", ""),
        mpn=proposal.data["device"].get("mpn", ""),
        ref_prefix=table.reference,
    )
    found += [f for f in imported.issues if not f.code.startswith("library.import-")]
    found += check_footprint(
        imported.footprint,
        record_id=ident,
        pins=len(expected_numbers(proposal)),
        polarized=package.keys.text("polarity") == "pad1",
    )
    found += check_symbol(imported.symbol, record_id=ident)
    found += check_device_map(imported.device.device, imported.symbol, imported.footprint)
    origin = ProposalOrigin(
        TOOL,
        date,
        proposal.data["datasheet"]["file"],
        hashlib.sha256(datasheet).hexdigest(),
        tuple(ImportSource(file, "", sha) for file, sha in sources),
        tuple(
            ProposalAuthor(p.data["proposer"]["kind"], p.data["proposer"]["name"], p.data["proposer"]["date"])
            for p in proposals
        ),
    )
    files = {name: data for name, data in imported.files.items() if not name.endswith(".toml")}
    for index, p in enumerate(proposals):
        files["proposal.toml" if index == 0 else "proposal-2.toml"] = proposal_text(p).encode()
    outputs = tuple(
        ImportOutput(name, hashlib.sha256(data).hexdigest()) for name, data in sorted(files.items())
    )
    result_records: list[Record] = []
    for record in imported.records:
        record = replace(
            record,
            header=replace(
                record.header,
                origin=replace(origin, output=outputs if isinstance(record, DeviceRecord) else ()),
                licence=licence,
                summary=proposal.data["device"].get("summary", name),
            ),
        )
        if isinstance(record, PinsRecord):
            groups = {number: row.group for row in table.rows for number in (row.number, *row.stacked)}
            record = replace(record, pins=tuple(replace(p, group=groups[p.number]) for p in record.pins))
        elif isinstance(record, PackageRecord):
            record = replace(record, derived="generated from cited parameter proposal")
        if isinstance(record, DeviceRecord):
            ratings: list[Rating] = []
            properties = dict(record.device.properties)
            for key, row in proposal.data.get("ratings", {}).items():
                model_key = "voltage" if key == "vin" else key
                if model_key == "vout":
                    properties["proposal.rating.vout"] = str({k: v for k, v in row.items() if k != "cite"})
                    continue
                unit = {"voltage": "uV", "current": "uA", "power": "uW", "temperature": "mK"}[model_key]
                ratings.append(
                    Rating(
                        model_key,
                        cast(Any, unit),
                        *(
                            micro_units(RATING_UNITS[key], row[b]) if b in row else None
                            for b in ("min", "max")
                        ),
                        limit=row.get("limit", "abs_max"),
                    )
                )
            device = stamped(
                replace(
                    record.device,
                    summary=record.header.summary,
                    ratings=tuple(ratings),
                    properties=properties,
                    provenance=None,
                ),
                tool=TOOL,
                source=origin.datasheet,
                date=date,
            )
            parts = tuple(
                PartEntry(row["mpn"], **{k: v for k, v in row.items() if k not in {"mpn", "cite"}})
                for row in proposal.data.get("part", [])
            )
            record = replace(record, device=device, parts=parts)
        record = seal(record)
        result_records.append(record)
        from fenolite.catalog.records import kind_of, parse_record

        text = record_text(record)
        parse_record(text)
        files[{"device": "device", "package": "package", "pins": "pins"}[kind_of(record)] + ".toml"] = (
            text.encode()
        )
    device_record = next(r for r in result_records if isinstance(r, DeviceRecord))
    return Imported(
        device_record, tuple(result_records), files, imported.symbol, imported.footprint, tuple(found)
    )


class GenerationRefused(ValueError):
    def __init__(self, issues: tuple[Issue, ...]):
        self.issues = issues
        super().__init__("generator refused the proposed parameters")
