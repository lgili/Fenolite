# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Export presets: a user's fabrication options, read from a TOML file of theirs (capability
manufacturing-exports, "Export presets"; ``docs/cli-contract.md``, "export").

A preset has the tables ``gerbers``, ``drill`` and ``pos``. Each key maps to one ``kicad-cli`` option that
9.0 and 10.0 both have (``H-K-EXPORT-OPTIONS``), and a key that is not given keeps the fixed value of the
export kind, so no preset and a preset of defaults run the same arguments. Fenolite ships no preset: the
values are the user's, from their fabricator.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from fenolite.backends.kicad.layers import is_canonical
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.exports import plan

PRESET_SCHEMA = "fenolite.export-preset.v0"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-EXPORT-OPTIONS",))
"""Joins the ``export`` envelope when a preset is used: the options exist on both majors by their help,
and what each does to the files is the fabricator's to check."""
BOOL = "bool"
LAYERS = "layers"
Rule = str | tuple[object, ...]
"""What a key takes: ``BOOL``, ``LAYERS``, or the tuple of its allowed values."""

TABLES: Mapping[str, Mapping[str, Rule]] = MappingProxyType(
    {
        "gerbers": MappingProxyType(
            {
                "layers": LAYERS,
                "protel_extensions": BOOL,
                "x2": BOOL,
                "netlist_attributes": BOOL,
                "aperture_macros": BOOL,
                "precision": (5, 6),
                "subtract_soldermask": BOOL,
                "use_drill_file_origin": BOOL,
                "include_border_title": BOOL,
                "exclude_refdes": BOOL,
                "exclude_value": BOOL,
            }
        ),
        "drill": MappingProxyType(
            {
                "format": ("excellon", "gerber"),
                "units": ("mm", "in"),
                "separate_th": BOOL,
                "mirror_y": BOOL,
                "minimal_header": BOOL,
                "origin": ("absolute", "plot"),
                "zeros": ("decimal", "suppressleading", "suppresstrailing", "keep"),
                "oval_format": ("route", "alternate"),
                "map": ("none", "pdf", "gerberx2", "ps", "dxf", "svg"),
                "gerber_precision": (5, 6),
            }
        ),
        "pos": MappingProxyType(
            {
                "format": ("csv", "ascii", "gerber"),
                "units": ("mm", "in"),
                "side": ("front", "back", "both"),
                "exclude_dnp": BOOL,
                "exclude_fp_th": BOOL,
                "smd_only": BOOL,
                "use_drill_file_origin": BOOL,
                "bottom_negate_x": BOOL,
            }
        ),
    }
)
"""Table → key → what the key takes, in the order the options are given."""

DEFAULTS: Mapping[str, Mapping[str, object]] = MappingProxyType(
    {
        "gerbers": MappingProxyType(
            {
                "protel_extensions": False,
                "x2": True,
                "netlist_attributes": True,
                "aperture_macros": True,
                "subtract_soldermask": False,
                "use_drill_file_origin": False,
                "include_border_title": False,
                "exclude_refdes": False,
                "exclude_value": False,
            }
        ),
        "drill": MappingProxyType(
            {
                "format": "excellon",
                "units": "mm",
                "separate_th": True,
                "mirror_y": False,
                "minimal_header": False,
                "origin": "absolute",
                "map": "none",
            }
        ),
        "pos": MappingProxyType(
            {
                "format": "csv",
                "units": "mm",
                "side": "both",
                "exclude_dnp": False,
                "exclude_fp_th": False,
                "smd_only": False,
                "use_drill_file_origin": False,
                "bottom_negate_x": False,
            }
        ),
    }
)
"""The value each key has without a preset: the fixed options of the export kinds. A key without a default
(`layers`, `precision`, `zeros`, `oval_format`, `gerber_precision`) gives no option unless it is set."""

EXCELLON_ONLY = ("units", "separate_th", "mirror_y", "minimal_header", "zeros", "oval_format")
"""Drill keys that have a meaning for the Excellon format only."""
POS_SUFFIX: Mapping[str, str] = MappingProxyType({"csv": ".csv", "ascii": ".pos", "gerber": ".gbr"})
"""Placement format → the suffix of ``pos/<stem>-pos``."""
FORBIDDEN = ("--check-zones", "--board-plot-params", "--variant", "--generate-tenting")
"""Options a preset never gives: the first two would make the files depend on more than the board as it
is, and the others exist on one major only."""


