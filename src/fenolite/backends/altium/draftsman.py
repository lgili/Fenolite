# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic candidate Draftsman shells (c0172), behind the native acceptance gate.

Only members already recorded in ``docs/formats/altium/draftsman.md`` are written. Format version 22
comes from the public corpus, not an observation of AD 26.5. Missing members deliberately keep their
data-contract defaults; whether Altium accepts those defaults is Part F's FP3, not an own-readback claim.
No board snapshot is written. The relative PCB-name binding is explicitly unconfirmed (FP4).

The Drill Table, Layer Stack Legend, Bill Of Materials, Note and Linear Dimension carry every member of
the round F0 rows (S-1421), in that order, with the values Altium saved there (c0388 task 4.1). They are
judged by unit tests against those rows only: no output reaches a user while ``NATIVE_WRITE`` is False,
and round FPC may still force their rework.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final, Literal, TypeAlias
from xml.sax.saxutils import escape, quoteattr

from fenolite.backends.altium.read.draftsman import (
    CHUNK_SIZE,
    INSTANCE,
    NAMESPACE,
    DraftsmanFile,
    DraftsmanSummary,
    summary,
)
from fenolite.core.evidence import Evidence, Level

NATIVE_WRITE: Final = False
DRAFTSMAN_KIND = "altium_draftsman"
EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-DWF-CONTAINER",
        "H-A-DWF-FIELD",
        "H-A-DWF-GEOM",
        "H-A-DWF-IMPORT",
        "H-A-DWF-KIT",
        "H-A-DWF-MINIMAL",
        "H-A-DWF-PARAMS",
        "H-A-DWF-READBACK",
        "H-A-DWF-TEMPLATE",
    ),
)
Kind = Literal[
    "Text",
    "Note",
    "BoardAssemblyViewData",
    "DrillViewView",
    "LayerStackLegendView",
    "DrillTableBoardView",
    "BillOfMaterialsView",
    "LinearDimension",
]
KINDS = frozenset(
    (
        "Text",
        "Note",
        "BoardAssemblyViewData",
        "DrillViewView",
        "LayerStackLegendView",
        "DrillTableBoardView",
        "BillOfMaterialsView",
        "LinearDimension",
    )
)
_NS = f"{{{NAMESPACE}}}"
# Round F0 (S-1421): `BoardSourceName` declares its own default namespace and dictionaries declare `a`.
BOARD = (
    "http://schemas.datacontract.org/2004/07/"
    "Altium.Designer.PcbDrawing.Implementation.Data.Serialization.V1.Document.Page.Item.Board"
)
ARRAYS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"
_A = f"{{{ARRAYS}}}"
_TYPE = f"{{{INSTANCE}}}type"
_NIL = f"{{{INSTANCE}}}nil"
Fill: TypeAlias = Callable[[ET.Element], None]
Value: TypeAlias = "str | Fill | None"


@dataclass(frozen=True)
class Dimension:
    """A Linear Dimension between two board points, snapped to the board outline of a view.

    ``target`` names a view of the same sheet. ``start`` and ``end`` are board points in nm; ``origin`` is
    where the board's origin lies on the sheet, so a page point is ``origin`` plus a board point (1:1).
    ``reference`` is the dimension line's point relative to ``start``. Horizontal or vertical only.
    """

    target: str
    start: tuple[int, int]
    end: tuple[int, int]
    origin: tuple[int, int]
    reference: tuple[int, int]


@dataclass(frozen=True)
class DraftsmanItem:
    """An authored shell, with geometry in integer nm from the page's lower-left corner.

    ``name`` is a stable path, not a native member. Texts have one string; notes may have many. Tables
    and the legend take round F0's columns and settings; an empty ``title`` gives F0's title. A Linear
    Dimension needs ``dimension``; its ``at`` and ``size`` are only its estimated box.
    """

    name: str
    kind: Kind
    at: tuple[int, int]
    size: tuple[int, int]
    title: str = ""
    texts: tuple[str, ...] = ()
    side: Literal["Top", "Bottom", "All"] = "Top"
    designators: bool = True
    dimension: Dimension | None = None


