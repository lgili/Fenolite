# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kicad-10 and kicad-9 oracle jobs, checked textually (capability ci-baseline; the dev extra has no YAML
parser)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARALLEL = "-n auto --dist loadfile"
"""The pytest-xdist options of every pytest step (capability ci-baseline, "Parallel test runs")."""
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
KICAD10_PYTEST = f"run: uv run pytest tests/kicad tests/corpus -q {PARALLEL}"
UNIT_PYTEST = f"run: uv run pytest -q {PARALLEL}"


def pytest_steps(job: str) -> list[str]:
    """The ``run:`` lines of a job that call pytest, stripped."""
    return [line.strip() for line in job.splitlines() if line.strip().startswith("run: uv run pytest")]


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
    if pytest_steps(job) != [KICAD10_PYTEST]:
        problems.append(f"kicad-10: the pytest step must end with {PARALLEL}")
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


def test_serial_kicad_10_step_rejected() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").replace(KICAD10_PYTEST, KICAD10_PYTEST[: -len(PARALLEL) - 1])
    assert f"kicad-10: the pytest step must end with {PARALLEL}" in job_problems(text)


def test_unit_job_runs_in_parallel() -> None:
    assert pytest_steps(job_text(WORKFLOW.read_text(encoding="utf-8"), "unit")) == [UNIT_PYTEST]


KICAD9_FETCH = "run: uv run python tools/corpus_fetch.py --uses rt2-9"
KICAD9_KEY = "key: corpus-rt2-9-${{ hashFiles('tests/corpus/manifest.toml') }}"
KICAD9_STEPS = [
    ("kicad-cli version", "run: kicad-cli version"),
    ("uv sync", "run: uv sync --locked --extra dev"),
    ("corpus cache", "uses: actions/cache"),
    ("corpus fetch", KICAD9_FETCH),
    ("pytest", "run: uv run pytest tests/kicad -q -rA"),
]
KICAD9_PYTEST = f"run: uv run pytest tests/kicad -q -rA {PARALLEL}"


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
    if pytest_steps(job) != [KICAD9_PYTEST]:
        problems.append(f"kicad-9: the pytest step must end with {PARALLEL}")
    if "FENOLITE_CORPUS_CACHE:" not in job:
        problems.append("kicad-9: FENOLITE_CORPUS_CACHE must name the cached folder")
    fetches = re.findall(r"run: uv run python tools/corpus_fetch\.py.*", job)
    if fetches != [KICAD9_FETCH]:
        problems.append("kicad-9: its only corpus fetch must be --uses rt2-9")
    return problems


def test_kicad_9_job() -> None:
    problems = kicad9_problems(WORKFLOW.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)


def test_serial_kicad_9_step_rejected() -> None:
    text = WORKFLOW.read_text(encoding="utf-8").replace(KICAD9_PYTEST, KICAD9_PYTEST[: -len(PARALLEL) - 1])
    assert f"kicad-9: the pytest step must end with {PARALLEL}" in kicad9_problems(text)


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


def test_routing_job_runs_pinned_tool_and_oracle_loop() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    job = job_text(text, "routing")
    assert "kicad/kicad:9.0.9@sha256:" in job and "kicad/kicad:10.0.6@sha256:" in job
    assert "--branch v0.22.1" in job
    assert "grid_router-linux-x86_64.so" in job
    assert "sha256sum --check" in job
    assert "FENOLITE_REQUIRE: kicad,router" in job
    assert "run: uv run pytest tests/routing -q -rA" in job


JAR_URL = "https://github.com/freerouting/freerouting/releases/download/v{0}/freerouting-{0}.jar"
JAR_CHECK = re.compile(r"echo '([0-9a-f]{64})  (\S+freerouting-([\d.]+)\.jar)' \| sha256sum --check")


def freerouting_problems(workflow: str, pinned: str) -> list[str]:
    """Problems of the Freerouting steps of the ``routing`` job against the plugin's pinned version
    (capability ci-baseline, "Freerouting in the routing job"; change c0023)."""
    job = job_text(workflow, "routing")
    problems: list[str] = []
    downloads = re.findall(r"releases/download/v([\d.]+)/freerouting-([\d.]+)\.jar", job)
    if not downloads:
        problems.append("the routing job downloads no Freerouting jar from its release page")
    for tag, name in downloads:
        if (tag, name) != (pinned, pinned):
            problems.append(f"ci.yml downloads Freerouting {tag} ({name}); the plugin pins {pinned}")
    check = JAR_CHECK.search(job)
    if check is None:
        problems.append("the routing job does not verify the jar against a 64-hex SHA-256")
    elif check.group(3) != pinned:
        problems.append(f"ci.yml verifies Freerouting {check.group(3)}; the plugin pins {pinned}")
    jar = re.search(r"FENOLITE_FREEROUTING_JAR: (\S+)", job)
    if jar is None:
        problems.append("the routing job does not set FENOLITE_FREEROUTING_JAR")
    elif check is not None and jar.group(1) != check.group(2):
        problems.append("FENOLITE_FREEROUTING_JAR does not name the verified jar")
    required = re.search(r"FENOLITE_REQUIRE: (\S+)", job)
    if required is None or "freerouting" not in required.group(1).split(","):
        problems.append("FENOLITE_REQUIRE of the routing job does not list freerouting")
    if "actions/setup-java" not in job or 'java-version: "25"' not in job:
        problems.append("the routing job does not install Java 25")
    if check is not None and job.find("sha256sum --check", check.start()) > job.find("run: uv run pytest"):
        problems.append("the jar is verified after the tests run")
    return problems


def test_routing_job_installs_the_pinned_freerouting() -> None:
    """Scenario "Workflow shape checked"."""
    from fenolite.routing.plugins.specctra.freerouting import JAVA_MIN, PINNED_VERSION

    text = WORKFLOW.read_text(encoding="utf-8")
    assert freerouting_problems(text, PINNED_VERSION) == []
    assert JAR_URL.format(PINNED_VERSION) in job_text(text, "routing")
    assert JAVA_MIN == 25
    assert "run: uv run pytest tests/routing -q -rA" in job_text(text, "routing")


def test_freerouting_version_drift_is_caught() -> None:
    """Scenario "Version drift caught": both values are named."""
    text = WORKFLOW.read_text(encoding="utf-8")
    problems = freerouting_problems(text, "2.5.0")
    assert problems and all("2.4.1" in problem and "2.5.0" in problem for problem in problems)


def test_freerouting_steps_missing_or_unverified() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    unverified = re.sub(r"\n +echo '[0-9a-f]{64}  \S+freerouting\S+' \| sha256sum --check", "", text)
    assert "the routing job does not verify the jar against a 64-hex SHA-256" in freerouting_problems(
        unverified, "2.4.1"
    )
    no_variable = text.replace("FENOLITE_FREEROUTING_JAR: ", "SOMETHING_ELSE: ")
    assert "the routing job does not set FENOLITE_FREEROUTING_JAR" in freerouting_problems(
        no_variable, "2.4.1"
    )
    not_required = text.replace(
        "FENOLITE_REQUIRE: kicad,router,freerouting", "FENOLITE_REQUIRE: kicad,router"
    )
    assert "FENOLITE_REQUIRE of the routing job does not list freerouting" in freerouting_problems(
        not_required, "2.4.1"
    )
