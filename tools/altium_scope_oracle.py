# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit step of change c0462, task 5.1 (S-2214): Altium's PCB filter counts, per object kind, the objects
each distinct mapped rule scope of the 8 public Altium rows selects.

    uv run python tools/altium_scope_oracle.py plan --out DIR
    uv run python tools/altium_scope_oracle.py record --results DIR --altium VERSION \
        --out tests/data/altium/kit/scope-oracle-c0462.json

``plan`` reads the cached public rows (``FENOLITE_CORPUS_CACHE``, else ``~/.cache/fenolite/corpus``), and for
each row writes ``DIR/<PcbDoc file name>.scopes.txt``, one line ``<n> <scope>`` per distinct scope that
``parse_scope`` maps with the row's ``ScopeDocument``, and ``DIR/scope_oracle.pas``, the DelphiScript of the
step. In Altium, with the row's PcbDoc open and focused and its ``.scopes.txt`` beside it, File » Run Script »
``FenoliteScopeOracle`` writes ``<PcbDoc file name>.counts.txt`` beside the document. ``record`` reads the
``.counts.txt`` files of ``--results`` into the oracle JSON.

For each scope the script clears every selection itself (``Selected``), runs the server process
``PCB:RunQuery`` with ``Expr``, ``Select`` and ``Apply``, and counts the selected objects of each kind: a
``board`` line per kind the board iterator returns, and a ``child`` line per kind of the children of each
polygon and component that a group iterator returns, since no public page says whether the board iterator
returns them. A scope that holds ``|``, which separates the parameters of a process, is written ``skipped``.

Every routine, method and constant of the script is in ``SCRIPT_CALLS`` with the public source that names
it (``docs/evidence/sources.md``). The parameters of ``PCB:RunQuery`` come from a page that could not be
read whole (S-2216, ``UNVERIFIED``): the first run says whether they hold. Nothing in Fenolite starts Altium
or this script. The output holds row ids, file digests, the scope texts of the public rows and counts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tomllib
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
ROW = re.compile(r"altium-third-party-pcbdoc-0[1-8]")
PROCEDURE = "FenoliteScopeOracle"
SCRIPT = "scope_oracle.pas"
SCOPES = ".scopes.txt"
COUNTS = ".counts.txt"
SCHEMA = "fenolite.altium-scope-oracle.v1"

KINDS: Mapping[str, str] = MappingProxyType(
    {
        "eArcObject": "arc",
        "ePadObject": "pad",
        "eViaObject": "via",
        "eTrackObject": "track",
        "eTextObject": "text",
        "eFillObject": "fill",
        "eComponentObject": "component",
        "ePolyObject": "polygon",
        "eRegionObject": "region",
    }
)
"""The ``TObjectId`` constants the script counts (S-2215, PCB API Types) → the kind written in the counts."""
GROUPS = ("ePolyObject", "eComponentObject")
"""The kinds whose children a group iterator returns (S-2215, ``GroupIterator_Create``)."""

SCRIPT_CALLS: Mapping[str, str] = MappingProxyType(
    {
        "PCBServer": "S-2215",
        "GetCurrentPCBBoard": "S-2215",
        "FileName": "S-2215",
        "BoardIterator_Create": "S-2215",
        "BoardIterator_Destroy": "S-2215",
        "AddFilter_ObjectSet": "S-2215",
        "AddFilter_LayerSet": "S-2215",
        "AddFilter_Method": "S-2215",
        "eProcessAll": "S-2215",
        "AllLayers": "S-2215",
        "MkSet": "S-2215",
        "FirstPCBObject": "S-2215",
        "NextPCBObject": "S-2215",
        "GroupIterator_Create": "S-2215",
        "GroupIterator_Destroy": "S-2215",
        "ObjectId": "S-2215",
        "Selected": "S-2215",
        **dict.fromkeys(KINDS, "S-2215"),
        "ResetParameters": "S-0506",
        "AddStringParameter": "S-0506",
        "RunProcess": "S-0506",
        "AssignFile": "S-0501",
        "Reset": "S-0501",
        "Rewrite": "S-0501",
        "Readln": "S-0501",
        "Writeln": "S-0501",
        "Eof": "S-0501",
        "CloseFile": "S-0501",
        "Pos": "S-0501",
        "Copy": "S-0501",
        "Length": "S-0501",
        "Trim": "S-0501",
        "FloatToStr": "S-0501",
    }
)
"""Every routine, method, property and constant of the script → the public source that names it."""
PROCESS = "PCB:RunQuery"
PROCESS_PARAMETERS = ("Expr", "Select", "Apply")
"""The process and the parameters the script passes (S-2216, ``UNVERIFIED``)."""


