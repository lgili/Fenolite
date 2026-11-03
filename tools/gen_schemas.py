# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generate JSON Schema (draft 2020-12) files from Fenolite dataclasses.

    uv run python tools/gen_schemas.py          # (re)write schemas/
    uv run python tools/gen_schemas.py --check  # exit 1 if any schema file would change

Supported annotations: bool, int, float, str, None, Any, Literal, X | None, list[T], tuple[T, ...],
dict[str, T], Enum subclasses and nested dataclasses. Field metadata keys ``pattern``,
``minimum``, ``enum`` and ``description`` are copied into the property schema.
"""

from __future__ import annotations

import argparse
import collections.abc
import dataclasses
import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
import types
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DRAFT = "https://json-schema.org/draft/2020-12/schema"
FROZEN = "schemas/frozen-v0.json"


def _formats_module() -> Any:
    name = "_fenolite_schema_formats"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools/schema_formats.py")
        if spec is None or spec.loader is None:
            raise ValueError("cannot load the explicit format inventory")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def format_readme() -> str:
    from fenolite.cli.results import RESULTS, schema_id

    formats = _formats_module()
    rows = formats.inventory(ROOT)
    result_rows = [
        f"| `{name}` | `{schema_id(name, 'v0')}` | `{schema_id(name, 'v1')}` | "
        f"`{cls.__module__}:{cls.__name__}` |"
        for name, cls in sorted(RESULTS.items())
    ]
    return (
        "# Schemas\n\n"
        "Generated from wire dataclasses by `tools/gen_schemas.py`; do not edit schema files by hand.\n"
        "The active CLI contract remains v0 until the 1.0 release. New result IDs have a `result`\n"
        "namespace because command names also occur in persisted model/document IDs. Per-command\n"
        "filenames remain `fenolite.<command>.<version>.json`. Existing v0 files retain their bytes.\n\n"
        "Published result objects allow additions. Tests close declared object structures while\n"
        "retaining documented, typed data maps. Four legacy v0 result files retain their original\n"
        "closed form. Public standalone formats live under `formats/`; canonical model layers\n"
        "remain under their model-version directory. Internal formats carry no release promise.\n\n"
        "## Command results\n\n"
        "| Command | v0 ID | Prepared v1 ID | Wire class |\n|---|---|---|---|\n"
        + "\n".join(result_rows)
        + "\n\n## Source format inventory\n\n"
        "Decided 2026-11-01: retain the public inputs and agent-readable outputs below. Viewer\n"
        "transport, kit forms, protected merge bases and disposable caches remain internal.\n"
        "Legacy device/family dialects retain their existing v0/v1 dispatch. The model activation\n"
        "and canonical-folder migration belong to c0218. Frozen model-v0 bytes come from the\n"
        "final model-0 source recorded in `frozen-model-v0.json`; prepared CLI-v0 targets are\n"
        "tracked separately in `frozen-v0.json` while the active CLI writer remains v0.\n\n"
        + formats.markdown(rows)
        + "\n## Test and evidence format inventory\n\n"
        "Decided 2026-11-02: these IDs occur outside the production source scanner. They describe\n"
        "internal test/evidence artifacts, with no public schema or reader promise. Their v0 suffix\n"
        "and any observed `model_schema` are independent of canonical migration; recorded bytes\n"
        "and measured native limitations remain unchanged.\n\n"
        + formats.markdown(formats.TEST_EVIDENCE_FORMATS)
        + "\nBounded internal diagnostic child markers are not schema IDs or canonical model versions:\n\n"
        + "\n".join(
            f"- `{marker}` from `{path}`: test diagnostics only; no public reader/schema promise."
            for marker, path in formats.TEST_DIAGNOSTIC_MARKERS.items()
        )
        + "\n"
    )


def contract_table() -> str:
    from fenolite.cli.results import RESULTS, schema_id

    rows = [
        f"| `{name}` | [`v0`](../schemas/fenolite.{name}.v0.json) | "
        f"[`v1`](../schemas/fenolite.{name}.v1.json) | `{schema_id(name, 'v1')}` |"
        for name in sorted(RESULTS)
    ]
    return (
        "<!-- BEGIN RESULT SCHEMAS -->\n"
        "## Result schema files\n\n"
        "Each visible command has a generated result descriptor. Its envelope label still comes from\n"
        "the active CLI contract. Newly prepared result document IDs use `fenolite.result.<command>.v1`\n"
        "to distinguish persisted documents with the same name. The four previously published v0 result\n"
        "files retain their IDs and bytes. The `migrate` descriptor is prepared for c0218.\n\n"
        "Published result structures accept additive keys. Fenolite's tests close declared structures\n"
        "and retain typed maps indexed by user data. Nullable fields and branch-specific optional fields\n"
        "describe existing replies; no result payload changes here. `--fields` projections are outside\n"
        "these complete-result schemas. Public file format declarations and the explicit internal/public\n"
        "inventory are in [`schemas/README.md`](../schemas/README.md). Readers retain semantic validation\n"
        "of ranges, references, provenance and hashes in addition to JSON Schema types.\n\n"
        "| Command | v0 file | Prepared v1 file | Prepared result ID |\n|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n<!-- END RESULT SCHEMAS -->\n"
    )


def contract_text() -> str:
    path = ROOT / "docs/cli-contract.md"
    before = path.read_text(encoding="utf-8")
    start, end = "<!-- BEGIN RESULT SCHEMAS -->", "<!-- END RESULT SCHEMAS -->"
    if start not in before:
        return before.rstrip() + "\n\n" + contract_table()
    prefix, _, tail = before.partition(start)
    _, marker, suffix = tail.partition(end)
    if not marker:
        raise ValueError("result schema documentation has no end marker")
    return prefix + contract_table().rstrip("\n") + suffix


@dataclass(frozen=True)
class Target:
    schema_id: str
    ref: str  # "module:ClassName"
    out: str  # path relative to ROOT
    all_required: bool  # wire formats: every field always present
    envelope_version: str | None = None
    published_open: bool = False
    optional_metadata: bool = False
    unique_defs: bool = False
    canonical_models: bool = False
    strict_tuples: bool = False
    document_schema: bool = False


def _format_targets() -> list[Target]:
    formats = _formats_module()
    seen = formats.inventory(ROOT)
    ids = {
        schema_id[:-1] + "1"
        if schema_id.endswith(".v0") and schema_id not in {"fenolite.device.v0", "fenolite.family.v0"}
        else schema_id
        for schema_id in seen
        if schema_id in formats.FORMATS and formats.FORMATS[schema_id].owner == "formats"
    }
    return [
        Target(
            schema_id,
            formats.FORMATS[schema_id].reference,
            f"schemas/formats/{schema_id}.json",
            False,
            optional_metadata=True,
            unique_defs=True,
            canonical_models=True,
            strict_tuples=True,
            document_schema=True,
        )
        for schema_id in sorted(ids)
    ]


def _model_targets() -> list[Target]:
    from fenolite.model.schema import (
        LAYER_SCHEMAS,
        LIBRARY_SCHEMA,
        PANEL_SCHEMA,
        SCHEMA_DIR,
        SCHEMATIC_SCHEMA,
        SHEET_SCHEMA,
    )

    layers = [Target(sid, ref, f"{SCHEMA_DIR}/{name}", False) for name, (sid, ref) in LAYER_SCHEMAS.items()]
    definitions = [
        Target(sid, ref, f"{SCHEMA_DIR}/{name}", False)
        for name, sid, ref in (LIBRARY_SCHEMA, SHEET_SCHEMA, SCHEMATIC_SCHEMA, PANEL_SCHEMA)
    ]
    return [*layers, *definitions]


def _targets() -> list[Target]:
    from fenolite.cli.api import CONTRACT_VERSION
    from fenolite.cli.results import LEGACY, RESULTS, schema_id

    wire = [
        Target(
            "fenolite.envelope.v0", "fenolite.cli.output:Envelope", "schemas/fenolite.envelope.v0.json", True
        ),
        Target("fenolite.error.v0", "fenolite.cli.errors:ErrorInfo", "schemas/fenolite.error.v0.json", True),
        Target(
            "fenolite.envelope.v1",
            "fenolite.cli.output:Envelope",
            "schemas/fenolite.envelope.v1.json",
            True,
            envelope_version="v1",
        ),
        Target("fenolite.error.v1", "fenolite.cli.errors:ErrorInfo", "schemas/fenolite.error.v1.json", True),
        Target(
            "fenolite.artifacts.v0",
            "fenolite.exports.manifest:Manifest",
            "schemas/fenolite.artifacts.v0.json",
            True,
        ),
        Target(
            "fenolite.equivalent.v0",
            "fenolite.api.schema:EquivalentReply",
            "schemas/fenolite.equivalent.v0.json",
            True,
        ),
        Target(
            "fenolite.convert.v0",
            "fenolite.api.schema:ConvertReply",
            "schemas/fenolite.convert.v0.json",
            True,
        ),
        Target(
            "fenolite.verify-source.v0",
            "fenolite.api.schema:VerifySourceReply",
            "schemas/fenolite.verify-source.v0.json",
            True,
        ),
        Target(
            "fenolite.import.v0",
            "fenolite.importer.schema:ImportReply",
            "schemas/fenolite.import.v0.json",
            True,
        ),
    ]
    results = [
        Target(
            schema_id(name, version),
            f"{cls.__module__}:{cls.__name__}",
            f"schemas/fenolite.{name}.{version}.json",
            True,
            published_open=True,
            optional_metadata=True,
            unique_defs=True,
            canonical_models=True,
            strict_tuples=True,
        )
        for name, cls in sorted(RESULTS.items())
        for version in sorted({CONTRACT_VERSION, "v1"})
        if version != "v0" or name not in LEGACY
    ]
    targets = [
        *wire,
        *results,
        *_model_targets(),
        *_format_targets(),
        Target(
            "fenolite.placement-request.v0",
            "fenolite.placement.constraints:PlacementRequest",
            "schemas/fenolite.placement-request.v0.json",
            False,
        ),
        Target(
            "fenolite.review.v0", "fenolite.view.review:ReviewFile", "schemas/fenolite.review.v0.json", False
        ),
    ]
    # Once activated, old schemas are immutable snapshots, never renderings of live classes.
    return targets if CONTRACT_VERSION == "v0" else [t for t in targets if not t.schema_id.endswith(".v0")]


TARGETS: list[Target] = _targets()


class SchemaBuilder:
    def __init__(
        self,
        *,
        all_required: bool,
        published_open: bool = False,
        optional_metadata: bool = False,
        unique_defs: bool = False,
        canonical_models: bool = False,
        strict_tuples: bool = False,
    ) -> None:
        self.all_required = all_required
        self.published_open = published_open
        self.optional_metadata = optional_metadata
        self.unique_defs = unique_defs
        self.canonical_models = canonical_models
        self.strict_tuples = strict_tuples
        self.names: dict[type, str] = {}
        self.defs: dict[str, dict[str, Any]] = {}

    def root(self, cls: type, schema_id: str) -> dict[str, Any]:
        body = self.object_schema(cls)
        schema: dict[str, Any] = {"$schema": DRAFT, "$id": schema_id, "title": cls.__name__, **body}
        if self.defs:
            schema["$defs"] = {name: self.defs[name] for name in sorted(self.defs)}
        return schema

    def object_schema(self, cls: type) -> dict[str, Any]:
        hints = typing.get_type_hints(cls)
        properties: dict[str, Any] = {}
        required: list[str] = []
        for f in dataclasses.fields(cls):
            prop = self.type_schema(hints[f.name])
            _apply_metadata(prop, dict(f.metadata))
            # ``name`` is the key on the wire when it is a Python keyword (``from_`` is written ``from``)
            key = str(f.metadata.get("name", f.name))
            properties[key] = prop
            no_default = f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            # a wire field added after v0 was published is marked ``optional``: old documents stay valid
            optional = self.optional_metadata and f.metadata.get("optional")
            require_wire = self.all_required and not (
                self.canonical_models and cls.__module__.startswith("fenolite.model.")
            )
            if not optional and (no_default or (require_wire and not f.metadata.get("optional"))):
                required.append(key)
        schema: dict[str, Any] = {}
        doc = (cls.__doc__ or "").strip().splitlines()
        if doc and not doc[0].startswith(cls.__name__ + "("):
            schema["description"] = doc[0]
        schema.update(
            {"type": "object", "properties": properties, "additionalProperties": self.published_open}
        )
        if required:
            schema["required"] = required
        return schema

    def type_schema(self, tp: Any) -> dict[str, Any]:
        origin = typing.get_origin(tp)
        args = typing.get_args(tp)
        if tp is Any or tp is object:
            return {}
        if tp is type(None):
            return {"type": "null"}
        if tp is bool:
            return {"type": "boolean"}
        if tp is int:
            return {"type": "integer"}
        if tp is float:
            return {"type": "number"}
        if tp is str:
            return {"type": "string"}
        if origin is typing.Literal:
            return {"enum": list(args)}
        if origin in (typing.Union, types.UnionType):
            return {"anyOf": [self.type_schema(a) for a in args]}
        if origin in (list, collections.abc.Sequence):
            return {"type": "array", "items": self.type_schema(args[0])}
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return {"type": "array", "items": self.type_schema(args[0])}
            schema: dict[str, Any] = {
                "type": "array",
                "prefixItems": [self.type_schema(a) for a in args],
                "items": False,
            }
            if self.strict_tuples:
                schema.update({"minItems": len(args), "maxItems": len(args)})
            return schema
        if origin in (dict, collections.abc.Mapping):
            value = self.type_schema(args[1])
            if self.published_open:
                return {
                    "type": "object",
                    "additionalProperties": value or True,
                    "x-fenolite-map": True,
                }
            return {"type": "object"} if value == {} else {"type": "object", "additionalProperties": value}
        if isinstance(tp, type) and issubclass(tp, Enum):
            return {"enum": [member.value for member in tp]}
        if isinstance(tp, type) and dataclasses.is_dataclass(tp):
            name = tp.__name__
            if self.unique_defs:
                if tp not in self.names:
                    suffix = 1
                    while name in self.names.values():
                        suffix += 1
                        name = f"{tp.__name__}{suffix}"
                    self.names[tp] = name
                name = self.names[tp]
            if name not in self.defs:
                self.defs[name] = {}
                self.defs[name] = self.object_schema(tp)
            return {"$ref": f"#/$defs/{name}"}
        raise TypeError(f"unsupported annotation {tp!r}")


def _apply_metadata(prop: dict[str, Any], metadata: dict[str, Any]) -> None:
    extra = {
        k: metadata[k] for k in ("pattern", "minimum", "enum", "description", "minItems") if k in metadata
    }
    if not extra:
        return
    if "anyOf" in prop:
        for option in prop["anyOf"]:
            if option.get("type") in ("string", "integer", "number"):
                option.update(extra)
    else:
        prop.update(extra)


def _load(ref: str) -> type:
    module_name, _, attr = ref.partition(":")
    return getattr(importlib.import_module(module_name), attr)


def render(target: Target) -> str:
    builder = SchemaBuilder(
        all_required=target.all_required,
        published_open=target.published_open,
        optional_metadata=target.optional_metadata,
        unique_defs=target.unique_defs,
        canonical_models=target.canonical_models,
        strict_tuples=target.strict_tuples,
    )
    schema = builder.root(_load(target.ref), target.schema_id)
    if target.envelope_version is not None:
        schema["properties"]["schema"]["pattern"] = (
            rf"^fenolite\.[a-z_][a-z0-9_-]*\.{target.envelope_version}$"
        )
    if target.document_schema:
        schema["properties"]["schema"] = {"const": target.schema_id}
        schema["required"] = list(dict.fromkeys(["schema", *schema.get("required", [])]))
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def frozen_v0() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "schemas").rglob("*.json"))
        if ".v0." in path.name or path.parent.name.endswith(".v0")
    }


def frozen_problems() -> list[str]:
    from fenolite.cli.api import CONTRACT_VERSION

    path = ROOT / FROZEN
    if not path.exists():
        return [] if CONTRACT_VERSION == "v0" else [f"missing frozen schema receipt: {FROZEN}"]
    expected = json.loads(path.read_text(encoding="utf-8"))
    current = frozen_v0()
    return [
        f"frozen schema changed or missing: {name}"
        for name, digest in expected.items()
        if current.get(name) != digest
    ] + [f"unrecorded v0 schema: {name}" for name in sorted(current.keys() - expected.keys())]


def compatibility_problems() -> list[str]:
    """Compare v1 declarations with the last reachable stable release, without modifying Git."""
    from fenolite import __version__
    from fenolite.cli.results.compatibility import schema_changes

    spec = importlib.util.spec_from_file_location(
        "_fenolite_release_surface", ROOT / "tools/gen_cli_surface.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("cannot load release-tag selection")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tag = module.release_tag(__version__, root=ROOT)
    if tag is None:
        return []
    listed = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", tag, "schemas/"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    old = {name for name in listed if name.endswith(".v1.json") or ".v1/" in name}
    targets = {
        target.out: target for target in TARGETS if target.out.endswith(".v1.json") or ".v1/" in target.out
    }
    problems = [f"removed schema: {name}" for name in sorted(old - targets.keys())]
    for name in sorted(old & targets.keys()):
        data = subprocess.run(
            ["git", "show", f"{tag}:{name}"], cwd=ROOT, text=True, capture_output=True, check=True
        ).stdout
        target = targets[name]
        for change in schema_changes(
            json.loads(data),
            json.loads(render(target)),
            name=target.schema_id,
            input_mode="/formats/" in name,
        ):
            problems.append(f"{change.kind}: {change.path}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(__doc__ or "Generate Fenolite JSON schemas.").splitlines()[0]
    )
    parser.add_argument("--check", action="store_true", help="fail if any schema file would change")
    parser.add_argument(
        "--formats", action="store_true", help="list concrete source IDs and their classifications"
    )
    parser.add_argument(
        "--freeze-v0", action="store_true", help="record reviewed last-v0 schema hashes before activation"
    )
    args = parser.parse_args(argv)
    if args.freeze_v0:
        from fenolite.cli.api import CONTRACT_VERSION

        if args.check or args.formats or CONTRACT_VERSION != "v0":
            parser.error("--freeze-v0 is a standalone pre-activation operation")
        (ROOT / FROZEN).write_text(json.dumps(frozen_v0(), indent=2) + "\n", encoding="utf-8")
        return 0
    if args.formats:
        formats = _formats_module()
        rows = formats.inventory(ROOT)
        if args.check:
            missing = sorted(set(rows) - set(formats.FORMATS))
            if missing:
                print("unclassified formats: " + ", ".join(missing), file=sys.stderr)
                return 1
        for schema_id, paths in rows.items():
            decision = formats.FORMATS.get(schema_id)
            kind = "unclassified" if decision is None else decision.classification
            print(f"{schema_id}\t{kind}\t{', '.join(paths)}")
        if args.check and format_readme() != (ROOT / "schemas/README.md").read_text(encoding="utf-8"):
            print("format inventory differs from schemas/README.md", file=sys.stderr)
            return 1
        return 0
    stale: list[str] = []
    for target in TARGETS:
        text = render(target)
        path = ROOT / target.out
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        if args.check:
            stale.append(target.out)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            print(f"wrote {target.out}")
    readme = ROOT / "schemas/README.md"
    text = format_readme()
    if readme.read_text(encoding="utf-8") != text:
        if args.check:
            stale.append("schemas/README.md")
        else:
            readme.write_text(text, encoding="utf-8")
            print("wrote schemas/README.md")
    contract = ROOT / "docs/cli-contract.md"
    text = contract_text()
    if contract.read_text(encoding="utf-8") != text:
        if args.check:
            stale.append("docs/cli-contract.md")
        else:
            contract.write_text(text, encoding="utf-8")
            print("wrote docs/cli-contract.md")
    if stale:
        print("stale schemas (run tools/gen_schemas.py):\n  " + "\n  ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        problems = frozen_problems() + compatibility_problems()
        if problems:
            print("incompatible schemas:\n  " + "\n  ".join(problems), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