@dataclass(frozen=True)
class DraftsmanSheet:
    name: str
    title: str
    paper: str
    size: tuple[int, int]
    items: tuple[DraftsmanItem, ...]


@dataclass(frozen=True)
class DraftsmanSpec:
    name: str
    sheets: tuple[DraftsmanSheet, ...]
    parameters: tuple[tuple[str, str], ...] = ()
    text_size: int = 1_500_000


def units(nm: int) -> str:
    """Integer nm to the measured 1/96-inch unit, rounded far below a nanometre, without floats."""
    if type(nm) is not int:
        raise ValueError("Draftsman geometry must use integer nanometres")
    with localcontext() as ctx:
        ctx.prec = 40
        value = (Decimal(nm) * 96 / 25_400_000).quantize(Decimal("0.000000000001"))
    return format(value, "f").rstrip("0").rstrip(".") if value else "0"


def _element(parent: ET.Element, name: str, value: str | None = None) -> ET.Element:
    found = ET.SubElement(parent, _NS + name)
    found.text = value
    return found


def _point(parent: ET.Element, name: str, at: tuple[int, int]) -> None:
    point = _element(parent, name)
    for axis, nm in zip(("X", "Y"), at, strict=True):
        _element(point, axis, units(nm))


def _size(parent: ET.Element, size: tuple[int, int]) -> None:
    found = _element(parent, "Size")
    _element(found, "Height", units(size[1]))
    _element(found, "Width", units(size[0]))


def _black(parent: ET.Element, name: str) -> None:
    _rgb(0, 0, 0)(_element(parent, name))


def _rgb(red: int, green: int, blue: int) -> Fill:
    def fill(color: ET.Element) -> None:
        for channel, value in (("A", 255), ("B", blue), ("G", green), ("R", red)):
            _element(color, channel, str(value))

    return fill


def _xy(at: tuple[int, int]) -> Fill:
    def fill(point: ET.Element) -> None:
        for axis, nm in zip(("X", "Y"), at, strict=True):
            _element(point, axis, units(nm))

    return fill


def _wh(size: tuple[int, int]) -> Fill:
    def fill(found: ET.Element) -> None:
        _element(found, "Height", units(size[1]))
        _element(found, "Width", units(size[0]))

    return fill


def _fraction(denominator: int, numerator: int) -> Fill:
    def fill(found: ET.Element) -> None:
        _element(found, "Denominator", str(denominator))
        _element(found, "Numenator", str(numerator))

    return fill


def _members(parent: ET.Element, members: Sequence[tuple[str, Value]]) -> None:
    """Write ``members`` in order: a string is the text, ``None`` is ``i:nil``, a function fills it."""
    for name, value in members:
        if isinstance(value, str):
            _element(parent, name, value)
        elif value is None:
            _element(parent, name).set(_NIL, "true")
        else:
            value(_element(parent, name))


def _dictionary(entry: str, pairs: Sequence[tuple[str, str]]) -> Fill:
    """A data-contract dictionary of F0: ``a:<entry>`` children, each an ``a:Key`` and an ``a:Value``."""

    def fill(found: ET.Element) -> None:
        for key, value in pairs:
            pair = ET.SubElement(found, _A + entry)
            ET.SubElement(pair, _A + "Key").text = key
            ET.SubElement(pair, _A + "Value").text = value

    return fill


def _sequence(name: str, values: Sequence[str]) -> Fill:
    def fill(found: ET.Element) -> None:
        for value in values:
            _element(found, name, value)

    return fill


_BLACK = _rgb(0, 0, 0)
_UNITS: tuple[tuple[str, Value], ...] = (
    ("DualUnits", "Imperial"),
    ("DualUnitsV2", "1"),
    ("DualValuePrecision", "-1"),
)
# Font ids name the one FontStyleData the candidate root writes; other style ids keep F0's values.
_FONT = "1"


def _identifier(name: str) -> str:
    # A conservative positive 31-bit candidate; the hash and the collision check are our choices.
    value = int.from_bytes(hashlib.sha256(("fenolite.draftsman:" + name).encode()).digest()[:4], "big")
    return str((value & 0x7FFF_FFFF) or 1)


