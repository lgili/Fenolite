# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of an Altium output job for the viewer page (capability documentation-view, change c0190).

``outjob_scene(path)`` reads a ``.OutJob`` with ``read.outjob`` and returns a table scene (``kind``
``"table"``): one row per output, with its group, name, type, category, the document it binds, its variant,
whether it is enabled and the containers it goes to. Each container's output folder is shown as the job
writes it: ``OutputBasePath<j>``, the media and outputer path tokens and ``OutputFileName<j>`` of
``[PublishSettings]``, which holds them for every container ``j`` whatever its type
(``docs/formats/altium/output-job.md``, ``H-A-RD-PRJ-OUTJOB``, INFERRED). The absolute
``RelativeOutputPath<j>`` of ``[GeneratedFilesSettings]`` (where the job last wrote, on its author's machine)
is not shown. Tokens such as ``[Media Name]`` stay as written: the viewer does not run the job. A row's
``docs`` names the project document it binds, which the page opens (``[bom]`` for the project's BOM
document). Standard library only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends.altium.read.ini import IniDocument
from fenolite.backends.altium.read.outjob import OutputMedium, read_outjob

SCHEMA = "fenolite.view_table.v0"
COLUMNS = ("Group", "Output", "Type", "Category", "Document", "Variant", "Enabled", "Containers")
SETTINGS = "PublishSettings"
"""The section that holds the path keys of every container."""
BOM_DOCUMENT = "[ActiveBOM Document]"
"""What an output binds for the project's BOM document; the page opens the project's ``.BomDoc``."""


def folder(ini: IniDocument, medium: OutputMedium) -> str:
    """Where container ``medium`` writes, as the job spells it: base path, media and outputer tokens, and file
    name; ``""`` when the job holds none of them."""
    section = ini.section(SETTINGS)
    if section is None:
        return ""
    j = medium.index
    parts = [
        section.get(f"OutputBasePath{j}") or "",
        section.get(f"OutputPathMedia{j}") or "",
        section.get(f"OutputPathOutputer{j}") or "",
    ]
    path = "".join(p if p.endswith("\\") or not p else p + "\\" for p in parts if p)
    name = section.get(f"OutputFileName{j}") or ""
    return (path + name).strip("\\") if path or name else ""


def outjob_scene(path: Path) -> dict[str, Any]:
    """The table scene of the output job at ``path`` (module docstring)."""
    data = path.read_bytes()
    job = read_outjob(data, file=path.name)
    rows: list[list[str]] = []
    docs: list[list[str]] = []
    for group in job.groups:
        media = {m.index: m for m in group.media}
        for output in group.outputs:
            shown: list[str] = []
            for index in output.enabled_media:
                medium = media.get(index)
                if medium is not None:
                    where = folder(job.ini, medium)
                    shown.append(f"{medium.name} ({medium.type})" + (f" → {where}" if where else ""))
            rows.append(
                [
                    group.name,
                    output.name,
                    output.type,
                    output.category,
                    output.document_path,
                    output.variant_name or group.variant_name,
                    "yes" if output.enabled else "no",
                    "; ".join(shown),
                ]
            )
            bound = output.document_path
            docs.append(
                ["[bom]"] if bound == BOM_DOCUMENT else [bound] if bound and not bound.startswith("[") else []
            )
    notes = [
        "Output folders are shown as the job writes them, path tokens included; "
        "Fenolite does not run the job."
    ]
    notes += [issue.message for issue in job.issues]
    return {
        "schema": SCHEMA,
        "kind": "table",
        "table": "outjob",
        "meta": {
            "name": path.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "backend": "altium",
            "evidence": "INFERRED",
            "counts": {"outputs": len(rows), "groups": len(job.groups)},
            "notes": notes,
        },
        "title": f"Output job {path.stem}",
        "columns": list(COLUMNS),
        "rows": rows,
        "docs": docs,
        "refs": [[] for _ in rows],
    }


__all__ = ["COLUMNS", "SCHEMA", "folder", "outjob_scene"]
