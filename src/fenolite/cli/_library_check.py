# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Record/library traversal and adapters for ``library check`` and human review (c0262)."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import html
import json
import os
import re
import tomllib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, cast

from fenolite import __version__
from fenolite.backends import registry
from fenolite.catalog import records
from fenolite.catalog.devices import check_device
from fenolite.catalog.footprints import Generated, generate, positions_of
from fenolite.catalog.footprints.record import Keys, Package, package_from
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.catalog.pins import read_pins
from fenolite.cli.api import Context, PlannedWrite, Result, contract_schema, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level, parse_level, strength
from fenolite.core.quantities import LengthRange
from fenolite.core.schema_ids import accepts_schema
from fenolite.geometry.errors import GeometryError
from fenolite.library import items as library_items
from fenolite.library import review, rules
from fenolite.library.device_items import source_ids
from fenolite.model import canonical
from fenolite.model.library import FootprintDef, Library, PinTable, SymbolDef

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-RULES", "H-G-LIBRARY-REVIEW"))
LIB_SUFFIXES = frozenset({".kicad_sym", ".kicad_mod", ".schlib", ".pcblib"})


def capability_entries() -> list[dict[str, object]]:
    return [
        {
            "name": f"library {action}",
            "mutates": True,
            "schema": contract_schema("library"),
            "hidden": False,
            "usage": usage,
        }
        for action, usage in (
            (
                "check",
                "fenolite library check TARGET... [--sheets DIR] [--compare OLD] [--fail-on error|warning]",
            ),
            ("review", "fenolite library review TARGET... [--accept --reviewer NAME --sheet HEX | --revoke]"),
            (
                "propose",
                "fenolite library propose --datasheet FILE [--proposal FILE] [--out DIR] [--licence SPDX]",
            ),
        )
    ]


