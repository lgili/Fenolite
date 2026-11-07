# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Render docs/evidence/matrix.md from the evidence declarations of the backends and the register.

    uv run python tools/gen_evidence_matrix.py [--check]

``--check`` writes nothing and exits 1 when the committed page differs from a fresh rendering. The page
is a function of the working tree only: no date, no tool version and no absolute path (capability
verification-evidence, "Generated evidence matrix page"; change c0067).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fenolite.backends import matrix  # noqa: E402
from fenolite.backends.base import MATRIX_OPERATIONS, GraduationRun, MatrixRow, graduated  # noqa: E402
from fenolite.core.errors import FormatError  # noqa: E402
from fenolite.core.evidence import Evidence  # noqa: E402
from fenolite.verify import HypothesisRow, load_register  # noqa: E402
from fenolite.verify.graduation import readback_tests, run_snapshots  # noqa: E402
from fenolite.verify.kit.manifest import Kit  # noqa: E402

PAGE = ROOT / "docs" / "evidence" / "matrix.md"
REGISTER = ROOT / "docs" / "hypotheses.md"
PAGE_NAME = "docs/evidence/matrix.md"
CONFORMANCE_JSON = ROOT / "docs/evidence/conformance.json"
CONFORMANCE_PAGE = ROOT / "docs/evidence/conformance.md"
TOOL_NAME = "tools/gen_evidence_matrix.py"
COMMAND = f"uv run python {TOOL_NAME}"
NOT_SET = "—"
MEANINGS = (
    ("detect", "the package names the kind of a file from its name or its content"),
    ("read", "a reader of the package builds a model object from a file of the kind"),
    (
        "write",
        "a writer of the package produces a file of the kind from a model object that Fenolite created",
    ),
    (
        "roundtrip_exact",
        "a file of the kind that is read and written back for the same version, with no change in between, "
        "keeps its whole content, modelled or not",
    ),
    (
        "roundtrip_modified",
        "a file of the kind that is read, changed through the model and written keeps everything the "
        "change did not touch, or the write is refused",
    ),
)


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _line(cells: Sequence[str]) -> str:
    return "| " + " | ".join(_cell(cell) for cell in cells) + " |"


def _operation(row: MatrixRow, operation: str) -> str:
    cell: Evidence | None = getattr(row, operation)
    if cell is None:
        return NOT_SET
    return cell.label() + (" (experimental)" if operation in row.experimental else "")


def _ids(idents: Sequence[str]) -> str:
    return ", ".join(f"`{ident}`" for ident in idents) or NOT_SET


def source_problems(
    rows: Sequence[MatrixRow],
    *,
    repository: Path = ROOT,
    register: Sequence[HypothesisRow] | None = None,
    records: Sequence[Mapping[str, Any]] | None = None,
    kit: Kit | None = None,
) -> list[str]:
    """Validate scope sources without executing tests or an external application.

    Native kit scopes need actual passing, non-synthetic records and a fresh labelled hypothesis.
    With no supplied kit, the normal CLI builder computes the current authored kit in memory.
    """
    from fenolite.verify.kit.record import KIT_LABEL, RUN_ID, kit_label, load_records

    found: list[str] = []
    kit_scopes = []
    root = repository.resolve()
    for row in rows:
        where = f"{row.backend}/{row.kind}"
        found.extend(f"{where}: {problem}" for problem in row.version_problems())
        for operation, cell in row.cells():
            for scope in row.versions.get(operation, ()):
                label = f"{where}/{operation}: source {scope.source!r}"
                source = PurePosixPath(scope.source)
                if scope.source.startswith("tests/"):
                    safe = (
                        not any(part in ("..", ".") for part in source.parts)
                        and "\\" not in scope.source
                        and ":" not in scope.source
                    )
                    path = (root / source).resolve()
                    if (
                        not safe
                        or not path.is_relative_to(root)
                        or not path.is_file()
                        or not path.name.startswith("test_")
                        or path.suffix != ".py"
                    ):
                        found.append(label + " is not an existing repository test file")
                elif RUN_ID.fullmatch(scope.source):
                    kit_scopes.append((row, operation, cell, scope, label))
                else:
                    found.append(label + " names neither a repository test nor a recorded kit run")
    if not kit_scopes:
        return found
    if register is None:
        register = load_register(root / "docs/hypotheses.md")
    if records is None:
        records = load_records(root)
    by_record = {str(record["run_id"]): record for record in records}
    by_id = {row.id: row for row in register}
    candidates = []
    for _row, _operation, cell, scope, label in kit_scopes:
        record = by_record.get(scope.source)
        if record is None:
            found.append(label + " has no validated recorded run")
            continue
        if (
            record["synthetic"]
            or record["altium_version"] != scope.version
            or scope.tool != "Altium Designer " + scope.version.removeprefix("AD ")
        ):
            found.append(label + " disagrees with the native version or is synthetic")
            continue
        supporting = [
            by_id[h]
            for h in cell.hypotheses
            if h in by_id
            and KIT_LABEL.fullmatch(by_id[h].level_text)
            and by_id[h].level_text == kit_label(record)
            and not by_id[h].refuted
        ]
        if not supporting:
            found.append(label + " has no matching current kit-labelled hypothesis")
            continue
        candidates.append((scope, label, supporting))
    if candidates:
        if kit is None:
            from fenolite.cli._kit import kit_sources
            from fenolite.verify.kit.manifest import KIT_FILE, kit_files, read_kit

            kit = read_kit(kit_files(kit_sources())[KIT_FILE])
        runs = {run.run_id: run for run in run_snapshots(register, records, kit, committed=True)}
        for scope, label, supporting in candidates:
            run = runs[scope.source]
            if (
                not run.committed
                or run.stale_hypotheses is None
                or any(h.id not in run.passed_hypotheses or h.id in run.stale_hypotheses for h in supporting)
            ):
                found.append(label + " has no current passing native observation for its hypotheses")
    return found


