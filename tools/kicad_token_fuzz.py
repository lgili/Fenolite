# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Prove the KiCad token inventory on a real kicad-cli (openspec change c0007, capability kicad-oracle).

    uv run python tools/kicad_token_fuzz.py [--kicad-cli PATH | --docker IMAGE] [--only ID ...]
                                             (--write DIR | --check DIR) [--timeout S]

Each example of tests/data/kicad/tokens/examples.toml becomes one case per kind (two for rows that the
running major no longer writes). The case file is the kind's skeleton with the example inserted and a
header chosen from the inventory; kicad-cli then decides whether it loads. Results are written to
<DIR>/<kicad-cli version>.json (--write) or compared with the committed file (--check).

Exit codes: 0 every outcome matches, 5 a mismatch (or drift from the committed results under --check),
6 no usable kicad-cli, 2 usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse, parse_fragment  # noqa: E402
from fenolite.backends.kicad.versions import (  # noqa: E402
    FORMAT_VERSIONS,
    FileKind,
    Inventory,
    load_inventory,
    wrap_rules,
)
from fenolite.core.evidence import Level  # noqa: E402

DATA = ROOT / "tests" / "data" / "kicad" / "tokens"
RESULTS_FORMAT = 1
DEFAULT_TIMEOUT = 120.0
MACOS_KICAD_CLI = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
SKELETONS = {
    FileKind.BOARD: "skeleton.kicad_pcb",
    FileKind.FOOTPRINT: "skeleton.kicad_mod",
    FileKind.WORKSHEET: "skeleton.kicad_wks",
    FileKind.RULES: "canary/canary.kicad_dru",
    FileKind.SCHEMATIC: "skeleton.kicad_sch",
    FileKind.SYMBOL_LIB: "skeleton.kicad_sym",
}
FLOOR_MAJOR = {
    FileKind.BOARD: 8,
    FileKind.FOOTPRINT: 8,
    FileKind.WORKSHEET: 8,
    FileKind.RULES: 9,
    FileKind.SCHEMATIC: 8,
    FileKind.SYMBOL_LIB: 8,
}
VERSIONED = (FileKind.BOARD, FileKind.FOOTPRINT, FileKind.SCHEMATIC, FileKind.SYMBOL_LIB)
"""The kinds whose case header is chosen from the inventory (the skeleton's own header is replaced)."""
EXAMPLE_KEYS = {"id", "kinds", "host", "mode", "fragment", "file", "exercises", "expect", "header", "note"}
OUTCOMES = ("load", "reject", "timeout", "inconclusive")
WORKSHEET_ERROR = "Error loading drawing sheet"
CANARY_TYPE = "clearance"

Runner = Callable[[Sequence[str], Path, dict[str, str], float], "RunResult"]


class UsageError(Exception):
    """A usage or input error of the harness (exit 2)."""


@dataclass(frozen=True)
class RunResult:
    returncode: int
    output: str


@dataclass(frozen=True)
class Example:
    id: str
    kinds: tuple[FileKind, ...]
    host: str | None = None
    mode: str | None = None
    fragment: str | None = None
    file: str | None = None
    exercises: tuple[str, ...] = ()
    expect: dict[str, str] | None = None
    header: int | None = None
    sha256: str = ""


@dataclass(frozen=True)
class Case:
    example: str
    kind: FileKind
    header_version: int
    example_sha256: str
    rows: tuple[str, ...]
    expected: str
    files: dict[str, bytes] = field(compare=False, repr=False)
    fixed_header: bool = field(default=False, compare=False)

    @property
    def key(self) -> tuple[str, str, int]:
        return self.example, self.kind.value, self.header_version


@dataclass(frozen=True)
class Outcome:
    outcome: str
    exit_code: int | None
    detail: str


# --- examples -------------------------------------------------------------------------------------


