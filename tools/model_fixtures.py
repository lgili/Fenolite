# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build model fixtures from Fenolite's own CC0 example at pinned public release commits (c0218).

    uv run python tools/model_fixtures.py
    uv run python tools/model_fixtures.py --check

The old releases run in temporary detached worktrees with their own venv, offline. Only the six
model layer files are copied; no native CAD, third-party demo or licence fixture is copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "tests/data/model"
RELEASES = {
    "v0.1.0": "cd4c1f93e4794401355eb28d467ec9a67cb118c6",
    "v0.2.0": "ea9e8b4b24bad56b7792d9e020bb6906021f78c0",
    "v0.3.0": "0649339dc3e7ab1d0ecfc4aad7acc0eefa2bee4e",
    "v0.4.0": "591dc0055fe8a499792ee10c5bdd5709b010545f",
    "v0.5.0": "3a0bfb7d168f0e0ac8294c3d5c2500a4782a134d",
}
FILES = ("meta.json", "circuit.json", "board.json", "rules.json", "manufacturing.json", "findings.json")
EXAMPLE = "examples/blink_2layer/design.py"
TIMESTAMP = "2026-01-01T00:00:00Z"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def _safe_data(data: object, location: str = "") -> None:
    if isinstance(data, str) and any(
        prefix in data for prefix in ("/workspace/", "/home/", "/Users/", "\\Users\\")
    ):
        raise ValueError(f"{location}: a temporary/user path must not enter a release fixture")
    if isinstance(data, float):
        raise ValueError(f"{location}: a model fixture must contain no float")
    if isinstance(data, dict):
        for key, value in data.items():
            _safe_data(value, f"{location}/{key}")
    elif isinstance(data, list):
        for index, value in enumerate(data):
            _safe_data(value, f"{location}/{index}")


def build(tag: str, destination: Path) -> None:
    commit = RELEASES[tag]
    if _git("rev-parse", f"{tag}^{{commit}}") != commit:
        raise ValueError(f"{tag}: local public tag differs from its pinned commit {commit}")
    with tempfile.TemporaryDirectory(prefix="fenolite-model-fixture-") as temporary:
        work = Path(temporary) / "release"
        _git("worktree", "add", "--detach", str(work), commit)
        try:
            guidance = work / "AGENTS.md"
            if not guidance.is_file():
                raise ValueError(f"{tag}: expected repository guidance")
            guidance.read_text(encoding="utf-8")
            example = (work / EXAMPLE).read_text(encoding="utf-8")
            if (
                not example.startswith("# SPDX-License-Identifier: CC0-1.0")
                or "Authored for Fenolite" not in example
            ):
                raise ValueError(f"{tag}: the example must be Fenolite's own explicitly authored CC0 data")
            environment = dict(os.environ)
            for key in ("VIRTUAL_ENV", "PYTHONPATH"):
                environment.pop(key, None)
            environment["UV_PROJECT_ENVIRONMENT"] = str(work / ".venv")
            environment["FENOLITE_STATE_DIR"] = str(Path(temporary) / "state")
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            command = [
                "uv",
                "run",
                "--offline",
                "--frozen",
                "--no-dev",
                "--project",
                str(work),
                "fenolite",
                "build",
                EXAMPLE,
                "--out",
                "build/model-fixture",
                "--seed",
                "0",
                "--timestamp",
                TIMESTAMP,
                "--confirm",
                "--json",
            ]
            result = subprocess.run(command, cwd=work, env=environment, capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(
                    f"{tag}: historical build failed ({result.returncode})\n{result.stderr}\n{result.stdout}"
                )
            generated = work / "build/model-fixture/.fenolite"
            data: dict[str, bytes] = {}
            for name in FILES:
                content = (generated / name).read_bytes()
                _safe_data(json.loads(content), name)
                data[name] = content
            if json.loads(data["meta.json"])["schema_version"] != "0":
                raise ValueError(f"{tag}: expected the historical model schema 0")
            destination.mkdir(parents=True, exist_ok=True)
            for name, content in data.items():
                (destination / name).write_bytes(content)
            source = {
                "schema": "fenolite.model-fixture.v0",
                "tag": tag,
                "commit": commit,
                "url": f"https://github.com/lgili/Fenolite/tree/{tag}/{EXAMPLE}",
                "example": EXAMPLE,
                "licence": "CC0-1.0",
                "authored": "Fenolite's own CC0 Mini example; generated by its pinned public release.",
                "seed": 0,
                "timestamp": TIMESTAMP,
                "files": {name: hashlib.sha256(content).hexdigest() for name, content in data.items()},
            }
            (destination / "SOURCE").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
            print(f"built {tag} ({commit}): {len(data)} original model layers")
        finally:
            _git("worktree", "remove", "--force", str(work))


def check(tag: str, destination: Path) -> None:
    source = json.loads((destination / "SOURCE").read_text(encoding="utf-8"))
    if (source.get("tag"), source.get("commit"), source.get("example")) != (tag, RELEASES[tag], EXAMPLE):
        raise ValueError(f"{tag}: SOURCE does not name the pinned public example/commit")
    if set(source.get("files", {})) != set(FILES):
        raise ValueError(f"{tag}: SOURCE must list the six model layer hashes")
    for name in FILES:
        content = (destination / name).read_bytes()
        _safe_data(json.loads(content), name)
        if hashlib.sha256(content).hexdigest() != source["files"][name]:
            raise ValueError(f"{tag}/{name}: differs from the release fixture's SOURCE hash")
    meta = json.loads((destination / "meta.json").read_text(encoding="utf-8"))
    if meta.get("schema_version") != "0" or meta.get("fenolite_version") != tag.removeprefix("v"):
        raise ValueError(f"{tag}: metadata does not identify the historical release and schema 0")
    print(f"checked {tag} ({RELEASES[tag]}): six original model layers")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--tag", choices=tuple(RELEASES), action="append")
    args = parser.parse_args(argv)
    try:
        for tag in args.tag or RELEASES:
            (check if args.check else build)(tag, DESTINATION / tag)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