def conformance_data(rows: Sequence[MatrixRow]) -> dict[str, Any]:
    snapshot = matrix.conformance(rows)
    return {"schema": snapshot.schema, "rows": [dataclasses.asdict(row) for row in snapshot.rows]}


def render_conformance_json(rows: Sequence[MatrixRow]) -> str:
    return json.dumps(conformance_data(rows), indent=2, ensure_ascii=False) + "\n"


def render_conformance(rows: Sequence[MatrixRow]) -> str:
    entries = conformance_data(rows)["rows"]
    lines = [
        "# Conformance by format version",
        "",
        f"Generated by `{TOOL_NAME}`. Do not edit by hand.",
        "",
        "These declarations preserve the operation's existing evidence level and name its test or recorded",
        "kit scope. They do not claim a new run on this commit or promote partial kit observations to a",
        "general file-format guarantee. A missing version means no version-specific claim",
        "(INFERRED or lower).",
        "",
        "The JSON form is [conformance.json](conformance.json); generic operation labels and hypotheses are",
        "in [matrix.md](matrix.md). Exact-head CI and unperformed native acceptance remain separate gates.",
    ]
    for backend in sorted({row.backend for row in rows}):
        lines += [
            "",
            f"## {backend}",
            "",
            _line(["kind", "operation", "version", "tool", "level", "source"]),
            "|---|---|---|---|---|---|",
        ]
        for entry in entries:
            if entry["backend"] == backend:
                lines.append(
                    _line(
                        [
                            str(entry[name]) if entry[name] is not None else NOT_SET
                            for name in ("kind", "operation", "version", "tool", "level", "source")
                        ]
                    )
                )
    return "\n".join(lines) + "\n"