def register(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("library checks and human review")
    group.add_argument(
        "--sheets", metavar="DIR", help="check: plan deterministic standalone HTML review sheets"
    )
    group.add_argument(
        "--compare", metavar="OLD", help="check: compare records with this old tree or library"
    )
    group.add_argument(
        "--fail-on",
        choices=("error", "warning"),
        default="error",
        help="check: lowest finding severity that exits 5",
    )
    group.add_argument(
        "--rules", metavar="CODES", help="check: run only these comma-separated library rule codes"
    )
    group.add_argument("--skip", metavar="CODES", help="check: omit these comma-separated library rule codes")
    choice = group.add_mutually_exclusive_group()
    choice.add_argument("--accept", action="store_true", help="review: human acceptance of the current sheet")
    choice.add_argument(
        "--revoke", action="store_true", help="review: remove acceptance and restore previous evidence"
    )
    group.add_argument(
        "--reviewer", metavar="NAME", help="review --accept: person who opened and checked the sheet"
    )
    group.add_argument(
        "--sheet", metavar="HEX", help="review --accept: at least 12 hex digits of the current sheet SHA-256"
    )


@dataclass
class Item:
    id: str
    kind: str
    path: Path
    file: str
    raw: dict[str, Any] = field(default_factory=lambda: {})
    record: records.Record | None = None
    header: records.Header | None = None
    package: Package | None = None
    table: PinTable | None = None
    generated: Generated | None = None
    symbol: SymbolDef | None = None
    footprint: FootprintDef | None = None
    findings: list[Issue] = field(default_factory=lambda: [])
    rules_run: set[str] = field(default_factory=lambda: set())
    used_waivers: set[str] = field(default_factory=lambda: set())
    dependencies: list[Item] = field(default_factory=lambda: [])
    digest: str = ""
    sheet_bytes: bytes = b""
    sheet_sha256: str = ""
    stale: bool = False
    effective: str = "UNVERIFIED"
    extra_files: list[Path] = field(default_factory=lambda: [])

    @property
    def evidence(self) -> str:
        return self.header.evidence if self.header else "UNVERIFIED"

    @property
    def latest(self) -> records.Review | None:
        return self.header.reviewed_by[-1] if self.header and self.header.reviewed_by else None

    def add(self, findings: list[Issue], codes: tuple[str, ...]) -> None:
        self.findings.extend(findings)
        self.rules_run.update(codes)


def _relative(path: Path, cwd: Path) -> str:
    try:
        return Path(os.path.relpath(path, cwd)).as_posix()
    except ValueError:  # another Windows drive, as in cmd_library._relative
        return path.as_posix()


def _files(targets: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for target in targets:
        if not target.exists():
            raise CliError("FEN-3001", f"library target {target.name} does not exist", where=target.name)
        if target.is_file():
            found.add(target)
        else:
            found.update(
                path
                for path in target.rglob("*")
                if path.is_file()
                and (path.suffix.lower() in LIB_SUFFIXES or path.suffix == ".toml")
                and not any(
                    part in {".git", ".venv", "__pycache__"} for part in path.relative_to(target).parts
                )
            )
    return sorted(found, key=lambda p: p.as_posix())


def _read(path: Path, cwd: Path) -> list[Item]:
    file = _relative(path, cwd)
    if path.suffix.lower() in LIB_SUFFIXES:
        backend = registry.for_path(path)
        if backend is None:
            raise FormatError("no backend reads this library", file=file)
        content = backend.read(path).content
        if not isinstance(content, Library):
            raise FormatError("not a library", file=file)
        return [
            *(Item(fp.lib_id, "footprint", path, file, footprint=fp) for fp in content.footprints),
            *(Item(symbol.lib_id, "symbol", path, file, symbol=symbol) for symbol in content.symbols),
        ]
    text = path.read_text(encoding="utf-8")
    raw: dict[str, Any] = tomllib.loads(text)
    if (
        path.name.lower() in {"sources.toml", "versions.toml", "licences.toml", "library.toml", "item.toml"}
        and raw.get("schema") not in records.SCHEMAS
    ):
        return []
    schema = raw.get("schema", "")
    if isinstance(schema, str) and schema.startswith("fenolite.proposal."):
        from fenolite.library.proposals.schema import parse_proposal

        parse_proposal(text, file=file)
        return []
    family = raw.get("family") or (raw.get("generator") if raw.get("generator") != "explicit" else None)
    if accepts_schema(schema, "fenolite.package.v0") and family and raw.get("generator") != "explicit":
        package = package_from(raw, file=file)
        count = (positions_of(package) or (None,))[0]
        generated = generate(package, positions=count)
        ident = f"{package.namespace or 'Local'}:{generated.name}"
        envelope = {
            "id": ident,
            "version": "0.0.0",
            "licence": "CC0-1.0",
            "summary": package.summary or generated.name,
            **raw,
        }
        header = records.parse_header(envelope, "package", file=file)
        item = Item(
            header.id,
            "package",
            path,
            file,
            raw,
            header=header,
            package=package,
            generated=generated,
            footprint=generated.footprint,
        )
        # Family generators already refuse impossible geometry. Keep this a library finding.
        for found in generated.issues:
            if found.severity == "error":
                item.findings.append(
                    rules.issue(
                        "library.record-invalid", f"{found.code}: {found.message}", item.id, found.where
                    )
                )
        return [item]
    drawing = raw.get("symbol", {})
    if accepts_schema(schema, "fenolite.pins.v0") and (
        not isinstance(drawing, dict) or "pins" not in drawing
    ):
        table = read_pins(path)
        symbol, _derived, findings = generate_symbol(table, library=table.namespace or "Local")
        header = records.parse_header(raw, "pins", file=file)
        item = Item(header.id, "pins", path, file, raw, header=header, table=table, symbol=symbol)
        item.findings += [
            rules.issue("library.record-invalid", f"{f.code}: {f.message}", item.id)
            for f in findings
            if f.severity == "error"
        ]
        return [item]
    record = records.parse_record(text, file=file, allow_stale_reviews=True)
    item = Item(
        record.header.id, records.kind_of(record), path, file, raw, record=record, header=record.header
    )
    if isinstance(record, records.PinsRecord):
        item.symbol = records.symbol_def(record)
        external = getattr(record, "symbol_file", "")
    elif isinstance(record, records.PackageRecord):
        item.footprint = records.footprint_def(record)
        external = getattr(record, "footprint", "")
    else:
        external = ""
    if isinstance(external, str) and external:
        source = path.parent / external
        backend = registry.for_path(source)
        if backend is None:
            raise FormatError("no backend reads the referenced definition", file=file)
        native = backend.read(source).content
        if not isinstance(native, Library):
            raise FormatError("referenced definition is not a library", file=file)
        if item.kind == "pins":
            item.symbol = next((s for s in native.symbols if s.name == record.header.name), None)
        else:
            fallback = item.footprint
            item.footprint = next((fp for fp in native.footprints if fp.name == record.header.name), None)
            if item.footprint is not None and fallback is not None and fallback.bodies:
                item.footprint = replace(item.footprint, bodies=fallback.bodies)
        if item.symbol is None and item.footprint is None:
            raise FormatError("referenced library has no matching definition", file=file)
        item.extra_files.append(source)
    return [item]


def _register(path: Path) -> tuple[set[str] | None, Path | None]:
    for parent in (path.parent, *path.parents):
        candidate = parent / "sources.toml"
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8")
            try:
                schema = tomllib.loads(text).get("schema")
            except ValueError as error:
                raise FormatError(f"sources.toml: {error}", file=str(candidate)) from None
            if accepts_schema(schema, "fenolite.library-sources.v0"):
                return set(source_ids(parent)), candidate
            # Retain the earlier S-id register form for project records.
            return set(re.findall(r"\bS-\d{4,}\b", text)), candidate
        candidate = parent / "docs" / "evidence" / "sources.md"
        if candidate.is_file():
            return set(
                re.findall(r"^\| (S-\d{4,}) \|", candidate.read_text(encoding="utf-8"), re.MULTILINE)
            ), candidate
    return None, None


def _package_facts(package: Package) -> rules.PackageFacts:
    ranges: dict[str, LengthRange] = {}

    def visit(keys: Keys, prefix: str = "") -> None:
        for name, value in keys.values.items():
            key = f"{prefix}.{name}" if prefix else name
            if isinstance(value, LengthRange):
                ranges[key] = value
            elif isinstance(value, Keys):
                visit(value, key)

    visit(package.keys)
    rows, columns = package.keys.count("rows") or 0, package.keys.count("columns") or 0
    depopulated = package.keys.raw("depopulated")
    removed: tuple[str, ...] = ()
    if isinstance(depopulated, tuple) and depopulated:
        if isinstance(depopulated[0], str):
            removed = cast(tuple[str, ...], depopulated)
        else:
            r, c = cast(tuple[int, int], depopulated)
            removed = tuple(
                f"{rules.row_name(i)}{j + 1}"
                for i in range((rows - r) // 2, (rows + r) // 2)
                for j in range((columns - c) // 2, (columns + c) // 2)
            )
    pins = package.keys.count("pins")
    if package.family == "grid" and pins is None:
        pins = rows * columns - len(removed)
    if package.family in {"chip", "molded"}:
        pins = 2
    if package.family == "to":
        pins = package.keys.count("leads")
        tab = package.keys.table("tab")
        if tab and tab.text("number") and tab.text("number") not in {str(i + 1) for i in range(pins or 0)}:
            pins = (pins or 0) + 1
    if package.family == "header":
        pins = rows * columns
    if package.family == "nolead" and package.keys.table("ep"):
        pins = (pins or 0) + 1
    return rules.PackageFacts(package.family, ranges, pins, rows, columns, removed)


def _resolve(items: list[Item], support: list[Item]) -> None:
    lookup = {(i.kind, i.id): i for i in [*support, *items]}
    shipped = records.shipped_tree()
    for item in items:
        if not isinstance(item.record, records.DeviceRecord):
            continue
        device = item.record.device
        pins, package = lookup.get(("pins", device.symbol)), lookup.get(("package", device.footprint))
        for kind, ident, present in (("pins", device.symbol, pins), ("package", device.footprint, package)):
            if present is not None:
                item.dependencies.append(present)
                continue
            record = shipped.get(cast(records.Kind, kind), ident)
            if record is not None:
                relative = shipped.files[(cast(records.Kind, kind), ident)].removeprefix(
                    "fenolite/catalog/data/"
                )
                source = Path(records.__file__).with_name("data") / relative
                present = Item(ident, kind, source, "builtin", record=record, header=record.header)
                if isinstance(record, records.PinsRecord):
                    present.symbol = records.symbol_def(record)
                    pins = present
                elif isinstance(record, records.PackageRecord):
                    present.footprint = records.footprint_def(record)
                    package = present
                item.dependencies.append(present)
        item.symbol, item.footprint = pins.symbol if pins else None, package.footprint if package else None
        if item.symbol is None or item.footprint is None:
            item.findings.append(
                rules.issue(
                    "library.record-invalid",
                    f"unresolved symbol {device.symbol} or footprint {device.footprint}",
                    item.id,
                )
            )
        else:
            item.add(
                rules.check_device_map(device, item.symbol, item.footprint, record_id=item.id),
                ("library.pad-count",),
            )
            for finding in check_device(device, item.symbol, item.footprint):
                if finding.severity == "error" and not any(
                    i.code == "library.pad-count" for i in item.findings
                ):
                    item.findings.append(
                        rules.issue("library.pad-count", finding.message, item.id, finding.where)
                    )


def _support_root(item: Item) -> Path:
    """Recognize an enclosing item tree without unbounded ancestor discovery."""
    local = item.path.parent
    if local.name in {"devices", "packages", "pins", "parts"}:
        return local.parent
    try:
        manifest = library_items.read_item(local.joinpath("item.json").read_bytes())
    except (library_items.ItemError, OSError):
        return local
    if manifest.kind != "device" or manifest.id != item.id or item.path.name not in manifest.files:
        return local
    for parent in tuple(local.parents)[:4]:
        if parent.name == "devices":
            return parent.parent
    return local


def load(targets: list[str], ctx: Context) -> tuple[list[Item], list[Path]]:
    paths = [Path(t) if Path(t).is_absolute() else ctx.cwd / t for t in targets]
    files = _files(paths)
    items: list[Item] = []
    for path in files:
        try:
            items.extend(_read(path, ctx.cwd))
        except (ValueError, FormatError, OSError, UnicodeError) as error:
            item = Item(_relative(path, ctx.cwd), "invalid", path, _relative(path, ctx.cwd))
            code = getattr(error, "cli_code", getattr(error, "code", "FEN-3004"))
            item.add(
                [rules.issue("library.record-invalid", f"{code}: {error}", item.id)],
                ("library.record-invalid",),
            )
            items.append(item)
    support: list[Item] = []
    for item in items:
        if isinstance(item.record, records.DeviceRecord):
            # A directly named device may refer to sibling pins and packages in the same tree.
            root = _support_root(item)
            for path in sorted(root.rglob("*.toml")):
                if path in files:
                    continue
                try:
                    support.extend(_read(path, ctx.cwd))
                    files.append(path)
                except (ValueError, FormatError, OSError, UnicodeError):
                    pass
    _resolve(items, support)
    linked = {p for item in (*items, *support) for p in item.extra_files}
    items = [item for item in items if item.header is not None or item.path not in linked]
    files.extend(linked)
    files.extend(dep.path for item in items for dep in item.dependencies)
    ids: set[tuple[str, str]] = set()
    for item in items:
        if (item.kind, item.id) in ids:
            item.findings.append(rules.issue("library.record-invalid", "duplicate stable id", item.id))
        ids.add((item.kind, item.id))
    return sorted(items, key=lambda i: (i.id, i.kind)), files


def _selected(args: argparse.Namespace) -> set[str]:
    def codes(value: str | None) -> set[str]:
        found: set[str] = {code.strip() for code in value.split(",")} if value else set()
        unknown = found - rules.RULES.keys()
        if unknown:
            raise CliError("FEN-2001", f"unknown library rules {sorted(unknown)}", where="--rules/--skip")
        return found

    return (codes(args.rules) if args.rules else set(rules.RULES)) - codes(args.skip)


def _base_checks(item: Item) -> None:
    header = item.header
    if header:
        register, _ = _register(item.path)
        sources = set(header.sources) | {s for ids in header.sources_by.values() for s in ids}
        if register is None and any(source.startswith("D-") for source in sources):
            register = set[str]()  # D ids require the external register; absence does not validate them.
        item.add(
            rules.check_envelope(
                header.evidence, sources, register, reviewed=bool(header.reviewed_by), record_id=item.id
            ),
            (
                "library.evidence-claim",
                "library.source-unknown" if register is not None else "library.sources-unchecked",
            ),
        )
    if item.footprint is not None and item.kind != "device":
        pins = _package_facts(item.package).pins if item.package else None
        if isinstance(item.record, records.PackageRecord):
            dimensions = item.record.dimensions
            pins = dimensions.get("pins", (None,))[0]
        polarized = bool(item.package and item.package.keys.text("polarity") == "pad1")
        item.add(
            rules.check_footprint(item.footprint, record_id=item.id, pins=pins, polarized=polarized),
            (
                "library.pad-count",
                "library.pin1-location",
                "library.pin1-marker",
                "library.courtyard-missing",
                "library.courtyard-containment",
                "library.pad-clearance",
            ),
        )
    if item.symbol is not None and item.kind != "device":
        stacked = (
            [number for p in item.table.rows for number in (p.number, *p.stacked) if p.stacked]
            if item.table
            else []
        )
        fp_name = item.record.device.footprint if isinstance(item.record, records.DeviceRecord) else None
        item.add(
            rules.check_symbol(item.symbol, record_id=item.id, stacked=stacked, footprint=fp_name),
            (
                "library.pin-grid",
                "library.hidden-power",
                "library.duplicate-pin",
                "library.footprint-filter-broad",
                *(("library.footprint-filter-miss",) if fp_name else ()),
            ),
        )
    if isinstance(item.record, records.DeviceRecord) and item.symbol is not None:
        found = rules.check_symbol(item.symbol, record_id=item.id, footprint=item.record.device.footprint)
        item.add(
            [f for f in found if f.code == "library.footprint-filter-miss"],
            ("library.footprint-filter-miss",),
        )
    rows = (
        [(p.number, p.group, p.type) for p in item.record.pins]
        if isinstance(item.record, records.PinsRecord)
        else ([(p.number, p.group, p.etype) for p in item.table.rows] if item.table else [])
    )
    if rows:
        item.add(rules.check_pin_groups(rows, record_id=item.id), ("library.pin-group-type",))
    if item.package:
        item.add(
            rules.check_package(_package_facts(item.package), item.footprint, record_id=item.id),
            ("library.body-span", *(("library.depopulated",) if item.package.family == "grid" else ())),
        )
        if item.package.land and item.generated:
            if item.footprint is not None:
                reference = rules.manufacturer_land(item.package, item.footprint)
                item.findings += rules.check_land_pattern(
                    item.footprint, reference, generated=True, record_id=item.id
                )
            delta = max((abs(v) for v in item.generated.land.deltas.values()), default=0)
            item.add(
                [
                    rules.issue(
                        "library.land-calculator-delta",
                        f"largest pattern/calculator difference {delta} nm",
                        item.id,
                        "land",
                    )
                ],
                ("library.land-mismatch", "library.land-calculator-delta"),
            )


def _stable_footprint(item: Item) -> FootprintDef | None:
    """Fix only generator-owned evidence metadata; every authored string remains in the digest."""
    if item.footprint is None:
        return None
    if item.package is not None:
        fixed = generate(replace(item.package, evidence="INFERRED")).footprint
        return replace(item.footprint, description=fixed.description) if fixed else item.footprint
    if isinstance(item.record, records.PackageRecord) and not getattr(item.record, "footprint", ""):
        record = replace(item.record, header=replace(item.record.header, evidence="INFERRED"))
        return replace(item.footprint, description=records.footprint_def(record).description)
    return item.footprint


def _stable_symbol(item: Item) -> SymbolDef | None:
    if item.symbol is not None and item.table is not None:
        fixed, _, _ = generate_symbol(replace(item.table, evidence="INFERRED"), library=item.symbol.library)
        return replace(item.symbol, properties=fixed.properties)
    return item.symbol


def _definitions(item: Item) -> list[object]:
    return [value for value in (_stable_symbol(item), _stable_footprint(item)) if value is not None]


def _digest(item: Item) -> str:
    dependencies = {f"{dep.kind}:{dep.id}": _digest(dep) for dep in item.dependencies}
    if item.header and isinstance(item.header.origin, records.ProposalOrigin):
        from fenolite.library.proposals.schema import parse_proposal

        for index in range(len(item.header.origin.proposer)):
            name = "proposal.toml" if index == 0 else "proposal-2.toml"
            path = item.path.parent / name
            try:
                data = path.read_bytes()
                parse_proposal(data.decode("utf-8"), file=name)
                dependencies[f"proposal:{name}"] = hashlib.sha256(data).hexdigest()
            except (OSError, FormatError, UnicodeError):
                dependencies[f"proposal:{name}"] = "missing-or-invalid"
        for name in sorted(item.path.parent.glob("*.step")):
            dependencies[f"model:{name.name}"] = hashlib.sha256(name.read_bytes()).hexdigest()
    return review.digest(
        item.record or item.raw,
        definitions=_definitions(item),
        dependencies=dependencies,
    )


def _findings(item: Item, *, stable: bool = False) -> list[dict[str, Any]]:
    return [
        {**dataclasses.asdict(f), "waived": f.code in item.used_waivers or f.hint.startswith("waived:")}
        for f in item.findings
        if not stable
        or f.code
        not in {
            "library.review-stale",
            "library.evidence-claim",
            "library.interface-changed",
            "library.removed",
        }
    ]


def _sheet(item: Item, old: Item | None = None) -> bytes:
    from fenolite.view.review_sheet import review_sheet

    metadata = {
        "Record and dimension sources": review.content_data(item.record or item.raw),
        "Pin table": review.content_data(item.table)
        if item.table
        else [{"number": p.number, "name": p.name, "type": p.etype, "unit": p.unit} for p in item.symbol.pins]
        if item.symbol
        else [],
        "Pin-to-pad map": canonical.to_data(item.record.device.pins)
        if isinstance(item.record, records.DeviceRecord)
        else [],
        "Referenced records": {
            f"{dep.kind}:{dep.id}": review.content_data(dep.raw or dep.record) for dep in item.dependencies
        },
    }
    if item.header and isinstance(item.header.origin, records.ProposalOrigin):
        from fenolite.library.proposals.schema import parse_proposal

        cited: list[dict[str, Any]] = []
        for index in range(len(item.header.origin.proposer)):
            name = "proposal.toml" if index == 0 else "proposal-2.toml"
            path = item.path.parent / name
            if path.is_file():
                cited.append(parse_proposal(path.read_text(), file=name).data)
        metadata["Cited proposals and open doubts"] = cited
    return review_sheet(
        item.id,
        metadata=metadata,
        findings=_findings(item, stable=True),
        symbol=_stable_symbol(item),
        footprint=_stable_footprint(item),
        old_symbol=_stable_symbol(old) if old else None,
        old_footprint=_stable_footprint(old) if old else None,
    )


def _paths(new: Any, old: Any, prefix: str = "") -> list[str]:
    if isinstance(new, dict) and isinstance(old, dict):
        new = cast(dict[str, Any], new)
        old = cast(dict[str, Any], old)
        return [
            path
            for key in sorted(set(new) | set(old))
            for path in _paths(new.get(key), old.get(key), f"{prefix}.{key}" if prefix else key)
        ]
    return [prefix] if new != old else []


def _interface(item: Item) -> object:
    if isinstance(item.record, records.DeviceRecord):
        return [(p.function, p.pin_pads) for p in item.record.device.pins]
    return {
        "pins": sorted(p.number for p in item.symbol.pins) if item.symbol else [],
        "pads": sorted(rules.electrical_pads(item.footprint)) if item.footprint else [],
    }


def compare(items: list[Item], old_items: list[Item]) -> list[dict[str, Any]]:
    new, old = {(i.kind, i.id): i for i in items}, {(i.kind, i.id): i for i in old_items}
    pairs: list[dict[str, Any]] = []
    for key in sorted(set(new) | set(old), key=lambda k: (k[1], k[0])):
        kind, ident = key
        a, b = new.get(key), old.get(key)
        change = (
            "added"
            if b is None
            else "removed"
            if a is None
            else "same"
            if a.digest == b.digest
            else "changed"
        )
        row: dict[str, Any] = {
            "id": ident,
            "kind": kind,
            "change": change,
            "fields": [],
            "symbol_changed": False,
            "footprint_changed": False,
        }
        if a and b:
            row.update(
                fields=_paths(review.content_data(a.raw), review.content_data(b.raw)),
                symbol_changed=review.content_data(_stable_symbol(a))
                != review.content_data(_stable_symbol(b)),
                footprint_changed=review.content_data(_stable_footprint(a))
                != review.content_data(_stable_footprint(b)),
            )
            if _interface(a) != _interface(b):
                a.add(
                    [
                        rules.issue(
                            "library.interface-changed",
                            "pin numbers, pad numbers or pin-to-pad map changed under the same id",
                            ident,
                            "interface",
                        )
                    ],
                    ("library.interface-changed",),
                )
        elif b and not (b.header and b.header.deprecated):
            removed = Item(ident, b.kind, b.path, b.file)
            removed.add(
                [rules.issue("library.removed", "non-deprecated id is absent from the new tree", ident)],
                ("library.removed",),
            )
            items.append(removed)
        pairs.append(row)
    return pairs


def inspect_items(items: list[Item], selected: set[str]) -> None:
    processed: set[int] = set()

    def visit(item: Item) -> None:
        if id(item) in processed:
            return
        processed.add(id(item))
        for dep in item.dependencies:
            visit(dep)
        try:
            _base_checks(item)
        except (ValueError, FormatError, GeometryError) as error:
            item.findings.append(rules.issue("library.record-invalid", f"FEN-3004: {error}", item.id))
        for dep in item.dependencies:
            item.findings.extend(replace(f, where=f"{item.id} -> {f.where}") for f in dep.findings)
        item.findings = [f for f in item.findings if f.code in selected]
        item.rules_run &= selected
        if item.header:
            item.findings, item.used_waivers = rules.apply_waivers(
                item.findings,
                {w.code: w.reason for w in item.header.waivers},
                record_id=item.id,
                selected=selected,
            )
        item.digest = _digest(item)
        try:
            item.sheet_bytes = _sheet(item)
            item.sheet_sha256 = review.sheet_digest(item.sheet_bytes)
        except (ValueError, FormatError, KeyError, GeometryError) as error:
            item.findings.append(rules.issue("library.render-failed", str(error), item.id))
        latest = item.latest
        if latest:
            item.stale = (
                review.is_stale(dataclasses.asdict(latest), item.digest, item.sheet_sha256)
                if latest.sheet_sha256
                else (bool(item.record and records.stale_reviews(item.record)))
            )
            if item.stale and "library.review-stale" in selected:
                item.findings.append(
                    rules.issue(
                        "library.review-stale",
                        "accepted record, dependencies or sheet bytes changed",
                        item.id,
                        "reviewed_by",
                    )
                )
            item.rules_run.add("library.review-stale")
        item.effective = rules.effective_evidence(
            item.evidence,
            (d.effective for d in item.dependencies),
            stale=item.stale,
            reviewed=latest is not None,
            previous_evidence=latest.previous_evidence or "UNVERIFIED" if latest else "UNVERIFIED",
        )

    for item in items:
        visit(item)


def rows(items: list[Item]) -> list[dict[str, Any]]:
    return [
        {
            "id": i.id,
            "kind": i.kind,
            "file": i.file,
            "evidence": i.evidence,
            "effective_evidence": i.effective,
            "rules_run": sorted(i.rules_run),
            "findings": _findings(i),
            "review": {
                "state": "stale" if i.stale else "accepted" if i.latest else "unreviewed",
                "latest": dataclasses.asdict(i.latest) if i.latest else None,
                "digest": i.digest,
            },
            "sheet": {"path": _sheet_path(i), "sha256": i.sheet_sha256},
        }
        for i in sorted(items, key=lambda i: (i.id, i.kind))
    ]


def _sheet_path(item: Item) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.+-]", "_", item.id)[:80]
    suffix = hashlib.sha256(item.id.encode("utf-8")).hexdigest()[:12]
    return f"{item.kind}/{stem}-{suffix}.html"


def check_command(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) < 2:
        raise CliError("FEN-2001", "library check needs TARGET...", where="check")
    if args.accept or args.revoke or args.reviewer or args.sheet:
        raise CliError("FEN-2001", "review flags belong to library review")
    selected = _selected(args)
    items, files = load(args.path[1:], ctx)
    inspect_items(items, selected)
    pairs: list[dict[str, Any]] = []
    if args.compare:
        old, old_files = load([args.compare], ctx)
        inspect_items(old, selected)
        pairs = compare(items, old)
        files += old_files
        for item in items:
            # Comparison findings participate in rule selection and record waivers too.
            waivers = {w.code: w.reason for w in item.header.waivers} if item.header else {}
            used = {
                f.code
                for f in item.findings
                if f.code in {"library.interface-changed", "library.removed"}
                and f.code in waivers
                and f.code in selected
            }
            item.used_waivers.update(used)
            item.findings = [
                replace(f, severity="info", hint=f"waived: {waivers[f.code]}") if f.code in used else f
                for f in item.findings
                if f.code in selected
                and not (
                    f.code == "library.waiver-unused"
                    and any(f.message == f"waiver {code} produced no finding" for code in used)
                )
            ]
            item.rules_run &= selected
            if any(p["id"] == item.id and p["kind"] == item.kind and p["change"] == "changed" for p in pairs):
                previous = next((i for i in old if i.id == item.id and i.kind == item.kind), None)
                item.sheet_bytes = _sheet(item, previous)
                # An old/new overlay is supplemental; review acceptance always binds the base sheet.
    shown = rows(items)
    writes: list[PlannedWrite] = []
    if args.sheets:
        out = Path(args.sheets)
        if out.is_absolute() or ".." in out.parts:
            raise CliError("FEN-2001", "--sheets must be a relative folder", where="--sheets")
        index_rows: list[str] = []
        manifest: list[dict[str, str]] = []
        for item, row in zip(sorted(items, key=lambda i: (i.id, i.kind)), shown, strict=True):
            path = row["sheet"]["path"]
            sha = review.sheet_digest(item.sheet_bytes)
            row["sheet"]["artifact_sha256"] = sha
            writes.append(PlannedWrite(f"{out.as_posix()}/{path}", item.sheet_bytes, "library-sheet"))
            manifest.append(
                {
                    "id": item.id,
                    "record_digest": item.digest,
                    "path": path,
                    "sha256": sha,
                    "review_sha256": item.sheet_sha256,
                }
            )
            index_rows.append(
                f'<tr><td><a href="{html.escape(path, quote=True)}">{html.escape(item.id)}</a></td>'
                f"<td>{html.escape(item.effective)}</td><td>{len(item.findings)}</td></tr>"
            )
        index = (
            '<!doctype html><html><head><meta charset="utf-8"><title>Library review</title></head>'
            "<body><h1>Library review</h1><table>" + "".join(index_rows) + "</table></body></html>\n"
        )
        writes += [
            PlannedWrite(f"{out.as_posix()}/index.html", index.encode(), "library-sheet"),
            PlannedWrite(
                f"{out.as_posix()}/sheets.json",
                (
                    json.dumps(
                        {"schema": "fenolite.library_sheets.v0", "items": manifest}, sort_keys=True, indent=2
                    )
                    + "\n"
                ).encode(),
                "library-sheets",
            ),
        ]
    for file in list(files):
        _, source_register = _register(file)
        if source_register:
            files.append(source_register)
    findings = tuple(f for i in items for f in i.findings if f.code in selected)
    summary = {
        "findings": dict(Counter(f.severity for f in findings)),
        "evidence": dict(Counter(i.effective for i in items)),
    }
    return Result(
        result={"items": shown, "compare": pairs, "summary": summary},
        issues=findings,
        evidence=EVIDENCE,
        writes=tuple(writes),
        depends=depends_on(ctx.cwd, *files),
    )


def _inline(value: Any) -> str:
    if isinstance(value, dict):
        value = cast(dict[str, Any], value)
        return (
            "{ " + ", ".join(f"{json.dumps(str(k))} = {_inline(v)}" for k, v in sorted(value.items())) + " }"
        )
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_inline(v) for v in cast(list[Any], value)) + "]"
    if isinstance(value, (str, bool, int)):
        return json.dumps(value, ensure_ascii=False)
    raise FormatError(f"cannot write TOML value {type(value).__name__}")


def _raw_text(raw: Mapping[str, Any]) -> str:
    lines = [
        f"# SPDX-License-Identifier: {raw.get('licence', 'CC0-1.0')}",
        "# Canonical library record written by Fenolite.",
    ]
    lines += [
        f"{json.dumps(key)} = {_inline(value)}" for key, value in sorted(raw.items()) if key != "reviewed_by"
    ]
    for entry in raw.get("reviewed_by", []):
        lines += [
            "",
            "[[reviewed_by]]",
            *(f"{key} = {_inline(value)}" for key, value in sorted(entry.items()) if value),
        ]
    return "\n".join(lines) + "\n"


def review_command(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) < 2:
        raise CliError("FEN-2001", "library review needs TARGET...", where="review")
    if not args.accept and (args.reviewer is not None or args.sheet is not None):
        raise CliError("FEN-2001", "--reviewer and --sheet require --accept")
    if args.sheets or args.compare or args.rules or args.skip:
        raise CliError("FEN-2001", "check flags belong to library check")
    if args.accept and (
        not args.reviewer
        or not args.reviewer.strip()
        or "@" in args.reviewer
        or not args.reviewer.isprintable()
    ):
        raise CliError(
            "FEN-2001", "--reviewer names a person and cannot be empty or an email", where="--reviewer"
        )
    items, files = load(args.path[1:], ctx)
    inspect_items(items, set(rules.RULES))
    if not args.accept and not args.revoke:
        return Result(result={"items": rows(items)}, evidence=EVIDENCE)
    if any(item.header is None for item in items) or not items:
        raise CliError(
            "FEN-2001", "review writes require parsed records, not plain libraries", where="review"
        )
    if args.accept:
        from fenolite.library.proposals.gate import review_gate

        supplied = getattr(args, "datasheet", None)
        datasheet = (
            Path(supplied)
            if supplied and Path(supplied).is_absolute()
            else ctx.cwd / supplied
            if supplied
            else None
        )
        if datasheet is not None:
            files.append(datasheet)
        gated: list[Issue] = []
        for item in items:
            if item.header and isinstance(item.header.origin, records.ProposalOrigin):
                gated.extend(
                    review_gate(
                        item.path.parent,
                        datasheet,
                        checked=not any(
                            f.severity == "error" and f.code != "library.review-stale" for f in item.findings
                        ),
                    )
                )
        if gated:
            return Result(result={"items": rows(items)}, issues=tuple(gated), evidence=EVIDENCE)
        for item in items:
            if not all(key in item.raw for key in ("id", "version", "licence")):
                raise CliError(
                    "FEN-2001", "acceptance needs a record with id, version and licence", where=item.id
                )
            if strength(parse_level(item.evidence)) > strength(Level.CORPUS_VERIFIED):
                raise CliError(
                    "FEN-7001", "review cannot lower evidence above CORPUS-VERIFIED", where=item.id
                )
        blocking = tuple(
            f
            for item in items
            for f in item.findings
            if f.severity == "error" and f.code != "library.review-stale"
        )
        if blocking:
            return Result(result={"items": rows(items)}, issues=blocking, evidence=EVIDENCE)
        for item in items:
            if not review.matches_sheet(args.sheet or "", item.sheet_sha256):
                raise CliError(
                    "FEN-4002", f"--sheet does not match the current sheet for {item.id}", where="--sheet"
                )
    writes: list[PlannedWrite] = []
    for item in items:
        assert item.header is not None
        header = item.header
        if args.revoke:
            if item.latest is None:
                continue
            header = replace(header, evidence=item.latest.previous_evidence or "UNVERIFIED", reviewed_by=())
        else:
            previous = (item.latest.previous_evidence or "UNVERIFIED") if item.latest else header.evidence
            entry = records.Review(
                str(args.reviewer).strip(),
                ctx.timestamp.date().isoformat(),
                header.version,
                item.digest,
                "CORPUS-VERIFIED",
                sheet_sha256=item.sheet_sha256,
                previous_evidence=previous,
                accepted_codes=tuple(sorted({f.code for f in item.findings if f.severity == "warning"})),
                fenolite_version=__version__,
            )
            header = replace(header, evidence=f"CORPUS-VERIFIED (review {entry.date})", reviewed_by=(entry,))
        if item.record is not None:
            record = replace(item.record, header=header)
            if not args.revoke:
                latest = replace(header.reviewed_by[-1], record_sha256=records.record_digest(record))
                record = replace(record, header=replace(header, reviewed_by=(latest,)))
                header = record.header
            text = records.record_text(record)
        else:
            raw = {**item.raw, "evidence": header.evidence}
            if header.reviewed_by:
                raw["reviewed_by"] = [dataclasses.asdict(r) for r in header.reviewed_by]
            else:
                raw.pop("reviewed_by", None)
            text = _raw_text(raw)
        writes.append(PlannedWrite(item.file, text.encode("utf-8"), "library-record"))
        item.header = header
        item.stale = False
        item.effective = rules.effective_evidence(
            header.evidence, (d.effective for d in item.dependencies), reviewed=bool(header.reviewed_by)
        )
    return Result(
        result={"items": rows(items), "action": "accept" if args.accept else "revoke"},
        evidence=EVIDENCE,
        writes=tuple(writes),
        depends=depends_on(ctx.cwd, *files),
    )