def _sha(entry: dict[str, Any], base: Path) -> str:
    payload = dict(entry)
    if entry.get("file"):
        payload["file_bytes"] = hashlib.sha256((base / str(entry["file"])).read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def load_examples(text: str, inventory: Inventory | None = None, *, base: Path = DATA) -> list[Example]:
    """Parse and validate ``examples.toml``; ``UsageError`` names the example at fault."""
    inventory = inventory or load_inventory()
    forms = {f.id for f in inventory.forms}
    examples: list[Example] = []
    seen: set[str] = set()
    for entry in tomllib.loads(text).get("example", []):
        ident = str(entry.get("id", "?"))
        unknown = sorted(set(entry) - EXAMPLE_KEYS)
        if unknown:
            raise UsageError(f"example {ident}: unknown key(s) {', '.join(unknown)}")
        if ident in seen:
            raise UsageError(f"example {ident}: duplicate id")
        seen.add(ident)
        try:
            kinds = tuple(FileKind(k) for k in entry.get("kinds", []))
        except ValueError as exc:
            raise UsageError(f"example {ident}: unknown kind in {entry.get('kinds')!r}") from exc
        if not kinds:
            raise UsageError(f"example {ident}: kinds must not be empty")
        has_file = "file" in entry
        has_fragment = "fragment" in entry or "host" in entry or "mode" in entry
        if has_file == has_fragment and ident != "positive-baseline":
            raise UsageError(f"example {ident}: give either file, or host, mode and fragment")
        if has_fragment and (entry.get("mode") not in ("append", "replace") or "host" not in entry):
            raise UsageError(f"example {ident}: mode must be 'append' or 'replace', with a host")
        for key in ("fragment", "file", "host"):
            if key in entry and not str(entry[key]).isascii():
                raise UsageError(f"example {ident}: {key} must be ASCII")
        if has_file and not (base / str(entry["file"])).is_file():
            raise UsageError(f"example {ident}: file {entry['file']!r} not found in {base}")
        exercises = tuple(entry.get("exercises", ()))
        for form_id in exercises:
            if form_id not in forms:
                raise UsageError(f"example {ident}: exercises unknown form row {form_id!r}")
        expect = entry.get("expect")
        if expect is not None and not set(expect.values()) <= {"load", "reject"}:
            raise UsageError(f"example {ident}: expect values must be 'load' or 'reject'")
        examples.append(
            Example(
                ident,
                kinds,
                entry.get("host"),
                entry.get("mode"),
                entry.get("fragment"),
                entry.get("file"),
                exercises,
                dict(expect) if expect else None,
                entry.get("header"),
                _sha(entry, base),
            )
        )
    return examples


def _skeleton_text(kind: FileKind, base: Path) -> str:
    return (base / SKELETONS[kind]).read_text(encoding="utf-8")


def _find(node: Node, chain: Sequence[str]) -> list[int] | None:
    """Child indices leading from ``node`` (whose head is chain[0]) to the first node with that chain."""
    if node.name != chain[0]:
        return None
    if len(chain) == 1:
        return []
    for index, child in enumerate(node.children):
        if isinstance(child, Node):
            rest = _find(child, chain[1:])
            if rest is not None:
                return [index, *rest]
    return None


def _replace_at(node: Node, path: list[int], new: Sequence[Node | Atom], mode: str) -> Node:
    if not path:
        raise UsageError("replace mode needs a host below the root")
    index, rest = path[0], path[1:]
    child = node.children[index]
    assert isinstance(child, Node)
    children = list(node.children)
    if rest:
        children[index] = _replace_at(child, rest, new, mode)
    elif mode == "replace":
        children[index : index + 1] = list(new)
    else:
        children[index] = child.with_children([*child.children, *new])
    return node.with_children(children)


def _fragment_items(fragment: str) -> list[Node | Atom]:
    wrapped = parse_fragment(f"(fenolite_fragment {fragment})")
    assert isinstance(wrapped, Node)
    return list(wrapped.children)


def _insert(tree: Node, example: Example) -> tuple[Node, list[tuple[tuple[str, ...], Node | Atom]]]:
    """The skeleton with the example inserted, and each inserted item with its parent chain."""
    assert example.host is not None and example.mode is not None and example.fragment is not None
    chain = tuple(example.host.split("/"))
    path = _find(tree, chain)
    if path is None:
        raise UsageError(f"example {example.id}: host {example.host!r} not found in the skeleton")
    items = _fragment_items(example.fragment)
    if example.mode == "append":
        new_tree = (
            _replace_at(tree, path, items, "append") if path else tree.with_children([*tree.children, *items])
        )
        parent = chain
    else:
        new_tree = _replace_at(tree, path, items, "replace")
        parent = chain[:-1]
    return new_tree, [(parent, item) for item in items]


def _rows_in(
    inventory: Inventory, kind: FileKind, parent: tuple[str, ...], item: Node | Atom, found: set[str]
) -> None:
    if isinstance(item, Atom):
        return
    chain = (*parent, item.name)
    row = inventory.match(kind, chain)
    if row is not None:
        found.add(row.id)
    for child in item.children:
        if isinstance(child, Node):
            _rows_in(inventory, kind, chain, child, found)
        elif child.kind == AtomKind.SYMBOL:
            value = inventory.match(kind, chain, child.text)
            if value is not None:
                found.add(value.id)


def exercised_rows(
    example: Example, kind: FileKind, inventory: Inventory, base: Path = DATA
) -> tuple[str, ...]:
    """Token rows matched by the example's nodes in host context (or by its whole file), plus forms."""
    found: set[str] = set()
    if example.file is not None:
        text = (base / example.file).read_text(encoding="utf-8")
        _rows_in(inventory, kind, (), parse(text), found)
    elif example.fragment is None:  # positive-baseline: the skeleton itself
        text = _skeleton_text(kind, base)
        root = wrap_rules(text) if kind == FileKind.RULES else parse(text)
        _rows_in(inventory, kind, (), root, found)
    elif kind == FileKind.RULES:
        for item in wrap_rules(example.fragment).children:
            _rows_in(inventory, kind, ("kicad_dru",), item, found)
    else:
        _, items = _insert(parse(_skeleton_text(kind, base)), example)
        for parent, item in items:
            _rows_in(inventory, kind, parent, item, found)
    found.update(example.exercises)
    return tuple(sorted(found))


def _since(inventory: Inventory, row_id: str) -> tuple[int, int | None, str]:
    for row in inventory.tokens:
        if row.id == row_id:
            return row.since_major, row.until_major, row.older_readers
    form = inventory.form(row_id)
    return form.since_major, None, "reject"


def _set_header(tree: Node, header: int) -> Node:
    children = [
        child.with_children([Atom.integer(header)])
        if isinstance(child, Node) and child.name == "version"
        else child
        for child in tree.children
    ]
    return tree.with_children(children)


def _case_files(example: Example, kind: FileKind, header: int, base: Path) -> dict[str, bytes]:
    if kind == FileKind.RULES:
        rules = _skeleton_text(kind, base)
        if example.fragment is not None:
            rules = rules.rstrip("\n") + "\n" + example.fragment.strip() + "\n"
        return {
            "canary.kicad_pcb": (base / "canary" / "canary.kicad_pcb").read_bytes(),
            "canary.kicad_pro": (base / "canary" / "canary.kicad_pro").read_bytes(),
            "canary.kicad_dru": rules.encode("utf-8"),
        }
    if example.file is not None:
        tree = parse((base / example.file).read_text(encoding="utf-8"))
    elif example.fragment is None:
        tree = parse(_skeleton_text(kind, base))
    else:
        tree, _ = _insert(parse(_skeleton_text(kind, base)), example)
    if kind in VERSIONED:
        tree = _set_header(tree, header)
    data = dumps(tree).encode("utf-8")
    if kind == FileKind.BOARD:
        return {"case.kicad_pcb": data}
    if kind == FileKind.SCHEMATIC:
        return {"case.kicad_sch": data}
    if kind == FileKind.SYMBOL_LIB:
        return {"case.kicad_sym": data}
    if kind == FileKind.FOOTPRINT:
        return {"case.pretty/case.kicad_mod": data}
    return {"case.kicad_wks": data, "board.kicad_pcb": (base / SKELETONS[FileKind.BOARD]).read_bytes()}


def _header_of(example: Example, kind: FileKind, base: Path) -> int:
    if kind == FileKind.RULES:
        return 1
    if kind == FileKind.WORKSHEET:
        if example.file is not None:
            node = parse((base / example.file).read_text(encoding="utf-8"))
            version = node.find("version")
            return int(version.atoms()[0].text) if version is not None else 0
        return FORMAT_VERSIONS[kind][8]
    raise AssertionError(kind)


def build_cases(
    inventory: Inventory, examples: Iterable[Example], major: int, base: Path = DATA
) -> list[Case]:
    """Every case to run on ``major``, baselines included, sorted by (example, kind, header)."""
    cases: list[Case] = []
    baseline = None
    for example in examples:
        if example.id == "positive-baseline":
            baseline = example
            continue
        for kind in example.kinds:
            rows = exercised_rows(example, kind, inventory, base)
            sinces = [_since(inventory, r) for r in rows]
            top = max([s for s, _, _ in sinces], default=FLOOR_MAJOR[kind])
            if example.header is not None:
                headers = [example.header]
            elif kind in VERSIONED:
                headers = [FORMAT_VERSIONS[kind][min(major, top)]]
                if any(u is not None and u < major for _, u, _ in sinces):
                    headers.append(FORMAT_VERSIONS[kind][major])
            else:
                headers = [_header_of(example, kind, base)]
            for header in dict.fromkeys(headers):
                if example.expect is not None:
                    if str(major) not in example.expect:
                        continue
                    expected = example.expect[str(major)]
                elif header == FORMAT_VERSIONS.get(kind, {}).get(major) and header != headers[0]:
                    expected = "load"
                else:
                    above = [r for s, _, r in sinces if s > major]
                    expected = "load" if all(r == "ignore" for r in above) else "reject"
                files = _case_files(example, kind, header, base)
                fixed = example.header is not None or example.file is not None
                cases.append(Case(example.id, kind, header, example.sha256, rows, expected, files, fixed))
    if baseline is not None:
        used = sorted(
            {(c.kind, c.header_version) for c in cases if c.kind in VERSIONED and not c.fixed_header}
        )
        used += [(kind, _header_of(baseline, kind, base)) for kind in (FileKind.WORKSHEET, FileKind.RULES)]
        for kind, header in used:
            if kind not in baseline.kinds:
                continue
            rows = exercised_rows(baseline, kind, inventory, base)
            expected = (baseline.expect or {}).get(str(major), "load")
            cases.append(
                Case(
                    baseline.id,
                    kind,
                    header,
                    baseline.sha256,
                    rows,
                    expected,
                    _case_files(baseline, kind, header, base),
                )
            )
    return sorted(cases, key=lambda c: (c.example, c.kind.value, c.header_version))


# --- running --------------------------------------------------------------------------------------


def kicad_env(tmp: Path) -> dict[str, str]:
    """The isolated environment of every kicad-cli run: empty config, C locale."""
    env = dict(os.environ)
    config = tmp / "cfg"
    config.mkdir(parents=True, exist_ok=True)
    env.update({"KICAD_CONFIG_HOME": str(config), "LANG": "C", "LC_ALL": "C"})
    return env


def sanitise(text: str, tmp: Path) -> str:
    """The first output line with temporary and home paths replaced."""
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    for path in sorted({str(tmp), os.path.realpath(tmp)}, key=len, reverse=True):
        line = line.replace(path, "<tmp>")
    home = str(Path.home())
    if home and home != "/":
        line = line.replace(home, "~")
    return line


def subprocess_runner(cli: str) -> Runner:
    def run(args: Sequence[str], cwd: Path, env: dict[str, str], timeout: float) -> RunResult:
        done = subprocess.run(
            [cli, *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return RunResult(done.returncode, done.stdout + done.stderr)

    return run


def run_case(
    case: Case, runner: Runner, *, timeout: float = DEFAULT_TIMEOUT, root: Path | None = None
) -> Outcome:
    """Write the case in a fresh temporary directory and decide whether kicad-cli loads it."""
    with tempfile.TemporaryDirectory(prefix="fenolite-fuzz-", dir=root) as name:
        tmp = Path(name)
        for rel, data in case.files.items():
            target = tmp / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        env = kicad_env(tmp)
        if case.kind == FileKind.BOARD:
            args = [
                "pcb",
                "export",
                "svg",
                "case.kicad_pcb",
                "-l",
                "Edge.Cuts",
                "--mode-single",
                "-o",
                "out.svg",
            ]
        elif case.kind == FileKind.FOOTPRINT:
            (tmp / "out").mkdir()
            args = ["fp", "export", "svg", "case.pretty", "-o", "out"]
        elif case.kind == FileKind.SCHEMATIC:
            args = ["sch", "export", "netlist", "case.kicad_sch", "-o", "out.net"]
        elif case.kind == FileKind.SYMBOL_LIB:
            (tmp / "out").mkdir()
            args = ["sym", "export", "svg", "case.kicad_sym", "-o", "out"]
        elif case.kind == FileKind.WORKSHEET:
            args = [
                "pcb",
                "export",
                "svg",
                "board.kicad_pcb",
                "--drawing-sheet",
                "case.kicad_wks",
                "-l",
                "Edge.Cuts",
                "--mode-single",
                "-o",
                "out.svg",
            ]
        else:
            args = ["pcb", "drc", "--format", "json", "-o", "r.json", "canary.kicad_pcb"]
        try:
            result = runner(args, tmp, env, timeout)
        except subprocess.TimeoutExpired:
            return Outcome("timeout", None, f"no answer within {timeout:g} s")
        detail = sanitise(result.output, tmp)
        if case.kind == FileKind.BOARD:
            loaded = result.returncode == 0 and (tmp / "out.svg").is_file()
        elif case.kind in (FileKind.FOOTPRINT, FileKind.SYMBOL_LIB):
            loaded = result.returncode == 0 and any((tmp / "out").glob("*.svg"))
        elif case.kind == FileKind.SCHEMATIC:
            loaded = result.returncode == 0 and (tmp / "out.net").is_file()
        elif case.kind == FileKind.WORKSHEET:
            loaded = result.returncode == 0 and WORKSHEET_ERROR not in result.output
            if not loaded and WORKSHEET_ERROR in result.output:
                lines = result.output.splitlines()
                at = next(i for i, ln in enumerate(lines) if WORKSHEET_ERROR in ln)
                detail = sanitise("\n".join(lines[at + 1 : at + 2]) or lines[at], tmp)
        else:
            loaded = result.returncode == 0 and _canary_fired(tmp / "r.json")
        return Outcome("load" if loaded else "reject", result.returncode, detail)


def _canary_fired(report: Path) -> bool:
    if not report.is_file():
        return False
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except ValueError:
        return False
    violations = data.get("violations", [])
    return any(isinstance(v, dict) and v.get("type") == CANARY_TYPE for v in violations)


def probe_version(runner: Runner, timeout: float = DEFAULT_TIMEOUT) -> str:
    """The first line of ``kicad-cli version``, restricted to ``[0-9A-Za-z.+-]``."""
    with tempfile.TemporaryDirectory(prefix="fenolite-fuzz-") as name:
        result = runner(["version"], Path(name), kicad_env(Path(name)), timeout)
    first = next((ln.strip() for ln in result.output.splitlines() if ln.strip()), "")
    version = re.sub(r"[^0-9A-Za-z.+-]", "", first)
    if result.returncode != 0 or not re.match(r"\d+\.\d+", version):
        raise RuntimeError(f"kicad-cli version gave {first!r}")
    return version


def run_all(cases: list[Case], runner: Runner, timeout: float) -> list[dict[str, Any]]:
    """Run every case; a case whose (kind, header) baseline did not load is ``inconclusive``."""
    outcomes = {case.key: run_case(case, runner, timeout=timeout) for case in cases}
    baseline_ok = {
        (c.kind, c.header_version): outcomes[c.key].outcome == "load"
        for c in cases
        if c.example == "positive-baseline"
    }
    records: list[dict[str, Any]] = []
    for case in cases:
        outcome = outcomes[case.key]
        state = outcome.outcome
        baseline = baseline_ok.get((case.kind, case.header_version))
        if case.example != "positive-baseline" and not case.fixed_header and baseline is False:
            state = "inconclusive"
        records.append(
            {
                "example": case.example,
                "kind": case.kind.value,
                "header_version": case.header_version,
                "example_sha256": case.example_sha256,
                "rows": list(case.rows),
                "expected": case.expected,
                "outcome": state,
                "exit_code": outcome.exit_code,
                "detail": outcome.detail,
            }
        )
    return records


def mismatches(records: Iterable[dict[str, Any]]) -> list[str]:
    return [
        f"{r['example']} [{r['kind']} {r['header_version']}]: expected {r['expected']}, got {r['outcome']}"
        f" (rows {', '.join(r['rows']) or 'none'})"
        for r in records
        if r["outcome"] != "inconclusive" and r["outcome"] != r["expected"]
    ]


def drift(records: list[dict[str, Any]], committed: dict[str, Any]) -> list[str]:
    old = {(c["example"], c["kind"], c["header_version"]): c for c in committed.get("cases", [])}
    problems: list[str] = []
    for record in records:
        key = (record["example"], record["kind"], record["header_version"])
        name = f"{record['example']} [{record['kind']} {record['header_version']}]"
        before = old.get(key)
        if before is None:
            problems.append(f"{name}: not in the committed results")
        elif (before["outcome"], before["exit_code"]) != (record["outcome"], record["exit_code"]):
            was = f"{before['outcome']} (exit {before['exit_code']})"
            problems.append(f"{name}: committed {was}, now {record['outcome']} (exit {record['exit_code']})")
    return problems


# --- evidence -------------------------------------------------------------------------------------


def row_levels(inventory: Inventory, results: Iterable[dict[str, Any]]) -> dict[str, dict[int, Level]]:
    """Evidence level per row and major from committed results (``inconclusive`` cases never count)."""
    rows: dict[str, tuple[int, int | None, frozenset[FileKind]]] = {
        r.id: (r.since_major, r.until_major, r.kinds) for r in inventory.tokens
    }
    rows.update({f.id: (f.since_major, None, f.kinds) for f in inventory.forms})
    levels: dict[str, dict[int, Level]] = {row_id: {} for row_id in rows}
    for result in results:
        major = int(str(result["kicad_cli"]["version"]).split(".")[0])
        cases = [c for c in result["cases"] if c["outcome"] != "inconclusive"]
        for row_id, (since, until, _kinds) in rows.items():
            mine = [c for c in cases if row_id in c["rows"]]
            ok = bool(mine) and all(c["outcome"] == c["expected"] for c in mine)
            if ok and major >= since:
                ok = any(c["outcome"] == "load" for c in mine)
                if ok and until is not None and until < major:
                    ok = any(
                        c["outcome"] == "load"
                        and c["header_version"] == FORMAT_VERSIONS[FileKind(c["kind"])][major]
                        for c in mine
                    )
            elif ok:
                ok = any(
                    c["outcome"] == c["expected"]
                    and [r for r in c["rows"] if r in rows and rows[r][0] > major] == [row_id]
                    for c in mine
                )
            levels[row_id][major] = Level.KICAD_VERIFIED if ok else Level.INFERRED
    return levels


# --- command line ---------------------------------------------------------------------------------


def find_cli(explicit: str | None) -> str | None:
    if explicit:
        return explicit if shutil.which(explicit) or Path(explicit).is_file() else None
    override = os.environ.get("FENOLITE_KICAD_CLI")
    if override:
        return override if Path(override).is_file() else None
    return shutil.which("kicad-cli") or (str(MACOS_KICAD_CLI) if MACOS_KICAD_CLI.is_file() else None)


def _docker(argv: list[str], image: str) -> int:
    passthrough: list[str] = []
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == "--docker":
            skip = True
            continue
        if not arg.startswith("--docker="):
            passthrough.append(arg)
    command = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        *(("-u", f"{os.getuid()}:{os.getgid()}") if hasattr(os, "getuid") else ()),
        "-e",
        "HOME=/tmp",
        "-e",
        "PYTHONPATH=/w/src",
        "-v",
        f"{ROOT}:/w",
        "-w",
        "/w",
        image,
        "python3",
        "tools/kicad_token_fuzz.py",
        "--kicad-cli",
        "kicad-cli",
        "--image",
        image,
        *passthrough,
    ]
    return subprocess.run(command, check=False).returncode


def main(argv: list[str] | None = None, *, runner: Runner | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Prove the KiCad token inventory on a real kicad-cli.")
    parser.add_argument("--kicad-cli", dest="kicad_cli")
    parser.add_argument("--docker", metavar="IMAGE")
    parser.add_argument("--image", default="", help=argparse.SUPPRESS)
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--examples", type=Path, default=DATA / "examples.toml")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", type=Path)
    group.add_argument("--check", type=Path)
    try:
        args = parser.parse_args(raw)
    except SystemExit as exc:
        return 2 if exc.code else 0
    if args.docker:
        return _docker(raw, args.docker)
    if runner is None:
        cli = find_cli(args.kicad_cli)
        if cli is None:
            print(
                "kicad-cli not found: install KiCad 9.0 or 10.0, set FENOLITE_KICAD_CLI, or use --docker",
                file=sys.stderr,
            )
            return 6
        runner = subprocess_runner(cli)
    try:
        version = probe_version(runner, args.timeout)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"kicad-cli is not usable: {exc}", file=sys.stderr)
        return 6
    major = int(version.split(".")[0])
    try:
        inventory = load_inventory()
        examples = load_examples(
            args.examples.read_text(encoding="utf-8"), inventory, base=args.examples.parent
        )
        if args.only:
            examples = [e for e in examples if e.id in set(args.only) or e.id == "positive-baseline"]
        cases = build_cases(inventory, examples, major, base=args.examples.parent)
    except UsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    records = run_all(cases, runner, args.timeout)
    result = {
        "format": RESULTS_FORMAT,
        "kicad_cli": {
            "version": version,
            "image": args.image,
            "platform": f"{platform.system().lower()}-{platform.machine().lower()}",
            "env": {"KICAD_CONFIG_HOME": "<tmp>/cfg", "LANG": "C", "LC_ALL": "C"},
        },
        "cases": records,
    }
    problems = mismatches(records)
    if args.write is not None:
        args.write.mkdir(parents=True, exist_ok=True)
        (args.write / f"{version}.json").write_text(
            json.dumps(result, indent=1, sort_keys=False) + "\n", encoding="utf-8"
        )
    else:
        committed_path = args.check / f"{version}.json"
        if not committed_path.is_file():
            print(
                f"no committed results for kicad-cli {version}: {committed_path} is missing", file=sys.stderr
            )
            return 5
        committed = json.loads(committed_path.read_text(encoding="utf-8"))
        if args.only:
            committed["cases"] = [
                c for c in committed["cases"] if c["example"] in {r["example"] for r in records}
            ]
        problems += drift(records, committed)
    for line in problems:
        print(line, file=sys.stderr)
    print(f"kicad-cli {version}: {len(records)} case(s), {len(problems)} problem(s)")
    return 5 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