def default_cache() -> Path:
    override = os.environ.get("FENOLITE_CORPUS_CACHE")
    return Path(override) if override else Path.home() / ".cache" / "fenolite" / "corpus"


def public_rows(cache: Path, manifest: Path = MANIFEST) -> list[tuple[str, str, Path]]:
    """``(row id, sha256, cached path)`` of the 8 public PcbDoc rows; ``SystemExit`` if one is not cached."""
    found: list[tuple[str, str, Path]] = []
    for row in tomllib.loads(manifest.read_text(encoding="utf-8")).get("file", []):
        if not ROW.fullmatch(row["id"]):
            continue
        name = urllib.parse.unquote(Path(str(urllib.parse.urlparse(str(row["url"])).path)).name)
        path = cache / row["id"] / name
        if not path.is_file():
            raise SystemExit(f"{row['id']} is not cached: run the corpus fetch with FENOLITE_HEAVY=1")
        found.append((row["id"], row["sha256"], path))
    return sorted(found)


def mapped_scopes(data: bytes, name: str) -> list[str]:
    """The distinct rule scopes of a PcbDoc that ``parse_scope`` maps with its ``ScopeDocument``, sorted."""
    from fenolite.backends.altium.adapter.layers import copper_layers_of
    from fenolite.backends.altium.pour import read_pour
    from fenolite.backends.altium.read.scope import for_kind, parse_scope
    from fenolite.backends.altium.read.scopedoc import scope_document

    reading = read_pour(data, file=name)
    board = reading.design.board
    document = scope_document(reading.document, None if board is None else copper_layers_of(board.layers))
    found: set[str] = set()
    for rule in reading.document.rules:
        fields = {key: value or "" for key, value in rule.record.fields}
        for key in ("SCOPE1EXPRESSION", "SCOPE2EXPRESSION"):
            text = fields.get(key, "").strip()
            if not text or text == "All":
                continue
            if not isinstance(parse_scope(text, document=for_kind(document, fields.get("RULEKIND"))), str):
                found.add(text)
    return sorted(found)


def fenolite_counts(data: bytes, name: str, scopes: Sequence[str]) -> list[dict[str, int]]:
    """Per scope, the number of objects of each kind that Fenolite's selector selects: the tracks, arcs,
    vias and pads of the computed pour's object table (an object on several layers counts once, when one of
    its layers' subjects matches) and the polygons by their copper's subject. The other half of the
    comparison with the kit's counts."""
    from fenolite.backends.altium.adapter.layers import copper_layers_of
    from fenolite.backends.altium.pour import (
        LayerObjects,
        object_subject,
        polygons_of,
        read_pour,
        rule_subject,
    )
    from fenolite.backends.altium.read.scope import parse_scope
    from fenolite.backends.altium.read.scopedoc import scope_document
    from fenolite.model.rules import Selector

    reading = read_pour(data, file=name)
    board = reading.design.board
    document = scope_document(reading.document, None if board is None else copper_layers_of(board.layers))
    everything = replace(document, parents=frozenset({"component", "polygon", "pair"}))
    """The filter selects parent objects too; for a function that returns a component or a pair alone the
    selector's ``ref`` or ``net`` leaves select its children, so the comparison counts its parents."""
    objects = LayerObjects(reading, 1)
    subjects: dict[tuple[str, str], list[object]] = {}
    for layer, items in objects.by_layer.items():
        for item in items:
            if item.kind in ("track", "arc", "via", "pad"):
                subjects.setdefault((item.kind, item.entity_id), []).append(object_subject(layer, item))
    for polygon in polygons_of(reading):
        netclass = objects.netclass.get(polygon.net, objects.netclass[None])
        subject = rule_subject(polygon.layer, "zone", polygon.net, netclass, zone=polygon.name or None)
        subjects.setdefault(("polygon", str(polygon.index)), []).append(subject)
    found: list[dict[str, int]] = []
    for scope in scopes:
        selector = parse_scope(scope, document=everything)
        if not isinstance(selector, Selector):
            raise ValueError(f"{name}: {scope!r} no longer maps: {selector}")
        counts: dict[str, int] = {}
        for (kind, _), each in sorted(subjects.items()):
            if any(selector.matches(s) for s in each):  # type: ignore[arg-type]
                counts[kind] = counts.get(kind, 0) + 1
        found.append(counts)
    return found