def _guid(path: str) -> str:
    # F0 note entries carry 32 hexadecimal digits; deriving them from the path is our choice.
    return hashlib.sha256(("fenolite.draftsman.entry:" + path).encode()).hexdigest()[:32]


def _head(found: ET.Element, item: DraftsmanItem, path: str, title: str, *, bound: bool = True) -> None:
    """`Id`, `Anchor`, `OriginatedFromTemplate`, `ElementItems` and, for a bound item, `BoardSourceName`."""
    _members(
        found,
        (
            ("Id", _identifier(path)),
            ("Anchor", "Top Left"),
            ("OriginatedFromTemplate", "false"),
        ),
    )
    data = _element(_element(found, "ElementItems"), "ElementItemData")
    data.set(_TYPE, "LinkedTextDrawingItemData")
    _members(
        data,
        (
            ("Name", "Title"),
            ("Color", _BLACK),
            ("FontStyleId", _FONT),
            ("HorizontalAlignment", "Left"),
            ("HorizontalAlignmentV2", "0"),
            ("IsShow", "true"),
            ("ManualOffset", _xy((0, 0))),
            ("ManualPositioning", "false"),
            ("Scaled", "false"),
            ("Title", title),
            ("UseDocumentFont", "true"),
            ("VerticalAlignment", "Top"),
            ("VerticalAlignmentV2", "0"),
        ),
    )
    if bound:
        # The public documents leave it empty; F0 holds the VM's absolute path, which is never written.
        ET.SubElement(found, f"{{{BOARD}}}BoardSourceName").text = ""


_DRILL_KEYS = (
    ("DrillSymbol", "Symbol"),
    ("CountHoles", "Count"),
    ("HoleSize", "Hole Size"),
    ("Plated", "Plated"),
    ("HoleType", "Hole Type"),
    ("DrillLayerPair", "Drill Layer Pair"),
    ("ViaPad", "Via / Pad"),
    ("PadShape", "Pad Shape"),
    ("Template", "Template"),
    ("Description", "Description"),
    ("HoleTolerance", "Hole Tolerance"),
    ("HoleLength", "Hole Length"),
)
_DRILL_COLUMNS = (
    *(name for _, name in _DRILL_KEYS),
    "Counterhole Angle",
    "Counterhole Depth",
    "Via Type",
    "Via Feature",
)
_DRILL_SHOWN = ("DrillSymbol", "CountHoles", "HoleSize", "Plated", "HoleTolerance")


def _drill_columns(found: ET.Element) -> None:
    shown = {name for key, name in _DRILL_KEYS if key in _DRILL_SHOWN}
    for index, name in enumerate(_DRILL_COLUMNS):
        pair = ET.SubElement(found, _A + "KeyValueOfintDrillTableColumnA8rmZfqX")
        ET.SubElement(pair, _A + "Key").text = str(index)
        _members(
            ET.SubElement(pair, _A + "Value"),
            (
                ("Align", "Left"),
                ("HAlign", "0"),
                ("Name", name),
                ("Position", str(index)),
                ("SortOrder", "false" if name == "Hole Size" else None),
                ("VAlign", "1"),
                ("Visible", "true" if name in shown else "false"),
                ("Width", "0"),
            ),
        )


