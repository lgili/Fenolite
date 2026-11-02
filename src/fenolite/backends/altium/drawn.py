# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn sheets as native Altium records (c0276), with explicit loss and connectivity checks.

Record forms are those already recorded in docs/formats/altium/schematic-records.md. Choices of
colours and text placement reuse schdoc; application acceptance remains H-A-DRAWN-WRITE, INFERRED.
All coordinate arithmetic uses integer counts of 1/100000 of a ten-mil unit.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

import fenolite.backends.altium.schdoc as schdoc
from fenolite.backends.altium.altsym import NM_PER_MIL, STEPS, AltiumSymbol
from fenolite.backends.altium.ascii import Field, TextForm, format_record, text_problem
from fenolite.backends.altium.hierarchy import ProjectSheets, SheetFile
from fenolite.backends.altium.layout import SHEET_SIZES, PartSpec, PlacedPart, SheetPlan
from fenolite.backends.altium.project import unique_id
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.drawn import DrawnInstance, DrawnSchematic, DrawnSheet, DrawnSheetRef, DrawnSymbol
from fenolite.model.drawn_connect import UnitInfo, component_path, coverage, instances, issue

if TYPE_CHECKING:
    from fenolite.backends.altium.adapter.netlist import Resolved

Record = list[Field]
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DRAWN-WRITE",))
UNIT_SCALE = 100_000
# One native fractional unit is 127/50 nm (the existing schematic-records.md unit).
NM_NUMERATOR, NM_DENOMINATOR = 50, 127
_IO = {"input": "2", "output": "1", "bidirectional": "3", "tri_state": "3"}
_COORD = re.compile(r"(?:LOCATION|CORNER)\.X|X[0-9]+")


class DrawnLossError(FenoliteError):
    """A drawn point needs a rounding that the caller has not accepted."""

    cli_code = "FEN-7001"
    hint = "review the named point, then use --allow-lossy to accept its reported rounding"

    def __init__(self, finding: Issue) -> None:
        self.issues = (finding,)
        super().__init__(finding.message)


