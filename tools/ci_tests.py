# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Run file-preserving CI partitions and audit exact-commit coverage receipts (c0380)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "fenolite.ci-tests.v1"
UNIT_LABELS = (
    "ubuntu-latest-py3.11",
    "ubuntu-latest-py3.12",
    "ubuntu-latest-py3.13",
    "macos-latest-py3.12",
    "windows-latest-py3.12",
)
FULL = {
    **{f"unit-{label}": 1 for label in UNIT_LABELS},
    "kicad-10": 4,
    "kicad-9": 1,
    "routing-9": 1,
    "routing-10": 1,
    "viewer": 1,
    "mcp": 1,
}


def selection(suite: str) -> list[str]:
    if suite.startswith("unit-") and suite in FULL:
        return []  # Deliberately keep the old whole-suite unit baseline, including declared skips.
    return {
        "fast": [
            "tests/unit",
            "tests/residue",
            "tests/consistency",
            "tests/fidelity",
            "-m",
            "not needs_kicad and not needs_corpus and not needs_libs and not long_flow",
        ],
        "kicad-10": [],  # The plugin keeps all native tests plus whole resource-bearing unit files.
        "kicad-9": ["tests/kicad"],
        "routing-9": ["tests/routing"],
        "routing-10": ["tests/routing"],
        "viewer": ["tests/visual"],
        "mcp": ["tests/unit/mcp", "tests/unit/cli/test_mcp_cmd.py"],
    }[suite]


def slot(file: str, count: int) -> int:
    return int.from_bytes(hashlib.sha256(file.encode("utf-8")).digest()[:8], "big") % count


def partition(items: list[dict], shard: int, count: int) -> list[dict]:
    if count < 1 or not 0 <= shard < count:
        raise ValueError("invalid shard index/count")
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("duplicate node ids in baseline collection")
    return [item for item in items if slot(item["file"], count) == shard]


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def audit(reports: list[dict], expected: dict[str, int], commit: str) -> list[str]:
    problems: list[str] = []
    identities = Counter((r.get("suite"), r.get("shard")) for r in reports)
    required = {(suite, shard) for suite, count in expected.items() for shard in range(count)}
    if set(identities) != required or any(n != 1 for n in identities.values()):
        problems.append("missing, duplicate or unexpected suite/shard receipts")
    for suite, count in expected.items():
        group = [r for r in reports if r.get("suite") == suite]
        if not group:
            continue
        baseline = group[0].get("baseline", [])
        if not baseline:
            problems.append(f"{suite}: empty full collection")
        seen: Counter[str] = Counter()
        for report in group:
            if (
                report.get("schema") != SCHEMA
                or report.get("commit") != commit
                or report.get("shards") != count
                or report.get("baseline") != baseline
            ):
                problems.append(f"{suite}: inconsistent schema, commit, partition count or baseline")
                continue
            try:
                planned = partition(baseline, report["shard"], count)
            except (ValueError, KeyError, TypeError):
                problems.append(f"{suite}: invalid partition")
                continue
            outcomes = report.get("outcomes", {})
            ids = {item["id"] for item in planned}
            if (
                report.get("selected") != planned
                or set(outcomes) != ids
                or any(v not in {"passed", "skipped"} for v in outcomes.values())
                or report.get("exit_code") != 0
            ):
                problems.append(f"{suite}/{report['shard']}: collection/outcomes incomplete or failed")
            seen.update(item["id"] for item in report.get("selected", []))
        if seen != Counter(item["id"] for item in baseline):
            problems.append(f"{suite}: partition union is not the complete disjoint baseline")
    unit_suite = "unit-ubuntu-latest-py3.12"
    if unit_suite in expected and "kicad-10" in expected:
        unit = next((r for r in reports if r.get("suite") == unit_suite), {})
        native = [r for r in reports if r.get("suite") == "kicad-10"]
        unit_items = unit.get("baseline", [])
        if any("resources" not in item for item in unit_items):
            problems.append("unit inventory: missing resource metadata for native cross-audit")
        files = {i["file"] for i in unit_items if i["file"].startswith("tests/unit/") and i.get("resources")}
        required = {i["id"] for i in unit_items if i["file"] in files}
        native_ids = {i["id"] for r in native for i in r.get("baseline", [])}
        if not required <= native_ids:
            problems.append("kicad-10: resource-bearing unit files are missing from native baseline")
        outcomes = {node: value for r in native for node, value in r.get("outcomes", {}).items()}
        if any(
            outcomes.get(i["id"]) != "passed"
            for i in unit_items
            if i["id"] in required and i.get("resources")
        ):
            problems.append("kicad-10: resource-marked unit cases must pass, not skip or remain missing")
    return problems