def _drill_table(found: ET.Element, item: DraftsmanItem, path: str) -> None:
    title = item.title or "Drill Table"
    keys = tuple(key for key, _ in _DRILL_KEYS)
    _head(found, item, path, title)
    _members(
        found,
        (
            ("BottomLayer", None),
            (
                "ColumnAligns",
                _dictionary(
                    "KeyValueOfDrillTableColumnDataHorizontalAlignment_SGWc8z3x", [(k, "Left") for k in keys]
                ),
            ),
            ("ColumnNames", _dictionary("KeyValueOfDrillTableColumnDatastringWwj0USu5", _DRILL_KEYS)),
            ("ColumnQueue", _sequence("DrillTableColumnData", keys)),
            (
                "ColumnWidths",
                _dictionary("KeyValueOfDrillTableColumnDatadoubleWwj0USu5", [(k, "0") for k in keys]),
            ),
            ("Columns", _drill_columns),
            *_UNITS,
            ("EvenLineColor", _rgb(192, 192, 192)),
            ("HorizontalAlignment", "0"),
            ("ImperialPrecision", "0"),
            ("IsShowFooter", "true"),
            ("IsShowTitle", "true"),
            ("LabelFontStyleId", _FONT),
            ("LayerPair", None),
            ("LineStyleId", "2"),
            ("Location", _xy(item.at)),
            ("MetricPrecision", "0"),
            ("NonEvenLineColor", _rgb(211, 211, 211)),
            (
                "OrderRule",
                _dictionary("KeyValueOfDrillTableColumnDatabooleanWwj0USu5", (("HoleSize", "false"),)),
            ),
            ("PadsVias", "All"),
            ("PadsViasV2", "3"),
            ("PlatedNonPlatedVisibility", "All"),
            ("PlatedNonPlatedVisibilityV2", "3"),
            ("ShowDualUnits", "false"),
            ("ShowUnitNames", "true"),
            ("ShowUnits", "false"),
            ("Size", _wh(item.size)),
            ("TextColor", _BLACK),
            ("Title", title),
            ("TitleFontStyleId", _FONT),
            ("TitleTextColor", _BLACK),
            ("TopLayer", None),
            ("Units", "Imperial"),
            ("UnitsV1", "Metric"),
            ("UnitsV2", "0"),
            ("UseDocumentDualUnits", "true"),
            ("UseDocumentFont", "false"),
            ("UseDocumentFontForTitle", "true"),
            ("UseDocumentUnits", "true"),
            ("ValuePrecision", "-1"),
            ("Version", "3"),
            ("VerticalAlignment", "2"),
            ("VisibilityColumns", _sequence("DrillTableColumnData", _DRILL_SHOWN)),
        ),
    )


def _legend(found: ET.Element, item: DraftsmanItem, path: str) -> None:
    title = item.title or "Layer Stack Legend"
    _head(found, item, path, title)
    _members(
        found,
        (
            ("BetweenLayersSpace", units(1_500_000)),
            ("CoreViewLayerHeight", units(4_000_000)),
            ("DielectricLayerTextColor", _BLACK),
            ("DielectricLayerTextFontStyleId", _FONT),
            ("DrawBreakLine", "false"),
            *_UNITS,
            ("HatchSpace", "10"),
            ("HatchedLineStyleId", "2"),
            ("HorizontalAlignment", "0"),
            ("ImperialPrecision", "0"),
            ("IsAlignTableRows", "false"),
            ("IsShowDrillPairs", "true"),
            ("IsShowFooter", "true"),
            ("IsShowHeader", "true"),
            ("IsShowTitle", "true"),
            ("IsShowUnits", "false"),
            ("LineStyleId", "1"),
            ("Location", _xy(item.at)),
            ("MaxLayerHeight", units(30_000_000)),
            ("MetricPrecision", "0"),
            ("MinLayerHeight", units(1_000_000)),
            ("PrepregViewLayerHeight", units(3_000_000)),
            ("RelationWidth", units(12_000_000)),
            ("ShowDualUnits", "false"),
            ("ShowTrueWidth", "true"),
            ("ShowUnitNames", "true"),
            ("SignalLayerTextColor", _BLACK),
            ("SignalLayerTextFontStyleId", _FONT),
            ("Size", _wh(item.size)),
            ("SourceStack", ""),
            ("SourceStackId", ""),
            ("TextColor", _BLACK),
            ("TextFontStyleId", _FONT),
            ("Title", title),
            ("TitleFontStyleId", _FONT),
            ("TitleTextColor", _BLACK),
            ("Units", "Imperial"),
            ("UnitsV1", "Metric"),
            ("UnitsV2", "0"),
            ("UseDocumentDualUnits", "true"),
            ("UseDocumentFont", "true"),
            ("UseDocumentFontForTitle", "true"),
            ("UseDocumentUnits", "true"),
            ("UsualLayerTextColor", _rgb(169, 169, 169)),
            ("UsualLayerTextFontStyleId", _FONT),
            ("ValuePrecision", "-1"),
            ("Version", "1"),
            ("VerticalAlignment", "0"),
            ("ViewLayerHeight", units(2_000_000)),
            ("ViewLineStyleId", "1"),
            ("ViewScale", _fraction(1, 100)),
            ("ViewWidth", units(35_000_000)),
        ),
    )


