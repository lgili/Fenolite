# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Same-tool regeneration evidence, isolated from pure equivalence (c0340)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, cast

from fenolite.api.sides import ReadSide
from fenolite.backends.kicad import _json, dru, pro
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.derived_teardrops import (
    Tree,
    crossing_counts,
    native_net,
    qualifies,
    regions,
    without_regions,
)
from fenolite.backends.kicad.lowering import MINIMUM_KEYS
from fenolite.backends.kicad.sexpr import AtomKind, Node, dumps, parse_bytes
from fenolite.checks.assignment_compare import board_netlist, net_names
from fenolite.checks.equivalence.model import Difference
from fenolite.cli.errors import CliError
from fenolite.model.design import Design


@dataclass(frozen=True)
class CacheInput:
    name: str
    files: Mapping[str, bytes]
    bindings: Mapping[str, tuple[str, ...]]
    project: pro.JsonObject


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bindings(design: Design) -> dict[str, tuple[str, ...]]:
    netlist, _ = board_netlist(design)
    members: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, str] = {}
    for assignment in netlist.assignments:
        if assignment.element in seen:
            if seen[assignment.element] != assignment.net:
                raise ValueError("ambiguous numbered-pad binding")
            continue
        seen[assignment.element] = assignment.net
        members[assignment.net].append(assignment.element)
    names = net_names(design)
    result: dict[str, tuple[str, ...]] = {}
    for net, elements in members.items():
        name = names.get(net)
        if name is None:
            continue
        if name in result:
            raise ValueError("ambiguous native net name")
        result[name] = tuple(sorted(elements))
    return result


