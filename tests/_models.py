# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Boards whose footprints name the authored 3D model of ``tests/data/models/`` (change c0116).

The model is a box of 2 x 1 x 0.5 mm that ``kicad-cli`` 10.0.6 wrote from the authored board beside it;
no official library model is in the repository, and no test downloads one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from _boards import FIXTURE, footprint, pad, uid

from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.sexpr import Atom

MODELS = Path(__file__).resolve().parent / "data" / "models"
"""A folder laid out like a 3D model library: ``Fenolite.3dshapes/Box_2x1.step``."""
BOX_REL = "Fenolite.3dshapes/Box_2x1.step"
BOX = MODELS / BOX_REL


def official(rel: str = BOX_REL, major: int = 10) -> str:
    """``${KICAD<major>_3DMODEL_DIR}/<rel>``, the form of a model path of an official footprint."""
    return f"${{KICAD{major}_3DMODEL_DIR}}/{rel}"


def model_node(path: str) -> str:
    """A ``model`` node naming ``path``, written as a KiCad string: the backslashes of a Windows path are
    escaped, or the reader would decode ``\\a`` of ``D:\\a\\...`` as an escape sequence."""
    return f"(model {Atom.string(path).text} (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0)))"


LAYERS = (
    '(layers (0 "F.Cu" signal) (2 "B.Cu" signal) (1 "F.Mask" user) (3 "B.Mask" user) (25 "Edge.Cuts" user))'
)


def outline(x0: int, y0: int, x1: int, y1: int, n: int = 900) -> str:
    """A rectangle on ``Edge.Cuts``, in millimetres."""
    return (
        f"(gr_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.05) (type solid)) (fill no)"
        f' (layer "Edge.Cuts") (uuid "{uid(n)}"))'
    )


def two_copper(*items: str, version: int = 20241229) -> str:
    """A two-copper board with the given root items, on A4; ``kicad-cli`` 9 and 10 both load it."""
    return (
        f'(kicad_pcb (version {version}) (generator "fenolite-tests") (generator_version "9.0")'
        f' (general (thickness 1.6)) (paper "A4") {LAYERS} (setup (pad_to_mask_clearance 0))'
        f' (net 0 "") (net 1 "A") {" ".join(items)})'
    )


def model_board(models: Mapping[str, Sequence[str]], *, version: int = 20241229) -> str:
    """A two-copper board of 40 x 20 mm with one footprint per reference of ``models``, each with one pad
    and its model paths."""
    items = [
        footprint(
            10 * index + 1,
            ref=ref,
            at=f"{10 + 10 * index} 10",
            pads=" ".join((pad(10 * index + 5), *map(model_node, paths))),
        )
        for index, (ref, paths) in enumerate(models.items())
    ]
    return two_copper(*items, outline(0, 0, 40, 20), version=version)


def with_models(text: str, models: Mapping[str, str]) -> str:
    """The text of ``two_layer.kicad_pcb`` (or a board printed like it) with one model path added to the
    footprint of each reference of ``models``."""
    for ref, path in models.items():
        start = text.index(f'(property "Reference" "{ref}"')
        end = text.index("\n\t)\n", start)
        text = text[:end] + f"\n\t\t{model_node(path)}" + text[end:]
    return text


def two_layer_with_models(folder: Path, models: Mapping[str, str], *, name: str = "two_layer") -> Path:
    """A copy of the authored two-layer board in ``folder`` whose footprints name ``models``."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{name}.kicad_pcb"
    target.write_text(
        with_models(FIXTURE.read_text(encoding="utf-8"), models), encoding="utf-8", newline="\n"
    )
    return target


def resolver(tmp_path: Path, **overrides: object) -> LibraryResolver:
    """A resolver that sees no install, no KiCad configuration and only the environment it is given."""
    empty = tmp_path / "empty-config"
    empty.mkdir(exist_ok=True)
    settings: dict[str, object] = {
        "env": {},
        "install_dir": tmp_path / "no-install",
        "config_home": empty,
        "project_dir": None,
    }
    settings.update(overrides)
    return LibraryResolver(LibraryConfig(**settings))  # type: ignore[arg-type]


__all__ = [
    "BOX",
    "BOX_REL",
    "MODELS",
    "model_board",
    "model_node",
    "official",
    "outline",
    "resolver",
    "two_copper",
    "two_layer_with_models",
    "with_models",
]