_BOM_COLUMNS = (
    ("Left", "2", "Line #", 15_000_000),
    ("Center", "0", "Designator", 45_000_000),
    ("Center", "0", "Comment", 45_000_000),
    ("Left", "2", "Quantity", 15_000_000),
)


def _bom_columns(found: ET.Element) -> None:
    for index, (align, data_type, name, width) in enumerate(_BOM_COLUMNS):
        _members(
            _element(found, "BomColumnInfo"),
            (
                ("Align", align),
                ("DataType", data_type),
                ("Id", str(index)),
                ("Name", name),
                ("Order", None),
                ("SourcePattern", "{" + name + "}"),
                ("Width", units(width)),
            ),
        )


def _members_of(members: Sequence[tuple[str, Value]]) -> Fill:
    return lambda found: _members(found, members)


_VARIATION = _members_of(
    (("SelectionType", "AllVariants"), ("SelectionTypeV2", "0"), ("Variant", "Document"))
)


def _bom(found: ET.Element, item: DraftsmanItem, path: str) -> None:
    title = item.title or "Bill Of Materials"
    _head(found, item, path, title)
    _members(
        found,
        (
            ("CurrentPage", "1"),
            ("CurrentVariation", _VARIATION),
            ("DataSource", "-1"),
            ("DataSourceKind", "Project"),
            ("DataSourceKindV2", "1"),
            *_UNITS,
            ("EvenRowColor", _rgb(192, 192, 192)),
            ("HorizontalAlignment", "0"),
            ("IsShowTitle", "true"),
            ("IsTableHeaderBottom", "false"),
            ("LabelFontStyleId", _FONT),
            ("LimitPageHeight", "false"),
            ("LineStyleId", "2"),
            ("Location", _xy(item.at)),
            ("MaxPageHeight", "200"),
            ("NonEvenRowColor", _rgb(211, 211, 211)),
            ("PageGroupId", "0"),
            ("ShowDualUnits", "false"),
            ("ShowEmptyLines", "true"),
            ("ShowNotFitted", "false"),
            ("ShowNotFittedV2", "0"),
            ("ShowUnitNames", "true"),
            ("ShowedColumns", _bom_columns),
            ("Size", _wh(item.size)),
            ("TextColor", _BLACK),
            ("Title", title),
            ("TitleFontStyleId", _FONT),
            ("TitleTextColor", _BLACK),
            ("Units", "Metric"),
            ("UnitsV2", "0"),
            ("UseDocumentDualUnits", "true"),
            ("UseDocumentFont", "false"),
            ("UseDocumentUnits", "true"),
            ("UseTitleDocumentFont", "true"),
            ("ValuePrecision", "-1"),
            ("VerticalAlignment", "0"),
            ("ViewMode", "Base"),
            ("ViewSide", item.side),
            # F0 shows 0 for a Top view and for the All table alike; other values are not measured.
            ("ViewSideV2", "0"),
        ),
    )


def _note(found: ET.Element, item: DraftsmanItem, path: str) -> None:
    def entries(elements: ET.Element) -> None:
        for index, text in enumerate(item.texts):
            _members(
                _element(elements, "NoteElement"),
                (
                    ("BorderStyle", "None"),
                    ("BorderStyleV2", "0"),
                    ("FirstLineIndent", "0"),
                    ("Id", _guid(f"{path}/{index}")),
                    ("Postfix", "."),
                    ("Text", text),
                ),
            )

    _head(found, item, path, item.title, bound=False)
    _members(
        found,
        (
            ("ElementFontStyleId", _FONT),
            ("ElementTextColor", _BLACK),
            ("Elements", entries),
            ("HorizontalSpacing", units(2_000_000)),
            # StartPoint is the note's top-left, whereas the spec consistently uses lower-left corners.
            ("StartPoint", _xy((item.at[0], item.at[1] + item.size[1]))),
            ("Title", item.title),
            ("TitleFont", None),
            ("TitleFontStyleId", _FONT),
            ("TitleTextColor", _BLACK),
            ("TitleVisible", "true" if item.title else "false"),
            ("UseDocumentFontForElements", "true"),
            ("UseDocumentFontForTitle", "true"),
            ("VerticalSpacing", units(2_000_000)),
            ("Width", units(item.size[0])),
        ),
    )


