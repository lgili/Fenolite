# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The 3D models a PCB document embeds for its component bodies (capability altium-import, "Embedded body
models"; ``docs/formats/altium/pcb-bodies.md``, "Embedded models and their placement"; change c0193).

``Models/Data`` is a run of records, each a 32-bit length and a property text; record ``n`` names the stream
``Models/<n>``, which holds the model inflated by ``zlib``. A body with ``MODEL.MODELTYPE=1`` names a record
by ``MODELID``. Its placement is ``MODEL.2D.X`` and ``MODEL.2D.Y`` (a point of the document: Y negated, as the
units module turns every point), ``MODEL.3D.DZ`` and ``MODEL.3D.ROTX``, ``ROTY`` and ``ROTZ``; the rotation
keys of the ``Models/Data`` record are not applied (``H-A-BODY-MODEL-PLACE``). Nothing is written.
"""

from __future__ import annotations

import struct
import zlib
from fractions import Fraction
from pathlib import Path

from fenolite.backends.altium.adapter.board import BODY_STORAGE
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.units import UDEG, round_half_even, text_length
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprops import parse_text
from fenolite.backends.base import BodyModel
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Udeg

EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-BODY-MODEL-PLACE",))
"""The records, the streams and the placement, measured on the eight public PCB documents of the corpus
(``pcb-bodies.md``, "Embedded models and their placement")."""
MODELS = "Models"
STEP = "step"


def model_records(data: bytes) -> tuple[dict[str, str], ...]:
    """The property records of ``Models/Data``, in stream order; a record cut short ends the run."""
    out: list[dict[str, str]] = []
    at = 0
    while at + 4 <= len(data):
        (size,) = struct.unpack_from("<I", data, at)
        body = data[at + 4 : at + 4 + size]
        if len(body) < size:
            break
        out.append(dict(parse_text(body.rstrip(b"\x00"))))
        at += 4 + size
    return tuple(out)


def _length(text: str) -> int:
    found = text_length(text) if text else None
    return 0 if found is None else found[0]


def _udeg(text: str) -> Udeg:
    try:
        value = Fraction(text.strip() or "0")
    except (ValueError, ZeroDivisionError):
        return 0
    return round_half_even(value * UDEG)


def body_models(path: Path, *, issues: list[Issue] | None = None) -> tuple[BodyModel, ...]:
    """The embedded model of every component body of the PCB document at ``path`` that names one, in body
    order. A record whose stream is missing or does not inflate is skipped with
    ``altium.import.model-unread``."""
    doc = read_pcbdoc(path.read_bytes(), file=path.name)
    storage = doc.storages.get(MODELS, {})
    bodies = doc.storages.get(BODY_STORAGE, {}).get("Data")
    if not storage or not bodies:
        return ()
    records = model_records(storage.get("Data", b""))
    index = {record.get("ID", ""): k for k, record in enumerate(records)}
    inflated: dict[int, bytes | None] = {}
    out: list[BodyModel] = []
    for record in read_bodies(bodies, storage=BODY_STORAGE):
        if not record.framed or record.component is None:
            continue
        props = record.properties
        if props.text("MODEL.MODELTYPE") != "1" or props.text("MODELID") not in index:
            continue
        k = index[props.text("MODELID")]
        if k not in inflated:
            try:
                inflated[k] = zlib.decompress(storage[str(k)])
            except (KeyError, zlib.error):
                inflated[k] = None
                if issues is not None:
                    issues.append(
                        issue(
                            "altium.import.model-unread",
                            "an embedded 3D model is missing or does not inflate; its body keeps no model",
                            f"{MODELS}/{k}",
                        )
                    )
        data = inflated[k]
        if data is None:
            continue
        out.append(
            BodyModel(
                locator=f"{BODY_STORAGE}/Data#{record.index}",
                name=records[k].get("NAME", "") or props.text("MODEL.NAME"),
                format=STEP,
                data=data,
                position=Point(_length(props.text("MODEL.2D.X")), -_length(props.text("MODEL.2D.Y"))),
                z=_length(props.text("MODEL.3D.DZ")),
                rotation=(
                    _udeg(props.text("MODEL.3D.ROTX")),
                    _udeg(props.text("MODEL.3D.ROTY")),
                    _udeg(props.text("MODEL.3D.ROTZ")),
                ),
            )
        )
    return tuple(out)


__all__ = ["EVIDENCE", "MODELS", "STEP", "body_models", "model_records"]
