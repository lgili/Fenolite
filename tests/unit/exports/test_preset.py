# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Export presets (capability manufacturing-exports, "Export presets"; change c0074). The preset texts are
written for these tests; Fenolite ships none."""

from __future__ import annotations

from pathlib import Path

import pytest

from fenolite.core.errors import FormatError
from fenolite.exports import plan
from fenolite.exports.preset import (
    DEFAULTS,
    FORBIDDEN,
    PRESET_SCHEMA,
    TABLES,
    Preset,
    arguments,
    pos_file,
    read_preset,
)

HEAD = f'schema = "{PRESET_SCHEMA}"\n'
LAYERS = ("F.Cu", "B.Cu", "Edge.Cuts")
KINDS = ("gerbers", "drill", "pos", "ipcd356")
ROOT = Path(__file__).resolve().parents[3]


def args(kind: str, body: str) -> tuple[str, ...]:
    return arguments(kind, read_preset(HEAD + body, file="fab.toml"), stem="board", layers=LAYERS)


def fixed(kind: str) -> tuple[str, ...]:
    return tuple(plan.arguments(kind, stem="board", layers=LAYERS))


def test_protel_extensions_and_inches() -> None:
    body = '[gerbers]\nprotel_extensions = true\n[drill]\nunits = "in"\n'
    gerbers, drill = args("gerbers", body), args("drill", body)
    assert "--no-protel-ext" not in gerbers and gerbers[-2:] == ("--layers", ",".join(LAYERS))
    assert drill == tuple("in" if a == "mm" else a for a in fixed("drill"))
    assert drill[drill.index("--excellon-units") + 1] == "in"
    assert args("pos", body) == fixed("pos")


def test_unknown_key() -> None:
    with pytest.raises(FormatError, match=r"drill\.speed") as raised:
        read_preset(HEAD + "[drill]\nspeed = 3\n", file="fab.toml")
    assert raised.value.file == "fab.toml" and "fab.toml" in str(raised.value)


def test_defaults_equal_no_preset() -> None:
    lines = [HEAD]
    for table, defaults in DEFAULTS.items():
        lines.append(f"[{table}]\n")
        for key, value in defaults.items():
            shown = str(value).lower() if isinstance(value, bool) else f'"{value}"'
            lines.append(f"{key} = {shown}\n")
    preset = read_preset("".join(lines))
    for kind in KINDS:
        assert arguments(kind, preset, stem="board", layers=LAYERS) == fixed(kind)
        assert arguments(kind, None, stem="board", layers=LAYERS) == fixed(kind)
        assert arguments(kind, Preset(), stem="board", layers=LAYERS) == fixed(kind)


def test_every_gerber_key() -> None:
    body = (
        '[gerbers]\nlayers = ["F.Cu", "Edge.Cuts"]\nprotel_extensions = true\nx2 = false\n'
        "netlist_attributes = false\naperture_macros = false\nprecision = 5\nsubtract_soldermask = true\n"
        "use_drill_file_origin = true\ninclude_border_title = true\nexclude_refdes = true\n"
        "exclude_value = true\n"
    )
    assert args("gerbers", body) == (
        "pcb", "export", "gerbers", "-o", "gerbers/", "--layers", "F.Cu,Edge.Cuts", "--no-x2",
        "--no-netlist", "--disable-aperture-macros", "--precision", "5", "--subtract-soldermask",
        "--use-drill-file-origin", "--include-border-title", "--exclude-refdes", "--exclude-value",
    )  # fmt: skip


def test_every_drill_key() -> None:
    body = (
        '[drill]\nformat = "excellon"\nunits = "in"\nseparate_th = false\nmirror_y = true\n'
        'minimal_header = true\norigin = "plot"\nzeros = "suppressleading"\noval_format = "route"\n'
        'map = "pdf"\n'
    )
    assert args("drill", body) == (
        "pcb", "export", "drill", "-o", "drill/", "--format", "excellon", "--excellon-units", "in",
        "--drill-origin", "plot", "--excellon-mirror-y", "--excellon-min-header",
        "--excellon-zeros-format", "suppressleading", "--excellon-oval-format", "route",
        "--generate-map", "--map-format", "pdf",
    )  # fmt: skip
    gerber = args("drill", '[drill]\nformat = "gerber"\ngerber_precision = 6\norigin = "plot"\n')
    assert gerber == (
        "pcb", "export", "drill", "-o", "drill/", "--format", "gerber", "--drill-origin", "plot",
        "--gerber-precision", "6",
    )  # fmt: skip


def test_every_pos_key_and_the_file_name() -> None:
    body = (
        '[pos]\nformat = "ascii"\nunits = "in"\nside = "front"\nexclude_dnp = true\nexclude_fp_th = true\n'
        "smd_only = true\nuse_drill_file_origin = true\nbottom_negate_x = true\n"
    )
    assert args("pos", body) == (
        "pcb", "export", "pos", "-o", "pos/board-pos.pos", "--format", "ascii", "--units", "in", "--side",
        "front", "--exclude-dnp", "--exclude-fp-th", "--smd-only", "--use-drill-file-origin",
        "--bottom-negate-x",
    )  # fmt: skip
    assert pos_file(None, "b") == "pos/b-pos.csv"
    assert pos_file(read_preset(HEAD + '[pos]\nformat = "gerber"\n'), "b") == "pos/b-pos.gbr"
    assert pos_file(read_preset(HEAD + '[pos]\nformat = "csv"\n'), "b") == "pos/b-pos.csv"


@pytest.mark.parametrize(
    ("text", "where"),
    [
        ("not toml [", ""),
        ('schema = "other.v1"\n', "schema"),
        ("[drill]\nunits = 1\n", "schema"),
        (HEAD + "[fab]\nx = 1\n", "fab"),
        (HEAD + "gerbers = 3\n", "gerbers"),
        (HEAD + '[drill]\nunits = "mil"\n', "drill.units"),
        (HEAD + "[drill]\nseparate_th = 1\n", "drill.separate_th"),
        (HEAD + "[gerbers]\nprecision = 7\n", "gerbers.precision"),
        (HEAD + "[gerbers]\nprecision = true\n", "gerbers.precision"),
        (HEAD + '[gerbers]\nlayers = "F.Cu"\n', "gerbers.layers"),
        (HEAD + "[gerbers]\nlayers = []\n", "gerbers.layers"),
        (HEAD + '[gerbers]\nlayers = ["F.Cu", "Top"]\n', "gerbers.layers"),
        (HEAD + '[gerbers]\nlayers = ["F.Cu", "F.Cu"]\n', "gerbers.layers"),
        (HEAD + "[gerbers]\ncheck_zones = true\n", "gerbers.check_zones"),
        (HEAD + '[gerbers]\nvariant = "A"\n', "gerbers.variant"),
        (HEAD + "[drill]\ngenerate_tenting = true\n", "drill.generate_tenting"),
        (HEAD + '[drill]\nformat = "gerber"\nunits = "in"\n', "drill.units"),
        (HEAD + "[drill]\ngerber_precision = 5\n", "drill.gerber_precision"),
        (HEAD + '[pos]\nside = "top"\n', "pos.side"),
    ],
)
def test_refused_presets(text: str, where: str) -> None:
    with pytest.raises(FormatError) as raised:
        read_preset(text, file="fab.toml")
    assert raised.value.file == "fab.toml" and raised.value.locator == where


def test_no_forbidden_option_can_be_given() -> None:
    every = {key for table in TABLES.values() for key in table}
    assert not {"check_zones", "board_plot_params", "variant", "generate_tenting"} & every
    assert FORBIDDEN == ("--check-zones", "--board-plot-params", "--variant", "--generate-tenting")


def test_fenolite_ships_no_preset() -> None:
    shipped = [
        path
        for path in (ROOT / "src").rglob("*.toml")
        if PRESET_SCHEMA in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert shipped == []