def _anchor(target: str, board: tuple[int, int], page: tuple[int, int]) -> Fill:
    point = f"{units(board[0])}, {units(board[1])}"
    snap_id = f"GI|Board Outline|Point: {point}"

    def snap(found: ET.Element) -> None:
        _members(
            found,
            (
                ("Arc", None),
                ("GroupId", "GI"),
                ("ItemId", "Board Outline"),
                ("Points", lambda points: _xy(board)(_element(points, "PointData"))),
            ),
        )
        z = _element(found, "PointsZ")
        ET.SubElement(z, _A + "double").text = "0"
        _members(found, (("SnapDesignation", "5"), ("SnapType", "0")))

    def fill(found: ET.Element) -> None:
        _members(
            found,
            (
                ("AnchorType", "Snap"),
                ("AnchorType2", "Snap"),
                ("AnchorTypeV3", "2"),
                ("ContentPoint", _xy(page)),
                ("PointOnPage", _xy(page)),
                ("Snap", snap),
                ("SnapDesignationData", "Outline"),
                ("SnapDesignationDataV2", "5"),
                ("SnapId", snap_id),
                ("SnapIdV2", snap_id),
                ("SnapPointOffset", _xy((0, 0))),
                ("SnapTargetItemId", target),
            ),
        )

    return fill


def _linear(found: ET.Element, item: DraftsmanItem, path: str, target: str) -> None:
    dimension = item.dimension
    assert dimension is not None
    start, end, origin = dimension.start, dimension.end, dimension.origin
    # F0 measures a horizontal dimension, whose extension lines run along Y; a vertical one is mirrored.
    direction = (0, 1) if start[1] == end[1] else (1, 0)
    red = _rgb(192, 0, 0)
    _members(
        found,
        (
            ("Id", _identifier(path)),
            ("Anchor", "Top Left"),
            ("OriginatedFromTemplate", "false"),
            ("ArrowStyleId", "1"),
            ("DimensionLineStyleId", "3"),
            ("DualTolerancePrecision", "-1"),
            *_UNITS,
            ("ExtensionLineStyleId", "3"),
            ("ExtensionLinesGap", units(400_000)),
            ("ExtensionLinesOffset", units(400_000)),
            ("FontStyleId", _FONT),
            ("IsValueOverridden", "false"),
            ("NegativeTolerance", "0"),
            ("OverriddenValue", "0"),
            ("PositiveTolerance", "0"),
            ("ShowDualUnits", "false"),
            ("ShowUnitNames", "true"),
            ("TextColor", red),
            ("TextPrefix", ""),
            ("TextSuffix", ""),
            ("ToleranceFontStyleId", _FONT),
            ("TolerancePrecision", "-1"),
            ("ToleranceTextColor", red),
            ("ToleranceType", "None"),
            ("ToleranceTypeV2", "0"),
            ("ToleranceUseDocumentFont", "true"),
            ("UseDocumentDualUnits", "true"),
            ("UseDocumentFont", "true"),
            ("UseDocumentUnits", "true"),
            ("ValuePrecision", "-1"),
            ("AdditionalText", ""),
            ("ArrowPosition", "Inside"),
            ("ArrowPositionV2", "0"),
            ("DimensionReferencePoint", _xy(dimension.reference)),
            ("EndAnchor", _anchor(target, end, (origin[0] + end[0], origin[1] + end[1]))),
            ("ExtensionsDirection", _members_of((("X", str(direction[0])), ("Y", str(direction[1]))))),
            ("HasBrokenSnaps", "false"),
            ("ShowAdditionalText", "false"),
            ("StartAnchor", _anchor(target, start, (origin[0] + start[0], origin[1] + start[1]))),
            ("TextPosition", "InsideAligned"),
            ("TextPositionV2", "2"),
            ("Units", "Metric"),
            ("UnitsV2", "0"),
        ),
    )


