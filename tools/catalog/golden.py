# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden digests of the shipped catalog (change c0259, task 1.1).

    uv run python tools/catalog/golden.py            # (re)write tests/data/catalog/golden.json
    uv run python tools/catalog/golden.py --check    # exit 1 when the catalog no longer matches it

``definitions`` holds, per lib id, the SHA-256 of the canonical JSON of the catalog's definition (its
``output_digest``); ``renders`` the SHA-256 of the two review sheets of ``tools/catalog/render_*.py``;
``builds`` the SHA-256 of each file that ``fenolite build`` writes for each catalog example with
``--seed 1`` and a fixed ``--timestamp``, but ``.fenolite/meta.json``, which names the version of
Fenolite. The file was first written from the Python catalog before the move to data files, so every later
catalog must give the same bytes; it changes only together with a version change in
``src/fenolite/catalog/data/VERSIONS.toml``.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "data" / "catalog" / "golden.json"
EXAMPLES: tuple[str, ...] = ("examples/catalog/design.py",)
"""The catalog examples whose built files are recorded."""
TIMESTAMP = "2026-01-01T00:00:00Z"
UNRECORDED: tuple[str, ...] = (".fenolite/meta.json",)
"""Built files left out: the model header holds the version of Fenolite, which a release changes."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def definitions() -> dict[str, str]:
    """``output_digest`` of every catalog definition, by lib id."""
    from fenolite.catalog import ENTRIES, get_footprint, get_symbol
    from fenolite.model import canonical

    found: dict[str, str] = {}
    for entry in ENTRIES:
        definition = get_symbol(entry.lib_id) if entry.kind == "symbol" else get_footprint(entry.lib_id)
        found[entry.lib_id] = _sha(canonical.dumps(definition).encode("utf-8"))
    return dict(sorted(found.items()))


def _tool(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "catalog" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def renders() -> dict[str, str]:
    """The SHA-256 of the full review sheets of the symbols and of the footprints."""
    from fenolite.catalog import list_entries

    symbols = [entry.lib_id.split(":", 1)[1] for entry in list_entries(kind="symbol")]
    footprints = [entry.lib_id.split(":", 1)[1] for entry in list_entries(kind="footprint")]
    return {
        "render_symbols": _sha(_tool("render_symbols").render(symbols).encode("utf-8")),
        "render_footprints": _sha(_tool("render_footprints").render(footprints).encode("utf-8")),
    }


def builds() -> dict[str, dict[str, str]]:
    """The SHA-256 of every file built for each catalog example, by path in the built folder."""
    from fenolite.cli.main import main

    found: dict[str, dict[str, str]] = {}
    for example in EXAMPLES:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "out"
            sink = io.StringIO()
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                code = main(
                    ["--seed", "1", "--timestamp", TIMESTAMP, "build", str(ROOT / example), "--out", str(out),
                     "--confirm", "--json"]
                )  # fmt: skip
            if code != 0:
                raise SystemExit(f"{example}: build exited {code}: {sink.getvalue()[-2000:]}")
            found[example] = {
                path.relative_to(out).as_posix(): _sha(path.read_bytes())
                for path in sorted(out.rglob("*"))
                if path.is_file() and path.relative_to(out).as_posix() not in UNRECORDED
            }
    return found


def golden() -> dict[str, object]:
    return {"definitions": definitions(), "renders": renders(), "builds": builds()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare with the file instead of writing it")
    args = parser.parse_args(argv)
    text = json.dumps(golden(), indent=2, sort_keys=True) + "\n"
    if args.check:
        if not GOLDEN.is_file() or GOLDEN.read_text(encoding="utf-8") != text:
            print(f"{GOLDEN.relative_to(ROOT)} does not match the catalog", file=sys.stderr)
            return 1
        return 0
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(text, encoding="utf-8")
    print(f"wrote {GOLDEN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