def _round(value: int, divisor: int) -> int:
    sign = -1 if value < 0 else 1
    return sign * ((abs(value) * 2 + divisor) // (2 * divisor))


def _fields(key: str, value: int) -> Record:
    sign = -1 if value < 0 else 1
    whole, fraction = divmod(abs(value), UNIT_SCALE)
    return [(key, str(sign * whole)), *([(f"{key}_FRAC", str(sign * fraction))] if fraction else [])]


def _value(record: Mapping[str, str], key: str) -> int:
    return int(record.get(key, "0")) * UNIT_SCALE + int(record.get(f"{key}_FRAC", "0"))


def _turn(x: int, y: int, rotation: int, mirror: str = "") -> tuple[int, int]:
    for _ in range(rotation % 4):
        x, y = -y, x
    if mirror == "x":
        y = -y
    elif mirror == "y":
        x = -x
    return x, y


class _Sheet:
    def __init__(self, plan: SheetPlan, issues: list[Issue], allow_lossy: bool, form: TextForm) -> None:
        self.plan = plan
        self.height = plan.size.height * 10_000
        self.issues = issues
        self.allow_lossy = allow_lossy
        self.form: TextForm = form
        self.records: list[Record] = []
        self.poses: list[PlacedPart] = []

    def point(self, at: Point, where: str) -> tuple[int, int]:
        values = (at.x * NM_NUMERATOR, at.y * NM_NUMERATOR)
        if any(value % NM_DENOMINATOR for value in values):
            finding = issue(
                "drawn.coordinate-rounded",
                f"drawn point ({at.x}, {at.y}) nm at {where} needs rounding to Altium's 127/50 nm step",
                where,
                DrawnLossError.hint,
            )
            if not self.allow_lossy:
                raise DrawnLossError(finding)
            self.issues.append(finding)
        return tuple(_round(value, NM_DENOMINATOR) for value in values)  # type: ignore[return-value]

    def location(self, at: Point, where: str, name: str = "LOCATION") -> Record:
        x, y = self.point(at, where)
        return [*_fields(f"{name}.X", x), *_fields(f"{name}.Y", self.height - y)]

    def add(self, record: Record, where: str = "") -> int:
        # Sheet record is inserted by schdoc, so the first explicit record has native index 1.
        for key, value in record:
            try:
                format_record([(key, "")])
            except ValueError as error:
                raise FormatError(str(error), locator=where or f"record[{len(self.records)}]") from None
            problem = text_problem(value, form=self.form) if value else None
            if problem is not None:
                raise FormatError(
                    f"Altium field {key}: {problem}", locator=where or f"record[{len(self.records)}]"
                )
        self.records.append(record)
        return len(self.records)

    def component(self, spec: PartSpec, symbol: DrawnSymbol, where: str) -> None:
        anchor_x, anchor_y = self.point(symbol.at, where)
        quarter = symbol.rotation // 90_000_000
        if symbol.mirror:
            self.issues.append(Issue("altium.not-lowered", "info", "the component mirror is carried by "
                                     "absolute child geometry; its native mirror metadata is unverified",
                                     where=where))  # fmt: skip
        origin = 1_000_000
        placed = PlacedPart(spec, origin, origin, (0, 0, 0, 0), symbol.unit)
        offset = len(self.records) + 1
        for original in schdoc.component_records(placed):
            record = dict(original)
            points: dict[str, Record] = {}
            for key in record:
                if not _COORD.fullmatch(key):
                    continue
                ykey = key.replace(".X", ".Y") if ".X" in key else "Y" + key[1:]
                x, y = _turn(
                    _value(record, key) - origin * 10_000,
                    _value(record, ykey) - origin * 10_000,
                    quarter,
                    symbol.mirror,
                )
                points[key] = [*_fields(key, anchor_x + x), *_fields(ykey, self.height - anchor_y + y)]
            coordinates = {k for values in points.values() for k, _ in values}
            coordinates |= {key for key in record if key.endswith("_FRAC") and key[:-5] in coordinates}
            output: Record = []
            consumed: set[str] = set()
            for key, value in original:
                if key in points:
                    output.extend(points[key])
                    consumed.update(k for k, _ in points[key])
                    continue
                if key in coordinates or key in consumed:
                    continue
                if key == "OWNERINDEX":
                    value = str(int(value) + offset)
                elif key == "PINCONGLOMERATE":
                    number = int(value)
                    dx, dy = _turn(*STEPS[number & 3], quarter, symbol.mirror)
                    direction = next(k for k, vector in STEPS.items() if vector == (dx, dy))
                    value = str((number & ~3) | direction)
                output.append((key, value))
            if record.get("RECORD") == "1":
                output.append(("ORIENTATION", str(quarter)))
            if record.get("RECORD") == "14":
                rectangle = dict(output)
                x0, x1 = sorted((_value(rectangle, "LOCATION.X"), _value(rectangle, "CORNER.X")))
                y0, y1 = sorted((_value(rectangle, "LOCATION.Y"), _value(rectangle, "CORNER.Y")))
                output = [(key, value) for key, value in output
                          if not key.startswith(("LOCATION.", "CORNER."))]  # fmt: skip
                output += [*_fields("LOCATION.X", x0), *_fields("LOCATION.Y", y0),
                           *_fields("CORNER.X", x1), *_fields("CORNER.Y", y1)]  # fmt: skip
            name = record.get("NAME", "")
            field_name = {"Designator": "Reference", "Comment": "Value"}.get(name, name)
            pose = next((p for p in symbol.fields if p.name == field_name), None)
            if pose is not None and record.get("RECORD") in {"34", "41"}:
                output = [
                    (k, v)
                    for k, v in output
                    if not k.startswith("LOCATION.")
                    and k not in {"ORIENTATION", "ISHIDDEN", "JUSTIFICATION", "ISMIRRORED"}
                ]
                output += self.location(pose.at, f"{where}.fields.{field_name}")
                output.append(("ORIENTATION", str(pose.rotation // 90_000_000)))
                words = pose.justify.split()
                if any(word != "mirror" for word in words):
                    self.issues.append(Issue("altium.not-lowered", "info", "source field justification "
                                             "is not represented by the native component parameter writer",
                                             where=f"{where}.fields.{field_name}"))  # fmt: skip
                if "mirror" in words:
                    output.append(("ISMIRRORED", "T"))
                if pose.hide:
                    output.append(("ISHIDDEN", "T"))
            self.add(output)
        self.poses.append(
            replace(placed, x=symbol.at.x // NM_PER_MIL, y=symbol.at.y // NM_PER_MIL, rotation=quarter)
        )

    def polyline(self, points: Sequence[Point], bus: bool, where: str) -> None:
        record: Record = [
            ("RECORD", "26" if bus else "27"),
            ("OWNERPARTID", "-1"),
            ("LINEWIDTH", schdoc.BUS_WIDTH if bus else "1"),
            ("COLOR", schdoc.TEXT_COLOR),
            ("LOCATIONCOUNT", str(len(points))),
        ]
        for index, point in enumerate(points, 1):
            x, y = self.point(point, f"{where}.pts[{index - 1}]")
            record += [*_fields(f"X{index}", x), *_fields(f"Y{index}", self.height - y)]
        self.add(record)

    def identifier(self, name: str, at: Point, rotation: int, kind: str, shape: str, where: str) -> None:
        x, y = self.point(at, where)
        location = [*_fields("LOCATION.X", x), *_fields("LOCATION.Y", self.height - y)]
        record: Record = [
            ("RECORD", {"local": "25", "hierarchical": "18", "global": "17"}[kind]),
            ("OWNERPARTID", "-1"),
            *location,
            ("COLOR", schdoc.TEXT_COLOR),
            ("FONTID", "1"),
        ]
        quarter = rotation // 90_000_000
        if kind == "local":
            record += [("TEXT", name), ("ORIENTATION", str(quarter))]
        elif kind == "global":
            record += [("TEXT", name), ("STYLE", "2"), ("ORIENTATION", str(quarter)), ("SHOWNETNAME", "T")]
        else:
            # A port's two hot ends stay on the label's axis; the drawn point is always one end.
            width = 100 * 10_000
            if quarter == 2:
                x -= width
            elif quarter == 3:
                y += width
            record = [(k, v) for k, v in record if not k.startswith("LOCATION.")]
            record += [
                *_fields("LOCATION.X", x),
                *_fields("LOCATION.Y", self.height - y),
                ("NAME", name),
                ("STYLE", "4" if quarter % 2 else "0"),
                *_fields("WIDTH", width),
                ("HEIGHT", "10"),
                ("IOTYPE", _IO.get(shape, "0")),
                ("UNIQUEID", unique_id(where)),
            ]
        self.add(record)

    def reference(self, ref: DrawnSheetRef, child_file: str, where: str) -> None:
        x, y = self.point(ref.at, where + ".at")
        width, height = self.point(Point(ref.size.w, ref.size.h), where + ".size")
        owner = self.add(
            [
                ("RECORD", "15"),
                ("OWNERPARTID", "-1"),
                *_fields("LOCATION.X", x),
                *_fields("LOCATION.Y", self.height - y),
                *_fields("XSIZE", width),
                *_fields("YSIZE", height),
                ("COLOR", schdoc.SYMBOL_COLOR),
                ("AREACOLOR", schdoc.SYMBOL_FILL),
                ("ISSOLID", "T"),
                ("SYMBOLTYPE", "Normal"),
                ("UNIQUEID", unique_id(where)),
            ]
        )
        for index, pin in enumerate(ref.pins):
            px, py = self.point(pin.at, f"{where}.pin[{index}]")
            if px == x:
                side, distance = 0, py - y
            elif px == x + width:
                side, distance = 1, py - y
            elif py == y:
                side, distance = 2, px - x
            elif py == y + height:
                side, distance = 3, px - x
            else:
                self.issues.append(
                    issue(
                        "drawn.sheet-pin-unmatched",
                        f"{pin.name} is not on its Altium sheet symbol edge",
                        where,
                    )
                )
                continue
            whole, fraction = divmod(distance, UNIT_SCALE * 10)
            self.add(
                [
                    ("RECORD", "16"),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    ("NAME", pin.name),
                    ("SIDE", str(side)),
                    ("DISTANCEFROMTOP", str(whole)),
                    *([("DISTANCEFROMTOP_FRAC1", str(fraction))] if fraction else []),
                    ("IOTYPE", _IO.get(pin.shape, "0")),
                    ("COLOR", schdoc.SYMBOL_COLOR),
                    ("AREACOLOR", schdoc.ENTRY_FILL),
                    ("TEXTCOLOR", schdoc.SYMBOL_COLOR),
                    ("TEXTFONTID", "1"),
                    ("TEXTSTYLE", "Full"),
                    ("ARROWKIND", schdoc.ENTRY_ARROW),
                ]
            )
        for record, text in (("32", ref.name), ("33", child_file)):
            self.add(
                [
                    ("RECORD", record),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    *_fields("LOCATION.X", x),
                    *_fields("LOCATION.Y", self.height - y),
                    ("TEXT", text),
                    ("FONTID", "1"),
                    ("COLOR", schdoc.TEXT_COLOR),
                ]
            )

    def drawing(
        self,
        sheet: DrawnSheet,
        instance: DrawnInstance,
        specs: Mapping[str, PartSpec],
        files: Mapping[str, str],
        symbol_overrides: Mapping[str, tuple[str, AltiumSymbol]],
    ) -> SheetPlan:
        where = instance.path or "root"
        if sheet.bus_aliases:
            self.issues.append(Issue("altium.not-lowered", "info", "bus alias declarations are not written "
                                     "as native alias metadata; the written pin partition remains guarded",
                                     where=where))  # fmt: skip
        if sheet.title_block:
            self.issues.append(
                Issue(
                    "altium.not-lowered",
                    "info",
                    "per-sheet source title metadata is not represented by the native drawn sheet writer",
                    where=where,
                )
            )
        for index, symbol in enumerate(sheet.symbols):
            spec = specs.get(instance.component(symbol.part))
            if spec is not None and 1 <= symbol.unit <= spec.body.parts:
                if symbol.symbol:
                    alias = symbol_overrides.get(symbol.symbol)
                    if alias is None:
                        raise FormatError(
                            f"unresolved Altium drawn unit alias {symbol.symbol}", locator=where
                        )
                    library, body = alias
                    spec = replace(spec, library=library, symbol=body.lib_ref, body=body)
                self.component(spec, symbol, f"{where}.symbol[{index}]")
        for kind, polylines in (("wire", sheet.wires), ("bus", sheet.buses)):
            for index, points in enumerate(polylines):
                self.polyline(points, kind == "bus", f"{where}.{kind}[{index}]")
        for index, junction in enumerate(sheet.junctions):
            self.add(
                [
                    ("RECORD", "29"),
                    ("OWNERPARTID", "-1"),
                    *self.location(junction.at, f"{where}.junction[{index}]"),
                    ("COLOR", schdoc.TEXT_COLOR),
                ]
            )
        for index, entry in enumerate(sheet.bus_entries):
            end = entry.end
            self.add(
                [
                    ("RECORD", "37"),
                    ("OWNERPARTID", "-1"),
                    *self.location(entry.at, f"{where}.bus_entry[{index}].at"),
                    *self.location(end, f"{where}.bus_entry[{index}].end", "CORNER"),
                    ("LINEWIDTH", "1"),
                    ("COLOR", schdoc.BUS_COLOR),
                ]
            )
        for index, at in enumerate(sheet.no_connects):
            self.add(
                [
                    ("RECORD", "22"),
                    ("OWNERPARTID", "-1"),
                    *self.location(at, f"{where}.no_connect[{index}]"),
                    ("COLOR", schdoc.NO_ERC_COLOR),
                    ("ISACTIVE", "T"),
                    ("SUPPRESSALL", "T"),
                    ("SYMBOL", schdoc.NO_ERC_SYMBOL),
                ]
            )
        for index, label in enumerate(sheet.labels):
            self.identifier(
                label.text, label.at, label.rotation, label.kind, label.shape, f"{where}.label[{index}]"
            )
        for index, power in enumerate(sheet.powers):
            self.identifier(power.net, power.at, power.rotation, "global", "", f"{where}.power[{index}]")
            if power.fields or power.mirror:
                self.issues.append(
                    Issue(
                        "altium.not-lowered",
                        "info",
                        "the native power port uses its own glyph and text placement; source field poses "
                        "and mirror metadata are not represented",
                        where=f"{where}.power[{index}]",
                    )
                )
        for ref in sheet.sheet_refs:
            child = "/".join((*instance.keys, ref.key))
            if child in files:
                self.reference(ref, files[child], f"{where}.sheet_ref.{ref.key}")
        for index, opaque in enumerate(sheet.opaques):
            if not opaque.altium:
                self.issues.append(
                    issue(
                        "drawn.opaque-dropped",
                        f"opaque item {index} of {sheet.key} has no Altium record text",
                        f"{where}.opaque[{index}]",
                    )
                )
                continue
            for line in opaque.altium.splitlines():
                fields: Record = []
                keys: set[str] = set()
                for item in line.strip().split("|"):
                    if not item:
                        continue
                    key, separator, value = item.partition("=")
                    if not separator or not key:
                        raise FormatError(
                            "opaque Altium text needs |KEY=value fields", locator=f"{where}.opaque[{index}]"
                        )
                    if key.upper() in keys:
                        raise FormatError(
                            f"opaque Altium record repeats field {key!r}",
                            locator=f"{where}.opaque[{index}]",
                        )
                    keys.add(key.upper())
                    fields.append((key, value))
                if dict(fields).get("RECORD") in {
                    None,
                    "0",
                    "1",
                    "2",
                    "15",
                    "16",
                    "17",
                    "18",
                    "22",
                    "25",
                    "26",
                    "27",
                    "29",
                    "31",
                    "32",
                    "33",
                    "34",
                    "37",
                    "41",
                } or any(
                    key.upper() in {"OWNERINDEX", "OWNERINDEXADDITIONALLIST", "OWNERINDEXADDITIONALRECORD"}
                    for key, _ in fields
                ):
                    raise FormatError(
                        "opaque Altium text must be a root graphic, without ownership, electrical or "
                        "framework-owned records",
                        locator=f"{where}.opaque[{index}]",
                    )
                self.add(fields, f"{where}.opaque[{index}]")
        return replace(
            self.plan,
            parts=tuple(self.poses),
            stubs=(),
            no_connects=(),
            symbols=(),
            ports=(),
            harnesses=(),
            lines=(),
            class_marks=(),
            buses=(),
            composition=None,
            drawn_records=tuple(tuple(record) for record in self.records),
        )


def lower_drawn(
    drawn: DrawnSchematic,
    design: Design,
    planned: ProjectSheets,
    *,
    name: str,
    issues: list[Issue],
    allow_lossy: bool = False,
    form: TextForm = "binary",
    symbol_overrides: Mapping[str, tuple[str, AltiumSymbol]] = MappingProxyType({}),
) -> ProjectSheets:
    """One native sheet per drawn instance, retaining generated module sheets and their records."""
    found, walk_issues = instances(drawn)
    issues.extend(walk_issues)
    specs = {part.spec.key: part.spec for sheet in planned.sheets for part in sheet.plan.parts}
    units = {
        key: UnitInfo(
            spec.body.parts,
            frozenset(
                part
                for part in range(1, spec.body.parts + 1)
                if any(pin.designator in spec.nets and pin.part in (0, part) for pin in spec.body.pins)
            ),
        )
        for key, spec in specs.items()
    }
    issues.extend(coverage(drawn, design.circuit, units))
    generated = {sheet.module or "": sheet for sheet in planned.sheets}
    files: dict[str, str] = {}
    for instance in found:
        sheet = drawn.sheet(instance.sheet)
        if sheet is not None and sheet.generated and instance.module in generated:
            files[instance.path] = generated[instance.module].file
        else:
            files[instance.path] = (
                f"{name}.SchDoc" if not instance.keys else f"{name}_drawn_{unique_id(instance.path)}.SchDoc"
            )
    counts = Counter(instance.sheet for instance in found)
    for key, count in sorted(counts.items()):
        if count > 1:
            issues.append(
                issue(
                    "drawn.altium-repeat-flattened",
                    f"sheet {key} is written as {count} Altium instances",
                    key,
                )
            )
    written: list[SheetFile] = []
    for instance in found:
        sheet = drawn.sheet(instance.sheet)
        if sheet is None:
            continue
        if sheet.generated:
            source = generated.get(instance.module)
            if source is None:
                issues.append(
                    issue(
                        "drawn.sheet-unknown",
                        f"no generated Altium module sheet for {instance.module}",
                        instance.module,
                    )
                )
            else:
                written.append(source)
                written.extend(
                    s for s in planned.sheets if s.module and s.module.startswith(instance.module + "/")
                )
            continue
        size = next((size for size in SHEET_SIZES if size.name == sheet.paper), None)
        if size is None:
            raise FormatError(f"Altium drawn sheet {sheet.key}: unsupported paper {sheet.paper!r}")
        base = SheetPlan(size, (), ())
        state = _Sheet(base, issues, allow_lossy, form)
        plan = state.drawing(sheet, instance, specs, files, symbol_overrides)
        written.append(
            SheetFile(
                files[instance.path],
                plan,
                instance.module or None,
                unique_id(instance.path) if instance.keys else None,
            )
        )
    written = _global_local_names(written, issues)
    return ProjectSheets("modules" if len(written) > 1 else "flat", tuple(written))


def _global_local_names(sheets: list[SheetFile], issues: list[Issue]) -> list[SheetFile]:
    """Preserve local partitions under source-verified Automatic/Global, without guessing another mode."""
    if len(sheets) <= 1:
        return sheets
    records = [[dict(record) for record in schdoc.schdoc_records(sheet.plan)] for sheet in sheets]
    if any(record.get("RECORD") == "16" for record in records[0]) or any(
        record.get("RECORD") == "18" for sheet in records for record in sheet
    ):
        return sheets  # Automatic selects Hierarchical or Flat; local names already have sheet scope.
    taken = {
        record.get("TEXT", record.get("NAME", "")).casefold()
        for sheet in records
        for record in sheet
        if record.get("RECORD") in {"17", "18", "25"}
    }
    occurrences: dict[str, set[int]] = {}
    for index, sheet_records in enumerate(records):
        for record in sheet_records:
            if record.get("RECORD") == "25":
                occurrences.setdefault(record.get("TEXT", ""), set()).add(index)
    shared = {name for name, holders in occurrences.items() if len(holders) > 1}
    result: list[SheetFile] = []
    for sheet in sheets:
        original = sheet.plan.drawn_records
        if original is None:
            result.append(sheet)
            continue
        names = sorted(
            {
                dict(record).get("TEXT", "")
                for record in original
                if dict(record).get("RECORD") == "25" and dict(record).get("TEXT", "") in shared
            }
        )
        prefix = f"__local_{unique_id(sheet.file)}_"
        while any((prefix + name).casefold() in taken for name in names):
            prefix += "_"
        replacements = {name: prefix + name for name in names}
        taken.update(value.casefold() for value in replacements.values())
        for name, replacement in replacements.items():
            issues.append(
                Issue(
                    "altium.not-lowered",
                    "info",
                    f"local label {name!r} is written as {replacement!r} to preserve its sheet scope when "
                    "Automatic selects Global; drawn label text is changed",
                    where=f"{sheet.file}:{name}",
                )
            )
        rewritten = tuple(
            tuple((key, replacements.get(value, value) if key == "TEXT" else value) for key, value in record)
            if dict(record).get("RECORD") == "25"
            else record
            for record in original
        )
        result.append(replace(sheet, plan=replace(sheet.plan, drawn_records=rewritten)))
    return result


@dataclass(frozen=True)
class NativeCoverage:
    """The intended native documents, unit pin tables and footprint maps; no persisted model field."""

    files: tuple[str, ...]
    units: tuple[tuple[str, int, tuple[str, ...]], ...]
    pad_maps: tuple[tuple[str, tuple[tuple[str, tuple[str, ...]], ...]], ...]


def planned_coverage(planned: ProjectSheets) -> NativeCoverage:
    """Coverage before the native producer runs, including units whose pins are all unconnected."""
    units: list[tuple[str, int, tuple[str, ...]]] = []
    maps: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {}
    for sheet in planned.sheets:
        for placed in sheet.plan.parts:
            spec = placed.spec
            pins = tuple(sorted(pin.designator for pin in spec.body.pins if pin.part in (0, placed.part)))
            units.append((spec.ref, placed.part, pins))
            maps[spec.ref] = tuple(sorted(spec.pin_pads))
    return NativeCoverage(tuple(sorted(s.file for s in planned.sheets)), tuple(sorted(units)),
                          tuple(sorted(maps.items())))  # fmt: skip


def _read_native(files: Mapping[str, bytes]) -> tuple[Resolved, NativeCoverage]:
    from fenolite.backends.altium.adapter.netlist import SheetInput, resolve
    from fenolite.backends.altium.read import sch

    sheets = [SheetInput(name, "", sch.read_schematic(data, file=name))
              for name, data in sorted(files.items()) if name.lower().endswith(".schdoc")]  # fmt: skip
    if not sheets or any(
        document.document.sheet is None
        or document.document.of_type(sch.UnknownRecord)
        or any(i.severity in {"warning", "error"} for i in document.document.issues)
        for document in sheets
    ):
        raise FormatError("the written Altium drawing has no verifiable native document set")
    diagnostics: list[Issue] = []
    resolved = resolve(sheets, issues=diagnostics)
    if any(i.severity in {"warning", "error"} for i in diagnostics):
        raise FormatError("the written Altium drawing has unresolved connectivity: "
                          + "; ".join(i.message for i in diagnostics))  # fmt: skip
    units: list[tuple[str, int, tuple[str, ...]]] = []
    maps: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {}
    for key in resolved.component_ids:
        instance, group = key
        sheet = resolved.sheets[resolved.instances[instance].sheet]
        parts = sheet.groups[group]
        ref = resolved.refs.get(key, "")
        if not ref:
            raise FormatError("the written Altium drawing has an unnamed component")
        for part in parts.parts:
            pins = tuple(sorted(pin.designator for pin in sheet.input.document.shown_children(part)
                                if isinstance(pin, sch.Pin)))  # fmt: skip
            units.append((ref, part.current_part, pins))
        maps[ref] = tuple(sorted(parts.pin_pads))
    coverage = NativeCoverage(tuple(sorted(sheet.file for sheet in sheets)), tuple(sorted(units)),
                              tuple(sorted(maps.items())))  # fmt: skip
    return resolved, coverage


def native_coverage(files: Mapping[str, bytes]) -> NativeCoverage:
    """The coverage of bytes already checked by the builder, for the CLI's final-write guard."""
    return _read_native(files)[1]


def readback_issues(
    files: Mapping[str, bytes], design: Design, *, expected: NativeCoverage
) -> tuple[Issue, ...]:
    """Check actual native coverage and logical pin partitions before returning any candidate bytes."""
    from fenolite.model.drawn_connect import DrawnNet, DrawnNetlist, compare

    def refused(message: str) -> tuple[Issue, ...]:
        return (Issue("build.schematic-netlist-differs", "error", message),)

    try:
        resolved, actual = _read_native(files)
    except (FenoliteError, ValueError, OSError) as error:
        return refused(f"the written Altium drawing cannot be verified: {error}")
    if actual != expected:
        return refused("the written Altium drawing changed its document, component/unit/pin coverage "
                       "or footprint pin map; nothing is written")  # fmt: skip
    by_ref = {component.ref: component_path(component) for component in design.circuit.components}
    if any(ref not in by_ref for ref, _unit, _pins in actual.units):
        return refused("the written Altium drawing contains a component outside the circuit")
    mapping = {native: by_ref[resolved.refs[key]] for key, native in resolved.component_ids.items()}
    nets = tuple(
        DrawnNet(net.name, tuple(sorted((mapping[p.component], p.designator) for p in net.pins)), net.aliases)
        for net in resolved.netlist.nets
    )
    pins = tuple(sorted({(by_ref[ref], pin) for ref, _unit, numbers in actual.units for pin in numbers}))
    # Altium's native electrical designators are logical pins. Its physical pin maps were sealed
    # separately above; compare logical native connections with the same logical circuit domain.
    circuit = replace(design.circuit, components=tuple(replace(c, pin_pad_map=())
                                                       for c in design.circuit.components))  # fmt: skip
    differences = compare(DrawnNetlist(nets, pins), circuit)
    return tuple(
        Issue("build.schematic-netlist-differs", "error", found.message, where=found.where, hint=found.hint)
        if found.severity == "error"
        else found
        for found in differences
    )


__all__ = [
    "EVIDENCE",
    "DrawnLossError",
    "NativeCoverage",
    "lower_drawn",
    "native_coverage",
    "planned_coverage",
    "readback_issues",
]
