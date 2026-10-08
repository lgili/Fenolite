# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A simulated kit run for the tests: Fenolite's own writers stand in for Altium's saves.

Every result file is a file that Fenolite wrote (the kit's own document, or a rebuild of a sample with one
edit of its model), and the form is marked ``synthetic``, so no label can come from such a run
(``record.refusal``). ``synthetic=False`` exists only for the tests of the record's form: what it gives is
never committed. Nothing here is a file that a tool saved.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path

from fenolite.cli._kit import (
    SAMPLES_DIR,
    build_sample,
    copper_problems,
    judge_document,
    poured_problems,
    read_document,
)
from fenolite.model.board import ZoneFill
from fenolite.model.design import Design
from fenolite.verify.kit.manifest import FORM_FILE, load_kit
from fenolite.verify.kit.script import DONE, END_OF_MESSAGES, LOG

VERSION = "AD 26.5"
"""A tool version of the right form; no run was made with it."""
DATE = "2026-10-06"


def poured(model: Design) -> Design:
    """``model`` with every zone filled by its own outline: what "Repour All" is taken to leave."""
    assert model.board is not None
    zones = tuple(
        dataclasses.replace(
            zone,
            filled=True,
            fills=tuple(ZoneFill(layer=layer, polygon=zone.outline) for layer in zone.layers),
        )
        for zone in model.board.zones
    )
    return dataclasses.replace(model, board=dataclasses.replace(model.board, zones=zones))


def simulated_judge(check: str, own: Path, saved: Path) -> list[str]:
    """``judge_document``, but for the checks ``poured`` and ``copper.clearance`` of a re-saved board.
    Fenolite's writers write every polygon unpoured,
    so no file of theirs can stand in for a repoured board: the stand-in is the kit's own board, and this
    check runs on its import with the zones filled in the model. Every other check is the product's."""
    if check == "poured":
        design = read_document(saved)
        assert isinstance(design, Design)
        assert poured_problems(design) == ["1 of 1 polygon(s) hold no poured copper"]
        return poured_problems(poured(design))
    if check == "copper.clearance" and saved.suffix.casefold() == ".pcbdoc":
        assert any("without poured copper" in text for text in copper_problems(saved, repoured=True))
        return copper_problems(saved, repoured=False)
    return judge_document(check, own, saved)


def without_net(name: str):  # noqa: ANN201
    """An edit that removes the net ``name`` from a model."""

    def edit(model: Design) -> Design:
        nets = tuple(net for net in model.circuit.nets if net.name != name)
        assert len(nets) == len(model.circuit.nets) - 1
        return dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, nets=nets))

    return edit


@cache
def rebuilt(sample: str, edit: object = None) -> Mapping[str, bytes]:
    """The files of ``sample`` rebuilt with ``edit`` applied to its model."""
    return build_sample(SAMPLES_DIR / sample / "design.py", edit=edit).files  # type: ignore[arg-type]


def simulate(
    folder: Path,
    *,
    synthetic: bool = True,
    script: bool = False,
    replace: Mapping[str, bytes] | None = None,
    skip: tuple[str, ...] = (),
) -> None:
    """Fill ``results/`` of the kit in ``folder`` as a complete run would. ``script`` writes the files of
    the scripted steps in the script's form, with ``script.log``; ``replace`` gives other bytes for a
    result path; ``skip`` leaves steps undone."""
    kit = load_kit(folder)
    values: dict[str, object] = {}
    log: list[str] = []
    for step in kit.steps:
        if step.id in skip:
            if step.kind == "form":
                values[step.result] = None
            continue
        if step.kind == "form":
            values[step.result] = step.expected
            continue
        if "messages" in step.checks:
            scripted = script and step.scripted
            data = (
                f"[Info] compiled (Compiler)\n{END_OF_MESSAGES}\n" if scripted else "no messages\n"
            ).encode()
            if scripted:
                log.append(f"{step.id} {DONE}")
        elif "listing" in step.checks:
            data = b"routed.GTL\nrouted.GBL\nrouted.TXT\nrouted.pdf\n"
        elif step.result.endswith(".html"):
            data = b"<html><body>Design Rule Verification Report (simulated)</body></html>\n"
        else:
            data = (folder / step.document).read_bytes()
        data = (replace or {}).get(step.result, data)
        target = folder / "results" / step.result
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if log:
        (folder / LOG).write_text("".join(f"{line}\n" for line in log), encoding="utf-8", newline="\n")
    form = {
        "schema": kit.data["form"]["schema"],
        "altium_version": VERSION,
        "os_family": "Windows",
        "date": DATE,
        "synthetic": synthetic,
        "values": values,
    }
    (folder / FORM_FILE).write_text(json.dumps(form, indent=2) + "\n", encoding="utf-8", newline="\n")