def _raw_bindings(root: Node, expected: frozenset[tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """Bind raw native net tokens by exact numbered-pad partitions, never spelling substitutions."""
    members: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, str] = {}
    seen_refs: set[str] = set()
    for footprint in root.nodes("footprint"):
        references = [
            p.atoms()[1].value
            for p in footprint.nodes("property")
            if len(p.atoms()) >= 2 and p.atoms()[0].value == "Reference"
        ]
        references += [
            p.atoms()[1].value
            for p in footprint.nodes("fp_text")
            if len(p.atoms()) >= 2 and p.atoms()[0].value == "reference"
        ]
        if len(references) != 1 or not references[0]:
            raise ValueError("native footprint has no unique reference")
        if references[0] in seen_refs:
            raise ValueError("native footprint reference ambiguous")
        seen_refs.add(references[0])
        for pad in footprint.nodes("pad"):
            atoms = pad.atoms()
            if not atoms or atoms[0].kind != AtomKind.STRING:
                raise ValueError("native pad number malformed")
            if not atoms[0].value or not pad.nodes("net"):
                continue
            net = native_net(pad, root)
            if not net:
                continue
            element = references[0] + "-" + atoms[0].value
            if element in seen:
                if seen[element] != net:
                    raise ValueError("native numbered-pad identity ambiguous")
                continue
            seen[element] = net
            members[net].append(element)
    result = {name: tuple(sorted(elements)) for name, elements in members.items()}
    if frozenset(result.values()) != expected:
        raise ValueError("native named-pad partitions changed")
    return result


def inputs(side: ReadSide) -> CacheInput | None:
    """Only already-traced project/board bytes; rule sidecar reads are explicit and receipted too."""
    boards = [(p, sha) for p, sha in side.source_files if p.suffix.lower() == ".kicad_pcb"]
    projects = [(p, sha) for p, sha in side.source_files if p.suffix.lower() == ".kicad_pro"]
    if len(boards) != 1 or len(projects) != 1:
        return None
    board, _ = boards[0]
    files: dict[str, bytes] = {}
    for path, digest in (*boards, *projects):
        data = path.read_bytes()
        if _hash(data) != digest:
            raise CliError(
                "FEN-4002",
                f"{path.name} changed during cache proof",
                where=path.name,
                hint="review the inputs and run the proof again",
            )
        name = board.name if path == board else board.with_suffix(".kicad_pro").name
        files[name] = data
    rules = board.with_suffix(".kicad_dru")
    if rules.is_file():
        files[rules.name] = rules.read_bytes()
        dru.parse_rules(files[rules.name].decode("utf-8"), file=rules.name)
    project = pro.read_project_text(files[board.with_suffix(".kicad_pro").name].decode("utf-8"))
    bindings = _raw_bindings(parse_bytes(files[board.name]), frozenset(_bindings(side.design).values()))
    return CacheInput(board.name, files, bindings, project)


def _json_key(value: Any) -> object:
    if isinstance(value, _json.JsonNumber):
        number = Fraction(value.text)
        return ("number", number.numerator, number.denominator)
    if isinstance(value, dict):
        return tuple((k, _json_key(v)) for k, v in sorted(cast(dict[str, Any], value).items()))
    if isinstance(value, list):
        return tuple(_json_key(v) for v in cast(list[Any], value))
    return value


def _settings(data: pro.JsonObject) -> dict[str, Any]:
    board = data.get("board")
    settings = cast(dict[str, Any], board).get("design_settings") if isinstance(board, dict) else None
    if not isinstance(settings, dict):
        raise ValueError("native project design settings missing")
    return cast(dict[str, Any], settings)


def _teardrop_configuration(settings: dict[str, Any]) -> None:
    """Only the observed template's closed option/parameter shapes qualify, never silent defaults."""
    reference = _settings(pro.template(10))
    for key in ("teardrop_options", "teardrop_parameters"):
        rows = settings.get(key)
        expected = cast(list[dict[str, Any]], reference[key])
        if not isinstance(rows, list):
            raise ValueError(f"malformed native {key}")
        known_rows = cast(list[Any], rows)
        if len(known_rows) != len(expected):
            raise ValueError(f"malformed native {key}")
        targets: set[str] = set()
        for row, known in zip(known_rows, expected, strict=True):
            if not isinstance(row, dict) or set(cast(dict[str, Any], row)) != set(known):
                raise ValueError(f"unknown/missing native {key} fields")
            current = cast(dict[str, Any], row)
            for name, default in known.items():
                value = current[name]
                if isinstance(default, bool):
                    if type(value) is not bool:
                        raise ValueError(f"malformed native {name}")
                elif isinstance(default, _json.JsonNumber):
                    if not isinstance(value, _json.JsonNumber) or Fraction(value.text) < 0:
                        raise ValueError(f"malformed native {name}")
                    number = Fraction(value.text)
                    if name == "td_curve_segcount" and number.denominator != 1:
                        raise ValueError("fractional native curve segment count")
                    if name in {"td_maxheight", "td_maxlen"} and (number * 1_000_000).denominator != 1:
                        raise ValueError("inexact native teardrop length")
                elif isinstance(default, str):
                    if (
                        not isinstance(value, str)
                        or value not in {r[name] for r in expected}
                        or value in targets
                    ):
                        raise ValueError("unknown or duplicate native teardrop target")
                    targets.add(value)
                else:
                    raise ValueError("unrecognized native teardrop configuration")


def configuration(a: CacheInput, b: CacheInput) -> dict[str, object]:
    """Judge supported settings exactly; list all other native project setting deltas as unjudged."""
    sa, sb = _settings(a.project), _settings(b.project)
    _teardrop_configuration(sa)
    _teardrop_configuration(sb)
    for key in ("teardrop_options", "teardrop_parameters"):
        if key not in sa or key not in sb or _json_key(sa[key]) != _json_key(sb[key]):
            raise ValueError(f"native project {key} missing or different")
    rules_a, rules_b = sa.get("rules"), sb.get("rules")
    if not isinstance(rules_a, dict) or not isinstance(rules_b, dict):
        raise ValueError("native project rules missing")
    rules_a, rules_b = cast(dict[str, Any], rules_a), cast(dict[str, Any], rules_b)
    keys = tuple(MINIMUM_KEYS[10].values())
    for key in keys:
        va, vb = rules_a.get(key), rules_b.get(key)
        if not isinstance(va, _json.JsonNumber) or not isinstance(vb, _json.JsonNumber):
            raise ValueError(f"native supported rule {key} missing/malformed")
        if min(Fraction(va.text), Fraction(vb.text)) < 0 or any(
            (Fraction(value.text) * 1_000_000).denominator != 1 for value in (va, vb)
        ):
            raise ValueError(f"native supported rule {key} is negative/inexact")
        if _json_key(va) != _json_key(vb):
            raise ValueError(f"native supported rule {key} differs")
    if pro.project_curve_error(a.project) != pro.project_curve_error(b.project):
        raise ValueError("native max_error differs")
    unjudged_rules = [
        {"key": key, "a": _json_key(rules_a.get(key)), "b": _json_key(rules_b.get(key))}
        for key in sorted(rules_a.keys() | rules_b.keys())
        if key not in {*keys, "max_error"} and _json_key(rules_a.get(key)) != _json_key(rules_b.get(key))
    ]
    unjudged_settings = [
        {
            "key": key,
            "a_canonical_sha256": _hash(repr(_json_key(sa.get(key))).encode()),
            "b_canonical_sha256": _hash(repr(_json_key(sb.get(key))).encode()),
        }
        for key in sorted(sa.keys() | sb.keys())
        if key not in {"rules", "teardrop_options", "teardrop_parameters"}
        and _json_key(sa.get(key)) != _json_key(sb.get(key))
    ]
    return {
        "judged_project_keys": [*keys, "max_error", "teardrop_options", "teardrop_parameters"],
        "unjudged_project_rule_deltas": unjudged_rules,
        "unjudged_project_setting_deltas": unjudged_settings,
        "whole_project_json_equality_claimed": False,
        "whole_native_rule_file_equality_claimed": False,
    }


def eligible(a: CacheInput, b: CacheInput) -> bool:
    """Both inputs and numbered-pad partitions must qualify before native execution."""
    try:
        configuration(a, b)
        ra, rb = parse_bytes(a.files[a.name]), parse_bytes(b.files[b.name])
        ca, cb = regions(ra, a.bindings), regions(rb, b.bindings)
        if not ca and not cb:
            return False
        if set(a.bindings.values()) != set(b.bindings.values()):
            return False
        return qualifies(ra, allow_empty=bool(cb)) and qualifies(rb, allow_empty=bool(ca))
    except ValueError:
        return False


def prove(a: CacheInput, b: CacheInput, tool: KicadCli) -> tuple[dict[str, object], tuple[Difference, ...]]:
    """Regenerate isolated exact bytes twice, never replace editable models with native saved boards."""
    if tool.major() != 10:
        raise CliError(
            "FEN-6002",
            "derived padvia cache proof requires KiCad 10",
            hint="use KiCad 10 for pcb drc --refill-zones --save-board",
        )
    summary: dict[str, object] = {
        **configuration(a, b),
        "tool": "kicad-cli",
        "version": tool.version(),
        "raw_cache_equality_claimed": False,
        "drc_safety_gate_claimed": False,
    }
    evidence: dict[str, dict[str, Any]] = {}
    normalized: list[tuple[Tree, ...]] = []
    for label, source in (("a", a), ("b", b)):
        raw = regions(parse_bytes(source.files[source.name]), source.bindings)
        argv = [
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--refill-zones",
            "--save-board",
            "-o",
            "derived-drc.json",
            source.name,
        ]
        stripped = dumps(without_regions(parse_bytes(source.files[source.name]))).encode("utf-8")
        native_files = {**source.files, source.name: stripped}
        run = tool.run(argv, files=native_files)
        saved = run.outputs.get(source.name)
        evidence[label] = {
            "raw_caches": len(raw),
            "raw_non_simple_rings": crossing_counts(parse_bytes(source.files[source.name])),
            "native_input_sha256": _hash(stripped),
            "qualified_caches_removed_from_private_input": True,
            "input_files": {name: _hash(data) for name, data in source.files.items()},
            "command": argv,
            "exit": run.returncode,
            "outcome": run.outcome,
            "stdout_sha256": _hash(run.stdout.encode()),
            "stderr_sha256": _hash(run.stderr.encode()),
            "output_sha256": _hash(saved) if saved is not None else None,
        }
        summary["sides"] = evidence
        if not run.ok or saved is None:
            summary["status"] = "native-failed"
            return summary, (
                Difference(
                    7,
                    "zone-field",
                    "board:derived:padvia",
                    "native_regeneration",
                    "successful native regeneration",
                    label + ":failed",
                ),
            )
        # Native must not have changed any supplied editable project/rule input on its private copy.
        if any(
            name in run.outputs and run.outputs[name] != data
            for name, data in source.files.items()
            if name != source.name
        ):
            summary["status"] = "native-config-changed"
            return summary, (
                Difference(
                    7,
                    "zone-field",
                    "board:derived:padvia",
                    "native_configuration",
                    "unchanged native inputs",
                    label + ":changed",
                ),
            )
        try:
            root = parse_bytes(saved)
            bindings = _raw_bindings(root, frozenset(source.bindings.values()))
            result = regions(root, bindings)
            if not qualifies(root):
                raise ValueError("regenerated cache parent does not qualify")
        except ValueError:
            summary["status"] = "native-cache-unqualified"
            return summary, (
                Difference(
                    7,
                    "zone-field",
                    "board:derived:padvia",
                    "native_regeneration",
                    "qualified native caches",
                    label + ":unqualified",
                ),
            )
        normalized.append(result)
        row = evidence[label]
        assert isinstance(row, dict)
        row["regenerated_caches"] = len(result)
        row["native_non_simple_rings"] = crossing_counts(root)
        row["exact_geometry_sha256"] = _hash(repr(result).encode())
    equal = normalized[0] == normalized[1]
    summary["status"] = "equal" if equal else "differs"
    summary["complete_regenerated_geometry_equal"] = equal
    summary["normal_zone_priorities_normalized"] = False
    differences = (
        ()
        if equal
        else (
            Difference(
                7,
                "zone-field",
                "board:derived:padvia",
                "regenerated_geometry",
                _hash(repr(normalized[0]).encode()),
                _hash(repr(normalized[1]).encode()),
            ),
        )
    )
    return summary, differences
