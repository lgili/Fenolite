# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Helpers of the build tests (change c0011): the blink design, variants and a hermetic resolver."""

from __future__ import annotations

import runpy
from pathlib import Path

from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.dsl import Design, mm, placements, to_model
from fenolite.lens.build import BuildOutput, build_design

ROOT = Path(__file__).resolve().parents[1]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
BLINK = BLINK_DIR / "design.py"
LIBS = ROOT / "tests" / "data" / "libs"


MARKS = (
    "# The blink uses three pins of the controller. The other 29 are marked, so the electrical rules checks\n"
    "# of both tools know that they are left open on purpose.\n"
    "no_connect(*(u1[pin] for pin in range(1, 33) if pin not in (1, 9, 10)))\n"
)
"""The lines of the blink example that mark the unused pins of its controller (c0061). Tests that connect
or mark those pins themselves build on the blink without them (``marks=False``)."""


def blink_text(marks: bool = True) -> str:
    """The blink script, as it is or without its no-connect marks."""
    text = BLINK.read_text(encoding="utf-8")
    assert MARKS in text
    return text if marks else text.replace(MARKS, "")


def blink(marks: bool = True) -> Design:
    if marks:
        design = runpy.run_path(str(BLINK))["design"]
    else:
        scope: dict[str, object] = {"__name__": "design"}
        exec(compile(blink_text(marks=False), str(BLINK), "exec"), scope)  # noqa: S102 - our own example
        design = scope["design"]
    assert isinstance(design, Design)
    return design


def blink_variant(
    folder: Path, old: str = "", new: str = "", *, append: str = "", marks: bool = True
) -> Path:
    """A copy of the blink script under ``folder`` with ``old`` replaced by ``new`` and ``append`` added,
    beside library tables that name the authored mini library by its absolute path; ``marks=False``
    leaves the no-connect marks of the example out."""
    folder.mkdir(parents=True, exist_ok=True)
    text = blink_text(marks)
    if old:
        assert old in text, old
        text = text.replace(old, new)
    script = folder / "design.py"
    script.write_text(text + append, encoding="utf-8")
    row = '\t(lib (name "Mini") (type "KiCad") (uri "{}") (options "") (descr ""))\n'
    for table, head, uri in (
        ("fp-lib-table", "fp_lib_table", LIBS / "Mini_v9.pretty"),
        ("sym-lib-table", "sym_lib_table", LIBS / "Mini_v9.kicad_sym"),
    ):
        (folder / table).write_text(f"({head}\n\t(version 7)\n{row.format(uri.as_posix())})\n", "utf-8")
    return script


POUR = 'design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3), connection="solid")\n'
"""The line that turns the blink script into its pour variant (c0031)."""


def pour_variant(**zone: object) -> Design:
    """The blink with a ``GND`` pour on ``B.Cu`` (0.3 mm clearance, solid pad connections); ``zone``
    overrides or adds arguments of its ``zone()`` call."""
    design = blink()
    arguments: dict[str, object] = {"layers": ("B.Cu",), "clearance": mm(0.3), "connection": "solid", **zone}
    design.zone(design.nets["GND"], **arguments)  # type: ignore[arg-type]
    return design


def pour_script(folder: Path, *, append: str = POUR, old: str = "", new: str = "") -> Path:
    """The pour variant as a script under ``folder`` (``blink_variant`` with the ``zone()`` line appended)."""
    return blink_variant(folder, old, new, append=append)


def resolver(
    target: int = 10,
    project_dir: Path = BLINK_DIR,
    config_home: Path | None = None,
    cache_dir: Path | None = None,
) -> LibraryResolver:
    """A resolver over the project tables of ``project_dir`` only (no global table, no install).

    ``config_home`` adds a global table; ``cache_dir`` adds a verified library cache, whose rows come from
    the directory scan (c0021). Either one turns ``use_global_table`` on.
    """
    return LibraryResolver(
        LibraryConfig(
            target_major=target,
            project_dir=project_dir,
            env={},
            config_home=config_home or project_dir / "no-such-config",
            install_dir=project_dir / "no-such-install",
            use_global_table=config_home is not None or cache_dir is not None,
            cache_dir=cache_dir,
        )
    )


