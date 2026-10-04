# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields in a build: the script's placement requests and their precedence over a rebuild
(``docs/dsl.md``, "Field placement"; ``docs/lens.md``, "Footprint fields").

``apply_requests`` applies the requests of one part to its placed footprint through the board-frame helpers
of ``backends.kicad.fields``; no geometry is computed here. A request reads like the DSL's ``FieldRequest``
(``FieldRequestLike``), so this module never imports the DSL.

``merge_fields`` decides every field of a matched part when a build merges an existing board: a locked
request wins, then the board's field, then an unlocked request, then the library's field. It is a two-way
merge without a base, as the placement precedence of ``lens.preserve`` is, and it reports its outcomes in
three lists instead of issues.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from fenolite.backends.kicad.fields import DEFAULT_GAP, OutsideSide, place_outside, set_field
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.core.units import Nm, Udeg
from fenolite.lens.preserve import PATH_PROPERTY, LayoutMatch, Merged, component_paths
from fenolite.model.board import FieldJustifyH, FieldJustifyV, FootprintField, FootprintInstance
from fenolite.model.design import Design

FIELD_LAYERS = {"silk": "SilkS", "fab": "Fab"}
"""A request's side-relative layer → the KiCad layer suffix; the prefix is ``F.`` or ``B.`` by the side."""


class FieldRequestLike(Protocol):
    """A field placement request (the DSL's ``FieldRequest``), read by attribute: lengths in nm, the angle in
    µdeg, ``None`` for a value that was not given."""

    @property
    def name(self) -> str: ...

    @property
    def dx(self) -> Nm | None: ...

    @property
    def dy(self) -> Nm | None: ...

    @property
    def rotation(self) -> Udeg | None: ...

    @property
    def layer(self) -> str | None: ...

    @property
    def visible(self) -> bool | None: ...

    @property
    def size(self) -> Nm | None: ...

    @property
    def thickness(self) -> Nm | None: ...

    @property
    def justify(self) -> str | None: ...

    @property
    def outside(self) -> str | None: ...

    @property
    def gap(self) -> Nm | None: ...

    @property
    def locked(self) -> bool: ...


def _justify(words: str) -> tuple[FieldJustifyH, FieldJustifyV]:
    found = words.split()
    h = next((w for w in found if w in ("left", "right")), "center")
    v = next((w for w in found if w in ("top", "bottom")), "center")
    return cast(FieldJustifyH, h), cast(FieldJustifyV, v)


def apply_request(instance: FootprintInstance, request: FieldRequestLike) -> FootprintInstance:
    """``instance`` with one request applied; a value that is not given keeps the footprint's."""
    name = request.name
    if all(field.name != name for field in instance.fields):
        raise FormatError(
            f"footprint {instance.lib_ref} has no field {name!r} to place",
            locator=f"{instance.lib_ref}:{name}",
        )
    bottom = instance.side == "bottom"
    if request.layer is not None:
        layer = ("B." if bottom else "F.") + FIELD_LAYERS[request.layer]
        instance = set_field(instance, name, layer=layer, mirrored=bottom)
    anchor = None
    if request.dx is not None and request.dy is not None:
        anchor = Point(instance.position.x + request.dx, instance.position.y + request.dy)
    instance = set_field(
        instance,
        name,
        anchor=anchor,
        angle=request.rotation,
        visible=request.visible,
        size=Size(request.size, request.size) if request.size is not None else None,
        thickness=request.thickness,
        justify=_justify(request.justify) if request.justify is not None else None,
    )
    if request.outside is not None:
        gap = DEFAULT_GAP if request.gap is None else request.gap
        instance = place_outside(instance, name, side=cast(OutsideSide, request.outside), gap=gap)
    return instance


def apply_requests(instance: FootprintInstance, requests: Sequence[FieldRequestLike]) -> FootprintInstance:
    """``instance`` with every request of its part applied, in name order.

    A request for a field that the footprint does not hold raises ``FormatError`` (``FEN-3004``) naming the
    footprint's lib id and the field, as a malformed library input.
    """
    for request in sorted(requests, key=lambda r: r.name):
        instance = apply_request(instance, request)
    return instance


FIELD_VALUES: tuple[str, ...] = (
    "position",
    "rotation",
    "layer",
    "size",
    "thickness",
    "visible",
    "h_justify",
    "v_justify",
    "mirrored",
)
"""What a field carries from the board to a re-placed footprint: placement and appearance, never the id,
the uuid or the slot list."""