def scope_lines(scopes: Sequence[str]) -> str:
    return "".join(f"{n} {scope}\n" for n, scope in enumerate(scopes, 1))


def script_text() -> str:
    """The DelphiScript of the step; every name it calls is in ``SCRIPT_CALLS``."""
    kinds = ", ".join(KINDS)
    names = "\n".join(f"  If Id = {constant} Then Result := '{kind}';" for constant, kind in KINDS.items())
    groups = " Or ".join(f"(Parent.ObjectId = {kind})" for kind in GROUPS)
    return f"""{{ Fenolite, change c0462 task 5.1: Altium's PCB filter counts per object kind for each
  scope of <document>.scopes.txt, written to <document>.counts.txt.
  Generated by tools/altium_scope_oracle.py. }}

Function KindName(Id) : String;
Begin
  Result := 'other';
{names}
End;

Procedure ClearAll(Board);
Var Iterator, Item, Children, Child;
Begin
  Iterator := Board.BoardIterator_Create;
  Iterator.AddFilter_ObjectSet(MkSet({kinds}));
  Iterator.AddFilter_LayerSet(AllLayers);
  Iterator.AddFilter_Method(eProcessAll);
  Item := Iterator.FirstPCBObject;
  While Item <> Nil Do
  Begin
    Item.Selected := False;
    Item := Iterator.NextPCBObject;
  End;
  Board.BoardIterator_Destroy(Iterator);
End;

Procedure CountKind(Board, Kind, Key, OutFile);
Var Iterator, Item, Count;
Begin
  Count := 0;
  Iterator := Board.BoardIterator_Create;
  Iterator.AddFilter_ObjectSet(MkSet(Kind));
  Iterator.AddFilter_LayerSet(AllLayers);
  Iterator.AddFilter_Method(eProcessAll);
  Item := Iterator.FirstPCBObject;
  While Item <> Nil Do
  Begin
    If Item.Selected Then Count := Count + 1;
    Item := Iterator.NextPCBObject;
  End;
  Board.BoardIterator_Destroy(Iterator);
  Writeln(OutFile, Key + ' board ' + KindName(Kind) + ' ' + FloatToStr(Count));
End;

Procedure CountChildren(Board, Key, OutFile, Clear);
Var Iterator, Parent, Children, Child;
Begin
  Iterator := Board.BoardIterator_Create;
  Iterator.AddFilter_ObjectSet(MkSet({", ".join(GROUPS)}));
  Iterator.AddFilter_LayerSet(AllLayers);
  Iterator.AddFilter_Method(eProcessAll);
  Parent := Iterator.FirstPCBObject;
  While Parent <> Nil Do
  Begin
    If {groups} Then
    Begin
      Children := Parent.GroupIterator_Create;
      Children.AddFilter_ObjectSet(MkSet({kinds}));
      Child := Children.FirstPCBObject;
      While Child <> Nil Do
      Begin
        If Clear Then Child.Selected := False
        Else If Child.Selected Then
          Writeln(OutFile, Key + ' child ' + KindName(Parent.ObjectId) + ' '
            + KindName(Child.ObjectId) + ' 1');
        Child := Children.NextPCBObject;
      End;
      Parent.GroupIterator_Destroy(Children);
    End;
    Parent := Iterator.NextPCBObject;
  End;
  Board.BoardIterator_Destroy(Iterator);
End;

Procedure {PROCEDURE};
Var Board, InFile, OutFile, Line, Space, Key, Expr;
Begin
  Board := PCBServer.GetCurrentPCBBoard;
  If Board = Nil Then Exit;
  AssignFile(InFile, Board.FileName + '{SCOPES}');
  Reset(InFile);
  AssignFile(OutFile, Board.FileName + '{COUNTS}');
  Rewrite(OutFile);
  Try
    While Not Eof(InFile) Do
    Begin
      Readln(InFile, Line);
      Line := Trim(Line);
      Space := Pos(' ', Line);
      If Space > 1 Then
      Begin
        Key := Copy(Line, 1, Space - 1);
        Expr := Copy(Line, Space + 1, Length(Line) - Space);
        If Pos('|', Expr) > 0 Then
          Writeln(OutFile, Key + ' skipped')
        Else
        Begin
          ClearAll(Board);
          CountChildren(Board, Key, OutFile, True);
          ResetParameters;
          AddStringParameter('{PROCESS_PARAMETERS[0]}', Expr);
          AddStringParameter('{PROCESS_PARAMETERS[1]}', 'True');
          AddStringParameter('{PROCESS_PARAMETERS[2]}', 'True');
          RunProcess('{PROCESS}');
{chr(10).join(f"          CountKind(Board, {kind}, Key, OutFile);" for kind in KINDS)}
          CountChildren(Board, Key, OutFile, False);
          Writeln(OutFile, Key + ' done');
        End;
      End;
    End;
  Finally
    CloseFile(InFile);
    CloseFile(OutFile);
  End;
End;
"""