def build(design: Design, target: int = 10, **kwargs: object) -> BuildOutput:
    """``build_design`` of ``design``; ``placements_override`` replaces ``placements(design)`` (c0019)."""
    project_dir = kwargs.pop("project_dir", BLINK_DIR)
    config_home = kwargs.pop("config_home", None)
    cache_dir = kwargs.pop("cache_dir", None)
    override = kwargs.pop("placements_override", None)
    return build_design(
        to_model(design),
        override if override is not None else placements(design),  # type: ignore[arg-type]
        name=design.name,
        copper=design.copper,  # type: ignore[arg-type]
        resolver=resolver(target, project_dir, config_home, cache_dir),  # type: ignore[arg-type]
        target=target,
        **kwargs,  # type: ignore[arg-type]
    )


def codes(output: BuildOutput) -> list[str]:
    return [i.code for i in output.issues]


def _uri(uri: str) -> str:
    """A library path as a table row holds it: with ``/``, as KiCad writes it on every system. A ``\\`` in a
    quoted KiCad string starts an escape, so a Windows path must not be written as it is."""
    return uri.replace("\\", "/")


def _rows(rows: dict[str, str]) -> str:
    return "".join(
        f'\t(lib (name "{n}") (type "KiCad") (uri "{_uri(u)}") (options "") (descr ""))\n'
        for n, u in rows.items()
    )


def project(tmp: Path, footprints: dict[str, str], symbols: dict[str, str]) -> Path:
    """A folder with an ``fp-lib-table`` and ``sym-lib-table`` (10.0 syntax) with these rows."""
    (tmp / "fp-lib-table").write_text(
        f"(fp_lib_table\n\t(version 7)\n{_rows(footprints)})\n", encoding="utf-8"
    )
    (tmp / "sym-lib-table").write_text(
        f"(sym_lib_table\n\t(version 7)\n{_rows(symbols)})\n", encoding="utf-8"
    )
    return tmp


HEADER_SYM = (
    '(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "fenolite-tests")\n\t(generator_version "9.0")\n'
)
FONT = "(effects (font (size 1.27 1.27)))"
PAD_LAYERS = '(layers "F.Cu" "F.Paste" "F.Mask")'


def _pin(i: int, number: str, name: str) -> str:
    at = f"(at 0 {-2.54 * i} 0) (length 2.54)"
    return f'\n\t\t\t(pin passive line {at} (name "{name}" {FONT}) (number "{number}" {FONT}))'


def symbol_lib(symbols: dict[str, list[tuple[str, str]]], footprint: str = "") -> str:
    """A 9-format symbol library: name → pins ``(number, name)``; ``footprint`` is each Footprint property."""
    body = []
    for name, pins in symbols.items():
        pin_text = "".join(_pin(i, num, pname) for i, (num, pname) in enumerate(pins))
        fields = (("Reference", "U"), ("Value", name), ("Footprint", footprint), ("Datasheet", ""))
        props = "".join(f'\n\t\t(property "{k}" "{v}" (at 0 0 0) {FONT})' for k, v in fields)
        unit = f'\n\t\t(symbol "{name}_1_1"{pin_text}\n\t\t)'
        body.append(f'\t(symbol "{name}" (in_bom yes) (on_board yes){props}{unit}\n\t)\n')
    return HEADER_SYM + "".join(body) + ")\n"


def footprint_file(name: str, pads: list[str], version: int = 20241229) -> str:
    """A footprint with one SMD pad per number (an empty number allowed)."""
    rows = "".join(
        f'\n\t(pad "{num}" smd rect (at {2 * i} 0) (size 1 1) {PAD_LAYERS} '
        f'(uuid "00000000-0000-4000-8000-{i + 1:012d}"))'
        for i, num in enumerate(pads)
    )
    head = f'(footprint "{name}"\n\t(version {version})\n\t(generator "fenolite-tests")\n\t(layer "F.Cu")'
    return f"{head}{rows}\n)\n"


def authored(tmp: Path, symbols: dict[str, list[tuple[str, str]]], footprints: dict[str, list[str]]) -> Path:
    """A project folder with library ``T`` holding ``symbols`` and ``footprints``."""
    (tmp / "T.pretty").mkdir(parents=True, exist_ok=True)
    for name, pads in footprints.items():
        (tmp / "T.pretty" / f"{name}.kicad_mod").write_text(footprint_file(name, pads), encoding="utf-8")
    (tmp / "T.kicad_sym").write_text(symbol_lib(symbols), encoding="utf-8")
    return project(tmp, {"T": "${KIPRJMOD}/T.pretty"}, {"T": "${KIPRJMOD}/T.kicad_sym"})