def _empty() -> Mapping[str, object]:
    return MappingProxyType({})


@dataclass(frozen=True)
class Preset:
    """The keys a preset file gives, per table; a key that is absent keeps its default."""

    gerbers: Mapping[str, object] = field(default_factory=_empty)
    drill: Mapping[str, object] = field(default_factory=_empty)
    pos: Mapping[str, object] = field(default_factory=_empty)

    def value(self, table: str, key: str) -> object:
        """The value of ``table.key``: the preset's, else the default, else ``None``."""
        given = cast(Mapping[str, object], getattr(self, table))
        return given[key] if key in given else DEFAULTS[table].get(key)


def _check(table: str, key: str, value: object, rule: Rule, file: str) -> object:
    where = f"{table}.{key}"
    if rule == BOOL:
        if not isinstance(value, bool):
            raise FormatError(f"{where} is true or false, not {value!r}", file=file, locator=where)
        return value
    if rule == LAYERS:
        names = cast(list[object], value) if isinstance(value, list) else None
        if not names or not all(isinstance(name, str) and is_canonical(name) for name in names):
            raise FormatError(
                f'{where} is a list of KiCad layer names such as "F.Cu", not {value!r}',
                file=file,
                locator=where,
            )
        if len(set(names)) != len(names):
            raise FormatError(f"{where} names a layer twice", file=file, locator=where)
        return tuple(cast(list[str], names))
    allowed = cast(tuple[object, ...], rule)
    if isinstance(value, bool) or value not in allowed:
        listed = ", ".join(repr(item) for item in allowed)
        raise FormatError(f"{where} is one of {listed}, not {value!r}", file=file, locator=where)
    return value


