# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kicad-10 oracle job, checked textually (capability ci-baseline; the dev extra has no YAML parser)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
STEPS = [
    ("checkout", "uses: actions/checkout@v4"),
    ("setup-uv", "uses: astral-sh/setup-uv"),
    ("kicad-cli version", "run: kicad-cli version"),
    ("uv sync", "run: uv sync --locked --extra dev"),
    ("corpus cache", "uses: actions/cache"),
    ("corpus fetch", "run: uv run python tools/corpus_fetch.py --uses rt0 --exclude-uses heavy"),
    ("pytest", "run: uv run pytest tests/kicad tests/corpus -q"),
]


def job_text(workflow: str, name: str) -> str:
    """The lines of one job under ``jobs:`` (until the next job at the same indentation)."""
    match = re.search(rf"^  {re.escape(name)}:\n(.*?)(?=^  \S|\Z)", workflow, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def job_problems(workflow: str) -> list[str]:
    job = job_text(workflow, "kicad-10")
    if not job:
        return ["kicad-10: job missing"]
    problems: list[str] = []
    if not re.search(r"image: kicad/kicad:10\.0\.6@sha256:[0-9a-f]{64}\s*$", job, re.MULTILINE):
        problems.append("kicad-10: image must be kicad/kicad:10.0.6 pinned by @sha256 index digest")
    if not re.search(r"^\s+options: --user 0\s*$", job, re.MULTILINE):
        problems.append("kicad-10: container options must be --user 0")
    if "runs-on: ubuntu-latest" not in job:
        problems.append("kicad-10: must run on ubuntu-latest")
    positions = [(name, job.find(marker)) for name, marker in STEPS]
    for name, position in positions:
        if position < 0:
            problems.append(f"kicad-10: step {name!r} missing")
    present = [(n, p) for n, p in positions if p >= 0]
    for (first, p1), (second, p2) in zip(present, present[1:], strict=False):
        if p2 < p1:
            problems.append(f"kicad-10: step {second!r} must come after {first!r}")
    if "key: corpus-${{ hashFiles('tests/corpus/manifest.toml') }}" not in job:
        problems.append("kicad-10: cache key must hash tests/corpus/manifest.toml")
    if not re.search(r"FENOLITE_REQUIRE: kicad,corpus", job):
        problems.append("kicad-10: pytest must run with FENOLITE_REQUIRE=kicad,corpus")
    return problems


def test_kicad_10_job() -> None:
    problems = job_problems(WORKFLOW.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_unpinned_image_rejected() -> None:
    text = re.sub(
        r"kicad/kicad:10\.0\.6@sha256:[0-9a-f]{64}", "kicad/kicad:10.0", WORKFLOW.read_text(encoding="utf-8")
    )
    assert any(p.startswith("kicad-10: image") for p in job_problems(text))


def test_steps_out_of_order() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    job = job_text(text, "kicad-10")
    swapped = (
        job.replace("run: kicad-cli version", "run: @@KICAD@@")
        .replace("run: uv sync --locked --extra dev", "run: kicad-cli version")
        .replace("run: @@KICAD@@", "run: uv sync --locked --extra dev")
    )
    problems = job_problems(text.replace(job, swapped))
    assert "kicad-10: step 'uv sync' must come after 'kicad-cli version'" in problems


def test_unit_job_untouched() -> None:
    assert "run: uv run pytest -q" in job_text(WORKFLOW.read_text(encoding="utf-8"), "unit")