_NATIVE: dict[str, Callable[[ET.Element, DraftsmanItem, str], None]] = {
    "DrillTableBoardView": _drill_table,
    "LayerStackLegendView": _legend,
    "BillOfMaterialsView": _bom,
    "Note": _note,
}


def _item(parent: ET.Element, item: DraftsmanItem, path: str, sheet: str = "") -> None:
    found = _element(parent, "Item")
    found.set(_TYPE, item.kind)
    if item.kind in _NATIVE:
        _NATIVE[item.kind](found, item, path)
        return
    if item.kind == "LinearDimension":
        assert item.dimension is not None
        _linear(found, item, path, _identifier(f"{sheet}/{item.dimension.target}"))
        return
    _element(found, "Id", _identifier(path))
    _element(found, "OriginatedFromTemplate", "false")
    if item.kind == "Text":
        _black(found, "Color")
        _element(found, "FontStyleId", "1")
        rect = _element(found, "Rect")
        for key, value in (
            ("Height", item.size[1]),
            ("Width", item.size[0]),
            ("X", item.at[0]),
            ("Y", item.at[1]),
        ):
            _element(rect, key, units(value))
        _element(found, "Text", item.texts[0])
    else:
        _point(found, "Location", item.at)
        if item.kind in ("BoardAssemblyViewData", "DrillViewView"):
            scale = _element(found, "Scale")
            _element(scale, "Denominator", "1")
            _element(scale, "Numenator", "1")
        _element(found, "Title", item.title)
        if item.kind == "BoardAssemblyViewData":
            display = _element(found, "DefaultComponentDisplaySettings")
            _element(display, "ShowDesignator", str(item.designators).lower())
            display = _element(found, "ViewComponentDisplaySettingsData")
            _element(display, "ComponentCaptionSource", "Designator")
        _element(found, "ViewSide", item.side)


def _validate(spec: DraftsmanSpec) -> None:
    if not spec.name or not spec.sheets or spec.text_size <= 0:
        raise ValueError("a Draftsman specification needs a name and a sheet")
    paths = [spec.name]
    for sheet in spec.sheets:
        paths.append(f"{spec.name}/{sheet.name}")
        if not sheet.name or any(n <= 0 for n in sheet.size):
            raise ValueError("a sheet needs a stable name and positive dimensions")
        for item in sheet.items:
            paths.append(f"{spec.name}/{sheet.name}/{item.name}")
            if item.kind == "Note":
                paths.extend(f"{spec.name}/{sheet.name}/{item.name}/{n}" for n in range(len(item.texts)))
            if item.kind not in KINDS or not item.name or any(n <= 0 for n in item.size):
                raise ValueError("an item needs a known kind, stable name and positive dimensions")
            if item.kind == "Text" and len(item.texts) != 1:
                raise ValueError("a Text needs exactly one string")
            if item.kind == "Note" and not item.texts:
                raise ValueError("a Note needs at least one entry")
            if (item.kind == "LinearDimension") != (item.dimension is not None):
                raise ValueError("a Linear Dimension, and only one, needs its dimension")
            if item.dimension is not None:
                views = {i.name for i in sheet.items if i.kind in ("BoardAssemblyViewData", "DrillViewView")}
                start, end = item.dimension.start, item.dimension.end
                if item.dimension.target not in views:
                    raise ValueError("a Linear Dimension must snap to a view of its sheet")
                if start == end or (start[0] != end[0] and start[1] != end[1]):
                    raise ValueError("a Linear Dimension is horizontal or vertical, between two points")
    if len(set(paths)) != len(paths) or len({_identifier(p) for p in paths}) != len(paths):
        raise ValueError("Draftsman object paths and identifiers must be unique")
    if len({name for name, _ in spec.parameters}) != len(spec.parameters):
        raise ValueError("Draftsman parameter names must be unique")
    texts = [spec.name, *(value for pair in spec.parameters for value in pair)]
    texts += [text for sheet in spec.sheets for item in sheet.items for text in (item.title, *item.texts)]
    if any(
        any(
            ord(c) < 32 and c not in "\t\r\n" or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF)
            for c in text
        )
        for text in texts
    ):
        raise ValueError("Draftsman text contains a character XML 1.0 cannot represent")


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def encode(text: bytes) -> bytes:
    """Encode XML as independent stored chunks of at most the measured 1 MiB length.

    Validity by Fenolite's reader is mechanical evidence only. FP1 must establish native acceptance.
    """
    if not text:
        raise ValueError("a Draftsman document cannot be empty")
    return b"".join(
        b"\0" + _varint(len(part)) + part
        for offset in range(0, len(text), CHUNK_SIZE)
        if (part := text[offset : offset + CHUNK_SIZE])
    )