def render(
    rows: Sequence[MatrixRow] | None = None,
    claims: Sequence[matrix.ModuleClaim] | None = None,
    register: Sequence[HypothesisRow] | None = None,
    *,
    runs: Sequence[GraduationRun] | None = None,
    own_readbacks: Mapping[str, str] | None = None,
    suite_tests: Collection[str] | None = None,
) -> str:
    """The page text. With no argument it is rendered from the working tree: ``matrix.rows()``, the
    ``module_claims`` of every backend package and ``docs/hypotheses.md``."""
    if rows is None:
        rows = matrix.rows()
    if claims is None:
        claims = [claim for package in matrix.packages() for claim in matrix.module_claims(package)]
    if register is None:
        register = load_register(REGISTER)
    by_id = {row.id: row for row in register}
    lines = [
        "# Evidence matrix",
        "",
        f"Generated by `{TOOL_NAME}` from the evidence declarations of the modules under",
        "`src/fenolite/backends/` (`fenolite.backends.matrix`) and from `docs/hypotheses.md`. Do not edit by",
        f"hand: change a declaration or a register row and run `{COMMAND}`.",
        "`tests/unit/test_evidence_matrix_page.py` fails while this page is stale. `fenolite capabilities`",
        "lists the same rows as `result.matrix`.",
        "Version scopes and their sources are published in [conformance.md](conformance.md) and",
        "[conformance.json](conformance.json); a scope preserves the existing operation label.",
        "",
        "## Operations",
        "",
        "A row states what one backend package does with one file kind, and how well each operation is",
        "verified. A label states what holds for an arbitrary file of the kind, so it is often weaker than",
        "the rows it names: a row of the register states what its test covered. A label is never stronger",
        "than a row it names (lowest wins).",
        "",
        "| operation | meaning |",
        "|---|---|",
        *(_line([f"`{name}`", meaning]) for name, meaning in MEANINGS),
        "",
        f"`{NOT_SET}` means that the package does not implement the operation for the kind. `(experimental)`",
        "marks an operation that may change its output, its options or its issue codes in any release.",
        "",
        "## Matrix",
        "",
        _line(["backend", "kind", *MATRIX_OPERATIONS, "verified_by"]),
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        cells = [_operation(row, operation) for operation in MATRIX_OPERATIONS]
        lines.append(_line([row.backend, f"`{row.kind}`", *cells, _ids(row.verified_by())]))
    altium_writes = [row for row in rows if row.backend == "altium" and row.write is not None]
    if altium_writes:
        if own_readbacks is None:
            from fenolite.backends.altium.claims import OWN_READBACK

            own_readbacks = OWN_READBACK
        if suite_tests is None:
            suite_tests = readback_tests(ROOT, own_readbacks)
        if runs is None:
            from fenolite.cli._kit import kit_sources
            from fenolite.verify.kit.manifest import KIT_FILE, kit_files, read_kit
            from fenolite.verify.kit.record import load_records

            current_kit = read_kit(kit_files(kit_sources())[KIT_FILE])
            runs = run_snapshots(register, load_records(ROOT), current_kit, committed=True)
        lines += [
            "",
            "## Write graduation",
            "",
            "Altium write graduation requires a declared own-readback test in the suite, release-verified",
            "hypotheses, RT-A3 for model kinds, and a passing committed kit hypothesis whose files match",
            "the current kit. These diagnostics use the committed run records; they do not promote a kind",
            "or substitute for passing CI. Other backends retain their existing release policy.",
            "",
            "| kind | missing graduation conditions |",
            "|---|---|",
        ]
        for row in altium_writes:
            passed, reasons = graduated(
                row,
                by_id,
                runs,
                own_readback=own_readbacks.get(row.kind),
                suite_tests=suite_tests,
            )
            lines.append(_line([f"`{row.kind}`", "none" if passed else "<br>".join(reasons)]))
    named = sorted({ident for row in rows for ident in row.verified_by()})
    lines += [
        "",
        "## Hypotheses",
        "",
        "The level that `docs/hypotheses.md` holds for each id a row names, as written there. The statement,",
        "the settling test and the result of an id are in its register row.",
        "",
        "| id | level in the register |",
        "|---|---|",
    ]
    for ident in named:
        found = by_id.get(ident)
        level = (
            "not registered" if found is None else found.level_text + (" (refuted)" if found.refuted else "")
        )
        lines.append(_line([f"`{ident}`", level]))
    lines += [
        "",
        "## Modules",
        "",
        "Every module of a backend package declares its evidence in one of three forms: constants (it owns",
        "a claim), `see` (its code runs only inside the operations of the named modules of the package), or",
        "`none` with a reason (it states nothing about a file format or a tool).",
    ]
    for package in sorted({claim.package for claim in claims}):
        lines += ["", f"### `{package}`", "", "| module | declaration |", "|---|---|"]
        for claim in sorted((c for c in claims if c.package == package), key=lambda c: c.module):
            if claim.constants:
                parts = [
                    f"`{name}` {evidence.label()}: {_ids(evidence.hypotheses)}"
                    for name, evidence in claim.constants
                ]
                declared = "<br>".join(parts)
            elif claim.see:
                declared = "see " + ", ".join(f"`{name}`" for name in claim.see)
            else:
                declared = f"none: {claim.none}"
            lines.append(_line([f"`{claim.module}`", declared]))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the evidence and versioned conformance matrices.")
    parser.add_argument("--check", action="store_true", help="exit 1 when the committed page is out of date")
    parser.add_argument(
        "--page", type=Path, default=None, help="render/check only a custom legacy matrix page"
    )
    args = parser.parse_args(argv)
    rows = matrix.rows()
    try:
        problems = source_problems(rows)
    except (FormatError, ValueError, OSError) as exc:
        problems = [str(exc)]
    if problems:
        print("invalid conformance sources:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    outputs = {args.page or PAGE: render(rows)}
    if args.page is None:
        outputs[CONFORMANCE_JSON] = render_conformance_json(rows)
        outputs[CONFORMANCE_PAGE] = render_conformance(rows)
    stale = []
    for path, text in outputs.items():
        current = path.read_bytes().decode("utf-8") if path.is_file() else ""
        if current != text:
            if args.check:
                stale.append(PAGE_NAME if args.page is not None else str(path.relative_to(ROOT)))
            else:
                path.write_bytes(text.encode("utf-8"))
    if stale:
        print(f"out of date: {', '.join(stale)}; run '{COMMAND}' and commit the pages", file=sys.stderr)
    return int(bool(stale))


if __name__ == "__main__":
    raise SystemExit(main())