@dataclass(frozen=True)
class FieldMerge:
    """The layout with its fields decided, and what happened, as sorted ``"<component path>:<field name>"``.

    ``kept``: an unlocked request differs from the board's field, which wins. ``forced``: a locked request
    changed a board field. ``carried``: a field of a re-placed footprint took the board's values.
    """

    design: Design
    kept: tuple[str, ...] = ()
    forced: tuple[str, ...] = ()
    carried: tuple[str, ...] = ()

    @property
    def summary(self) -> dict[str, list[str]]:
        """``result.preserved.fields``."""
        return {"kept": list(self.kept), "forced": list(self.forced), "carried": list(self.carried)}


def _values(field: FootprintField) -> tuple[object, ...]:
    return tuple(getattr(field, name) for name in FIELD_VALUES)


def _named(instance: FootprintInstance, name: str) -> FootprintField | None:
    return next((f for f in instance.fields if f.name == name), None)


def _user_names(instance: FootprintInstance) -> set[str]:
    """The names of the script's user properties: the fields after ``fenolite.path``."""
    names = [f.name for f in instance.fields]
    return set(names[names.index(PATH_PROPERTY) + 1 :]) if PATH_PROPERTY in names else set()


def _changes(instance: FootprintInstance, request: FieldRequestLike) -> FootprintInstance | None:
    """``instance`` with ``request`` applied, or ``None`` when the request changes nothing or names a field
    that the footprint does not hold."""
    before = _named(instance, request.name)
    if before is None:
        return None
    applied = apply_request(instance, request)
    after = _named(applied, request.name)
    assert after is not None
    return applied if _values(after) != _values(before) else None


def merge_fields(
    merged: Merged,
    board: Design,
    match: LayoutMatch,
    requests: Mapping[str, Sequence[FieldRequestLike]],
) -> FieldMerge:
    """The merged layout with every field of a matched part decided (``docs/lens.md``, "Footprint fields").

    - A **kept** footprint keeps the board's fields; only locked requests are applied to it.
    - A **re-placed** footprint with the board footprint's lib id and side takes the board's values for
      every field both have, unless a locked request names the field. Fields are footprint-relative, so the
      copy is exact.
    - Every other footprint keeps the built copy's fields: the library's, with every request applied.

    Pure: nothing but fields changes, and a second run over its own result changes nothing.
    """
    design = merged.design
    if design.board is None:
        return FieldMerge(design)
    kept_paths = set(cast(Sequence[str], merged.summary.get("kept", ())))
    replaced_paths = set(cast(Sequence[str], merged.summary.get("replaced", ())))
    components = component_paths(design)
    current = {fp.component_id: fp for fp in design.board.footprints}
    kept: list[str] = []
    forced: list[str] = []
    carried: list[str] = []
    changed: dict[str, FootprintInstance] = {}
    for path, found in match.matches.items():
        component = components.get(path)
        instance = current.get(component.id) if component is not None else None
        if component is None or instance is None:
            continue
        wanted = sorted(requests.get(path, ()), key=lambda r: r.name)
        original = instance
        if path in kept_paths:
            for request in wanted:
                applied = _changes(instance, request)
                if applied is None:
                    continue
                if request.locked:
                    instance = applied
                    forced.append(f"{path}:{request.name}")
                else:
                    kept.append(f"{path}:{request.name}")
        elif path in replaced_paths:
            theirs = found.footprint
            if instance.lib_ref != theirs.lib_ref or instance.side != theirs.side:
                continue
            locked = {r.name for r in wanted if r.locked}
            user = _user_names(instance)
            fields: list[FootprintField] = []
            for field in instance.fields:
                old = _named(theirs, field.name)
                if old is None:
                    fields.append(field)
                elif field.name in locked:
                    if _values(field) != _values(old):
                        forced.append(f"{path}:{field.name}")
                    fields.append(field)
                else:
                    taken = dataclasses.replace(field, **dict(zip(FIELD_VALUES, _values(old), strict=True)))  # type: ignore[arg-type]
                    if _values(taken) != _values(field) and field.name not in user:
                        carried.append(f"{path}:{field.name}")
                    fields.append(taken)
            if tuple(fields) != instance.fields:
                instance = dataclasses.replace(instance, fields=tuple(fields))
            for request in wanted:
                if not request.locked and _named(theirs, request.name) is not None:
                    if _changes(instance, request) is not None:
                        kept.append(f"{path}:{request.name}")
        if instance is not original:
            changed[original.component_id] = instance
    if changed:
        footprints = tuple(changed.get(fp.component_id, fp) for fp in design.board.footprints)
        design = dataclasses.replace(design, board=dataclasses.replace(design.board, footprints=footprints))
    return FieldMerge(design, tuple(sorted(kept)), tuple(sorted(forced)), tuple(sorted(carried)))


__all__ = [
    "FIELD_LAYERS",
    "FIELD_VALUES",
    "FieldMerge",
    "FieldRequestLike",
    "apply_request",
    "apply_requests",
    "merge_fields",
]