def write_draftsman(spec: DraftsmanSpec) -> bytes:
    """Write a candidate shell, without opening a file or bypassing the build's closed native gate."""
    _validate(spec)
    root = ET.Element(_NS + "Document")
    _element(root, "Id", _identifier(spec.name))
    styles = _element(root, "FontStyles")
    font = _element(styles, "FontStyleData")
    _element(font, "FamilyName", "Arial")
    _element(font, "Id", "1")
    _element(font, "Size", units(spec.text_size))
    _element(root, "FormatVersion", "22")
    pages = _element(root, "Pages")
    for sheet in spec.sheets:
        path = f"{spec.name}/{sheet.name}"
        page = _element(pages, "Page")
        _element(page, "Id", _identifier(path))
        items = _element(page, "Items")
        for item in sheet.items:
            _item(items, item, f"{path}/{item.name}", path)
        _element(page, "SheetSizingMode", "StandardSize")
        _size(page, sheet.size)
        _element(page, "StandardSizeName", sheet.paper)
    parameters = _element(root, "Parameters")
    for name, value in spec.parameters:
        parameter = _element(parameters, "DrawingDocumentParameterData")
        _element(parameter, "Name", name)
        _element(parameter, "Value", value)
    # Relative binding is a candidate choice; the public files have absolute source paths (FP4 pending).
    _element(root, "SourceDocumentName", f"{spec.name}.PcbDoc")
    return encode(_xml(root, root=True).encode("utf-8"))


def _xml(element: ET.Element, *, root: bool = False) -> str:
    """Serialize our closed vocabulary without ElementTree's mutable global namespace registry."""
    space, _, name = element.tag[1:].partition("}")
    attributes = f" xmlns={quoteattr(NAMESPACE)} xmlns:i={quoteattr(INSTANCE)}" if root else ""
    if space == ARRAYS:
        name = "a:" + name
    elif space == BOARD:
        if len(element):
            raise ValueError("a board-namespace member holds text only")
        attributes += f" xmlns={quoteattr(BOARD)}"
    elif space != NAMESPACE:
        raise ValueError("an unknown namespace in the candidate Draftsman tree")
    if space != ARRAYS and any(child.tag.startswith(_A) for child in element):
        attributes += f" xmlns:a={quoteattr(ARRAYS)}"
    for key, value in element.attrib.items():
        if key == _TYPE:
            attributes += f" i:type={quoteattr(value)}"
        elif key == _NIL:
            attributes += f" i:nil={quoteattr(value)}"
        else:
            raise ValueError("an unknown attribute in the candidate Draftsman tree")
    content = escape(element.text or "").replace("\r", "&#13;")
    content += "".join(_xml(child) for child in element)
    return f"<{name}{attributes}>{content}</{name}>"


def written_scope(root: ET.Element) -> DraftsmanSummary:
    """The reader's sheet/object/text/parameter-name scope, not a native rendering verdict."""
    return summary(DraftsmanFile((), root))


__all__ = [
    "ARRAYS",
    "BOARD",
    "DRAFTSMAN_KIND",
    "EVIDENCE",
    "KINDS",
    "NATIVE_WRITE",
    "Dimension",
    "DraftsmanItem",
    "DraftsmanSheet",
    "DraftsmanSpec",
    "encode",
    "units",
    "write_draftsman",
    "written_scope",
]
