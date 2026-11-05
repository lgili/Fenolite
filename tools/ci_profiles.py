# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative CI event policy and distinct aggregate gates (c0380)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

WORKING = ("codex/", "cac/", "feature/", "fix/", "router-")
INTEGRATION = ("dev", "main", "master")
FULL_JOBS = (
    "plan",
    "quality",
    "dco",
    "unit",
    "viewer",
    "mcp",
    "wheel",
    "kicad-10",
    "kicad-9",
    "routing",
    "drawn-floor-bridge",
    "audit",
)


def controls(path: str) -> bool:
    path = path.casefold()
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith((".github/", "tools/ci_", "tests/"))
        or name
        in {
            "conftest.py",
            "pytest.toml",
            ".pytest.toml",
            "pytest.ini",
            ".pytest.ini",
            "tox.ini",
            "setup.cfg",
        }
        or path
        in {
            "agents.md",
            "contributing.md",
            "docs/ci.md",
            "makefile",
            "gnumakefile",
            "pyproject.toml",
            "setup.py",
            "uv.toml",
            "uv.lock",
            ".python-version",
            "tests/_resources.py",
            "tests/_drawn_census_reuse.py",
            "tests/_drawn_context.py",
            "tests/_drawn_corpus.py",
            "tests/kicad/schematic/test_drawn_corpus.py",
        }
    )


def profile(event: str, ref: str, payload: dict, changed: list[str] | None) -> tuple[str, str]:
    if event not in {"push", "workflow_dispatch"}:
        return "full", "pull requests, merge groups and unknown events require full validation"
    if not ref.startswith("refs/heads/"):
        return "full", "non-branch or unknown ref"
    branch = ref.removeprefix("refs/heads/")
    if branch in INTEGRATION or branch.startswith(("release/", "releases/", "cac/lote-")):
        return "full", "integration branch"
    if not branch.startswith(WORKING):
        return "full", "unclassified branch"
    if payload.get("deleted"):
        return "full", "deleted ref cannot produce a fast validation"
    if changed is None or any(controls(p) for p in changed):
        return "full", "unknown diff or CI-control change"
    inputs = payload.get("inputs", {})
    if event == "workflow_dispatch" and (not isinstance(inputs, dict) or inputs.get("profile") != "fast"):
        return "full", "manual full validation (default)"
    return "fast", "working branch: full validation remains required on every PR"


def changed_paths(event: str, payload: dict) -> list[str] | None:
    try:
        before = payload.get("before") if event == "push" else ""
        if event == "push" and (
            not isinstance(before, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", before)
        ):
            return None
        if not before or set(before) == {"0"}:
            before = subprocess.check_output(
                ["git", "merge-base", "origin/dev", "HEAD"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", before):
            return None
        result = subprocess.check_output(
            ["git", "diff", "--no-renames", "--name-only", "-z", before, "HEAD"],
            stderr=subprocess.DEVNULL,
        )
        return [part.decode("utf-8") for part in result.split(b"\0") if part]
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return None


def gate(kind: str, selected: str, needs: dict) -> list[str]:
    if selected != kind:
        return [f"{kind} gate cannot certify profile {selected!r}"]
    required = FULL_JOBS if kind == "full" else ("plan", "quality", "dco", "fast", "fast-audit")
    return [
        f"{job}: expected success, got {needs.get(job, {}).get('result', 'missing')}"
        for job in required
        if needs.get(job, {}).get("result") != "success"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "gate"))
    parser.add_argument("--kind", choices=("fast", "full"))
    args = parser.parse_args()
    if args.mode == "gate":
        problems = gate(
            args.kind or "full",
            os.environ.get("CI_PROFILE", ""),
            json.loads(os.environ.get("CI_NEEDS", "{}")),
        )
        print("\n".join(problems) if problems else f"{args.kind} validation passed")
        return int(bool(problems))
    try:
        payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("event must be an object")
    except (KeyError, OSError, ValueError) as exc:
        payload = {}
        selected, reason = "full", f"invalid event input: {type(exc).__name__}"
    else:
        event = os.environ.get("GITHUB_EVENT_NAME", "")
        selected, reason = profile(
            event, os.environ.get("GITHUB_REF", ""), payload, changed_paths(event, payload)
        )
    print(json.dumps({"profile": selected, "reason": reason}))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"profile={selected}\n")
    return int(bool(payload.get("deleted")))


if __name__ == "__main__":
    raise SystemExit(main())