def run(suite: str, shard: int, count: int, out: Path, workers: str) -> int:
    out.mkdir(parents=True, exist_ok=True)
    collect_path, plan_path, receipt = out / "collection.json", out / "plan.json", out / "receipt.json"
    # Clear prior evidence before preflight: refused options and Git failures must not preserve
    # a previous success or a stale diagnostic JUnit file for the always-kept artifact step.
    for path in (collect_path, plan_path, receipt, out / "junit.xml"):
        path.unlink(missing_ok=True)
    if os.environ.get("PYTEST_ADDOPTS"):
        raise ValueError("CI baselines refuse implicit PYTEST_ADDOPTS filters/options")
    targets = selection(suite)
    allowed_counts = (1, 3) if suite == "fast" else (FULL[suite],)
    if count not in allowed_counts:
        raise ValueError(f"{suite} requires shard count in {allowed_counts}")
    partition([], shard, count)
    # Container users can differ from checkout ownership. Trust only this checkout for this
    # invocation, and retain actual HEAD identity rather than substituting GITHUB_SHA blindly.
    commit = subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "tools"), str(ROOT), os.environ.get("PYTHONPATH", ""))),
        "CI_RECEIPT_PLAN": str(plan_path),
        "CI_RECEIPT_MODE": "collect",
        "CI_RECEIPT_SUITE": suite,
        "CI_RECEIPT_OUT": str(collect_path),
    }
    save(plan_path, {})
    command = [sys.executable, "-m", "pytest", "-p", "ci_receipt"]
    started = time.monotonic()
    with (out / "collection.log").open("w", encoding="utf-8") as stream:
        code = subprocess.call(
            [*command, *targets, "--collect-only", "-q"],
            cwd=ROOT,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
    collection_seconds = time.monotonic() - started
    if code:
        print((out / "collection.log").read_text(encoding="utf-8", errors="replace")[-8000:])
        return code
    collection = json.loads(collect_path.read_text(encoding="utf-8"))["items"]
    if not collection:
        raise ValueError("full baseline collection is empty")
    chosen = partition(collection, shard, count)
    plan = {
        "schema": SCHEMA,
        "suite": suite,
        "shard": shard,
        "shards": count,
        "commit": commit,
        "baseline": collection,
        "selected": chosen,
        "collection_seconds": collection_seconds,
    }
    save(plan_path, plan)
    print(
        f"{suite}: {len(collection)} baseline nodes; shard {shard}/{count}: {len(chosen)} nodes", flush=True
    )
    if not chosen:
        save(receipt, {**plan, "outcomes": {}, "exit_code": 0})
        return 0
    env.update(CI_RECEIPT_MODE="run", CI_RECEIPT_OUT=str(receipt))
    files = sorted({item["file"] for item in chosen})
    marker_args = targets[targets.index("-m") :] if "-m" in targets else []
    # Preserve the legacy root selection when unsharded. Enumerating 1600+ files would exceed
    # Windows' command-line limit; only the four Linux partitions need explicit file arguments.
    execution_args = targets if count == 1 else [*files, *marker_args]
    started = time.monotonic()
    code = subprocess.call(
        [
            *command,
            *execution_args,
            "-q",
            "-n",
            workers,
            "--dist",
            "loadfile",
            "--no-loadscope-reorder",
            *(["-rA"] if suite == "kicad-9" or suite.startswith("routing-") else []),
            "--durations=30",
            "--junitxml",
            str(out / "junit.xml"),
            "--basetemp",
            str(out / "tmp"),
        ],
        cwd=ROOT,
        env=env,
    )
    if not receipt.exists():
        return code or 1
    data = json.loads(receipt.read_text(encoding="utf-8"))
    data["execution_seconds"] = time.monotonic() - started
    save(receipt, data)
    return code or data["exit_code"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--suite", choices=[*FULL, "fast"], required=True)
    run_parser.add_argument("--shard", type=int, default=0)
    run_parser.add_argument("--shards", type=int, default=1)
    run_parser.add_argument("--out", type=Path, required=True)
    run_parser.add_argument("--workers", default="auto")
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("folder", type=Path)
    audit_parser.add_argument("--commit", required=True)
    audit_parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "run":
            return run(args.suite, args.shard, args.shards, args.out.resolve(), args.workers)
        reports = [json.loads(p.read_text(encoding="utf-8")) for p in args.folder.rglob("receipt.json")]
        problems = audit(reports, {"fast": 3} if args.fast else FULL, args.commit)
        print("\n".join(problems) if problems else f"coverage passed: {len(reports)} complete receipts")
        return int(bool(problems))
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(f"CI receipt error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