KEYWORDS = frozenset(
    "Function Procedure Var Begin End If Then Else While Do Not Or Try Finally Exit Nil True False Result "
    "String".split()
)
"""DelphiScript keywords and types the script uses (S-0502)."""


def called_names(text: str) -> set[str]:
    """The names of ``text`` that are not its own procedures, variables or parameters, nor a keyword."""
    own = {"KindName", "ClearAll", "CountKind", "CountChildren", PROCEDURE}
    own |= set("Id Board Iterator Item Children Child Kind Key OutFile Count Parent Clear".split())
    own |= {"InFile", "Line", "Space", "Expr"}
    body = re.sub(r"'[^']*'", "", re.sub(r"\{[^}]*\}", "", text))
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", body)) - own - KEYWORDS


_COUNT = re.compile(
    r"(?P<n>[0-9]+) (?:(?P<board>board) (?P<kind>[a-z]+) (?P<count>[0-9]+)"
    r"|(?P<child>child) (?P<parent>[a-z]+) (?P<ckind>[a-z]+) 1|(?P<state>done|skipped))"
)


def parse_counts(text: str, scopes: Sequence[str]) -> list[dict[str, object]]:
    """The counts of one ``.counts.txt`` for the scopes it was run on; ``ValueError`` on a line that is not
    the script's, a scope never finished, or a scope the plan does not hold."""
    entries: dict[int, dict[str, object]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        found = _COUNT.fullmatch(line.strip())
        if found is None:
            raise ValueError(f"line {line!r} is not one the script writes")
        n = int(found["n"])
        if not 1 <= n <= len(scopes):
            raise ValueError(f"scope {n} is not in the plan")
        entry = entries.setdefault(n, {"scope": scopes[n - 1], "board": {}, "child": {}, "state": None})
        if found["board"]:
            cast(dict[str, int], entry["board"])[found["kind"]] = int(found["count"])
        elif found["child"]:
            child = cast(dict[str, int], entry["child"])
            key = f"{found['parent']}/{found['ckind']}"
            child[key] = child.get(key, 0) + 1
        else:
            entry["state"] = found["state"]
    missing = [n for n in range(1, len(scopes) + 1) if entries.get(n, {}).get("state") is None]
    if missing:
        raise ValueError(f"scopes {missing} have no 'done' or 'skipped' line")
    return [entries[n] for n in range(1, len(scopes) + 1)]


def plan(out: Path, cache: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    (out / SCRIPT).write_text(script_text(), encoding="utf-8", newline="\r\n")
    for ident, _sha, path in public_rows(cache):
        scopes = mapped_scopes(path.read_bytes(), path.name)
        (out / f"{path.name}{SCOPES}").write_text(scope_lines(scopes), encoding="utf-8", newline="\r\n")
        print(f"{ident}: {len(scopes)} scopes -> {path.name}{SCOPES}")
    return 0


def record(results: Path, out: Path, cache: Path, altium: str) -> int:
    rows: list[dict[str, object]] = []
    for ident, sha, path in public_rows(cache):
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise SystemExit(f"{ident}: the cached file is not the manifest's")
        scopes = mapped_scopes(path.read_bytes(), path.name)
        counts = results / f"{path.name}{COUNTS}"
        if not counts.is_file():
            raise SystemExit(f"{ident}: {counts.name} is missing from {results}")
        rows.append({"row": ident, "sha256": sha, "scopes": parse_counts(counts.read_text("utf-8"), scopes)})
    oracle = {"schema": SCHEMA, "source": "S-2214", "altium": altium, "rows": rows}
    out.write_text(json.dumps(oracle, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("record")
    r.add_argument("--results", type=Path, required=True)
    r.add_argument("--out", type=Path, required=True)
    r.add_argument("--altium", required=True, help="the Altium Designer version the run used, e.g. 26.1.0")
    for each in (p, r):
        each.add_argument("--cache", type=Path, default=default_cache())
    args = parser.parse_args(argv)
    if args.command == "plan":
        return plan(args.out, args.cache)
    return record(args.results, args.out, args.cache, args.altium)


if __name__ == "__main__":
    sys.exit(main())
