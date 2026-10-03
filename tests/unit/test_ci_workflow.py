# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kicad-10 and kicad-9 oracle jobs, checked textually (capability ci-baseline; the dev extra has no YAML
parser)."""

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
    ("corpus fetch", "run: uv run python tools/corpus_fetch.py --uses rt0 --uses libs --exclude-uses heavy"),
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
    fetches = [line for line in job.splitlines() if "tools/corpus_fetch.py" in line]
    if not any("--uses libs" in line for line in fetches):
        problems.append("kicad-10: the corpus fetch must pass --uses libs (the demo library rows)")
    if not any("--exclude-uses heavy" in line for line in fetches):
        problems.append("kicad-10: the corpus fetch must pass --exclude-uses heavy")
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


def test_library_rows_not_fetched() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").replace("--uses rt0 --uses libs ", "--uses rt0 ")
    assert "kicad-10: the corpus fetch must pass --uses libs (the demo library rows)" in job_problems(text)


def test_unit_job_untouched() -> None:
    assert "run: uv run pytest -q" in job_text(WORKFLOW.read_text(encoding="utf-8"), "unit")


KICAD9_FETCH = "run: uv run python tools/corpus_fetch.py --uses rt2-9"
KICAD9_KEY = "key: corpus-rt2-9-${{ hashFiles('tests/corpus/manifest.toml') }}"
KICAD9_STEPS = [
    ("kicad-cli version", "run: kicad-cli version"),
    ("uv sync", "run: uv sync --locked --extra dev"),
    ("corpus cache", "uses: actions/cache"),
    ("corpus fetch", KICAD9_FETCH),
    ("pytest", "run: uv run pytest tests/kicad -q -rA"),
]


def kicad9_problems(workflow: str) -> list[str]:
    job = job_text(workflow, "kicad-9")
    if not job:
        return ["kicad-9: job missing"]
    problems: list[str] = []
    if not re.search(r"image: kicad/kicad:9\.0\.9@sha256:[0-9a-f]{64}\s*$", job, re.MULTILINE):
        problems.append("kicad-9: image must be kicad/kicad:9.0.9 pinned by @sha256 index digest")
    if not re.search(r"^\s+options: --user 0\s*$", job, re.MULTILINE):
        problems.append("kicad-9: container options must be --user 0")
    positions = [(name, job.find(marker)) for name, marker in KICAD9_STEPS]
    problems += [f"kicad-9: step {name!r} missing" for name, at in positions if at < 0]
    present = [(n, p) for n, p in positions if p >= 0]
    for (first, p1), (second, p2) in zip(present, present[1:], strict=False):
        if p2 < p1:
            problems.append(f"kicad-9: step {second!r} must come after {first!r}")
    if not re.search(r"FENOLITE_REQUIRE: kicad\s*$", job, re.MULTILINE):
        problems.append("kicad-9: pytest must run with FENOLITE_REQUIRE=kicad")
    if KICAD9_KEY not in job:
        problems.append("kicad-9: cache key must be corpus-rt2-9-<hash of tests/corpus/manifest.toml>")
    if "FENOLITE_CORPUS_CACHE:" not in job:
        problems.append("kicad-9: FENOLITE_CORPUS_CACHE must name the cached folder")
    fetches = re.findall(r"run: uv run python tools/corpus_fetch\.py.*", job)
    if fetches != [KICAD9_FETCH]:
        problems.append("kicad-9: its only corpus fetch must be --uses rt2-9")
    return problems


def test_kicad_9_job() -> None:
    problems = kicad9_problems(WORKFLOW.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_both_kicad_jobs_run_tests_kicad() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for job in ("kicad-9", "kicad-10"):
        assert re.search(r"run: uv run pytest tests/kicad\b", job_text(text, job)), job


def test_every_kicad_image_is_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    references = re.findall(r"kicad/kicad:\S+", text)
    assert references and all(re.fullmatch(r"kicad/kicad:[0-9.]+@sha256:[0-9a-f]{64}", r) for r in references)


def test_unpinned_kicad_9_rejected() -> None:
    text = re.sub(
        r"kicad/kicad:9\.0\.9@sha256:[0-9a-f]{64}", "kicad/kicad:9.0", WORKFLOW.read_text(encoding="utf-8")
    )
    assert any(p.startswith("kicad-9: image") for p in kicad9_problems(text))


def test_kicad_9_wider_fetch_rejected() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").replace("--uses rt2-9", "--uses rt0")
    problems = kicad9_problems(text)
    assert any(p.startswith("kicad-9:") and "rt2-9" in p for p in problems)


def test_kicad_9_cache_key_and_order() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    other_key = text.replace("corpus-rt2-9-", "corpus-")
    assert any("cache key" in p for p in kicad9_problems(other_key))
    job = job_text(text, "kicad-9")
    assert (
        job.find("uses: actions/cache") < job.find(KICAD9_FETCH) < job.find("run: uv run pytest tests/kicad")
    )
    assert "corpus-rt2-9-" not in job_text(text, "kicad-10")  # the two jobs never share a cache key