def read_preset(text: str, *, file: str = "") -> Preset:
    """The preset of a TOML text. A text that is not TOML, another ``schema``, an unknown table or key, or
    a value outside its allowed values raises ``FormatError`` naming ``file`` and the ``table.key``."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not TOML: {error}", file=file) from error
    if data.get("schema") != PRESET_SCHEMA:
        raise FormatError(
            f"schema is {data.get('schema')!r}, not {PRESET_SCHEMA!r}", file=file, locator="schema"
        )
    found: dict[str, dict[str, object]] = {name: {} for name in TABLES}
    for name, table in data.items():
        if name == "schema":
            continue
        if name not in TABLES or not isinstance(table, dict):
            raise FormatError(
                f"unknown table {name!r}; a preset holds {', '.join(TABLES)}", file=file, locator=name
            )
        for key, value in cast(dict[str, object], table).items():
            rule = TABLES[name].get(key)
            if rule is None:
                where = f"{name}.{key}"
                raise FormatError(
                    f"unknown key {where}; [{name}] holds {', '.join(TABLES[name])}", file=file, locator=where
                )
            found[name][key] = _check(name, key, value, rule, file)
    drill = found["drill"]
    excellon = drill.get("format", DEFAULTS["drill"]["format"]) == "excellon"
    for key in EXCELLON_ONLY if not excellon else ():
        if key in drill:
            where = f"drill.{key}"
            raise FormatError(f'{where} applies to format "excellon" only', file=file, locator=where)
    if excellon and "gerber_precision" in drill:
        where = "drill.gerber_precision"
        raise FormatError(f'{where} applies to format "gerber" only', file=file, locator=where)
    return Preset(*(MappingProxyType(found[name]) for name in TABLES))


def _flags(preset: Preset, table: str, flags: Sequence[tuple[str, str]]) -> list[str]:
    """The flags of the keys of ``flags`` that are true, in order."""
    return [flag for key, flag in flags if preset.value(table, key) is True]


def _gerbers(preset: Preset, stem: str, layers: Sequence[str]) -> list[str]:
    del stem
    entry = plan.KINDS["gerbers"]
    args = [*entry.words, "-o", f"{entry.folder}/"]
    if preset.value("gerbers", "protel_extensions") is not True:
        args.append("--no-protel-ext")
    chosen = cast(Sequence[str] | None, preset.value("gerbers", "layers")) or layers
    args += ["--layers", ",".join(chosen)]
    for key, flag in (
        ("x2", "--no-x2"),
        ("netlist_attributes", "--no-netlist"),
        ("aperture_macros", "--disable-aperture-macros"),
    ):
        if preset.value("gerbers", key) is False:
            args.append(flag)
    precision = preset.value("gerbers", "precision")
    if precision is not None:
        args += ["--precision", str(precision)]
    return args + _flags(
        preset,
        "gerbers",
        (
            ("subtract_soldermask", "--subtract-soldermask"),
            ("use_drill_file_origin", "--use-drill-file-origin"),
            ("include_border_title", "--include-border-title"),
            ("exclude_refdes", "--exclude-refdes"),
            ("exclude_value", "--exclude-value"),
        ),
    )


def _drill(preset: Preset, stem: str, layers: Sequence[str]) -> list[str]:
    del stem, layers
    entry = plan.KINDS["drill"]
    fmt = cast(str, preset.value("drill", "format"))
    args = [*entry.words, "-o", f"{entry.folder}/", "--format", fmt]
    if fmt == "excellon":
        args += ["--excellon-units", cast(str, preset.value("drill", "units"))]
        if preset.value("drill", "separate_th") is True:
            args.append("--excellon-separate-th")
    args += ["--drill-origin", cast(str, preset.value("drill", "origin"))]
    if fmt == "excellon":
        args += _flags(
            preset,
            "drill",
            (("mirror_y", "--excellon-mirror-y"), ("minimal_header", "--excellon-min-header")),
        )
        for key, flag in (("zeros", "--excellon-zeros-format"), ("oval_format", "--excellon-oval-format")):
            value = preset.value("drill", key)
            if value is not None:
                args += [flag, str(value)]
    drawn = preset.value("drill", "map")
    if drawn != "none":
        args += ["--generate-map", "--map-format", str(drawn)]
    precision = preset.value("drill", "gerber_precision")
    if precision is not None:
        args += ["--gerber-precision", str(precision)]
    return args


def pos_file(preset: Preset | None, stem: str) -> str:
    """The placement file below the output folder: ``pos/<stem>-pos`` with the suffix of its format."""
    fmt = "csv" if preset is None else cast(str, preset.value("pos", "format"))
    return f"{plan.KINDS['pos'].folder}/{stem}-pos{POS_SUFFIX[fmt]}"


def _pos(preset: Preset, stem: str, layers: Sequence[str]) -> list[str]:
    del layers
    entry = plan.KINDS["pos"]
    args = [*entry.words, "-o", pos_file(preset, stem)]
    for key, flag in (("format", "--format"), ("units", "--units"), ("side", "--side")):
        args += [flag, cast(str, preset.value("pos", key))]
    return args + _flags(
        preset,
        "pos",
        (
            ("exclude_dnp", "--exclude-dnp"),
            ("exclude_fp_th", "--exclude-fp-th"),
            ("smd_only", "--smd-only"),
            ("use_drill_file_origin", "--use-drill-file-origin"),
            ("bottom_negate_x", "--bottom-negate-x"),
        ),
    )


_BUILDERS = MappingProxyType({"gerbers": _gerbers, "drill": _drill, "pos": _pos})


def arguments(kind: str, preset: Preset | None, *, stem: str, layers: Sequence[str] = ()) -> tuple[str, ...]:
    """The ``kicad-cli`` arguments of ``kind`` without the board name, with each key of ``preset`` given as
    its option. Without a preset, and for a kind a preset has no table for, they are the fixed arguments
    of ``plan.arguments``."""
    builder = _BUILDERS.get(kind)
    if preset is None or builder is None:
        return tuple(plan.arguments(kind, stem=stem, layers=layers))
    args = tuple(builder(preset, stem, layers))
    assert not set(args) & set(FORBIDDEN)
    return args


__all__ = [
    "DEFAULTS",
    "EVIDENCE",
    "FORBIDDEN",
    "PRESET_SCHEMA",
    "TABLES",
    "Preset",
    "arguments",
    "pos_file",
    "read_preset",
]
