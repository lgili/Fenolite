## 0. Investigation

- [x] 0.1 Reproduce the failure as root with the pinned 10.0.6 image through `DockerCli`, and read what the image needs: its user, its `HOME`, what `kicad-cli` writes outside `KICAD_CONFIG_HOME`. Proof: `design.md`, Context.
  - **2026-10-09.** As root, `DockerCli("kicad/kicad:10.0.6").drc(two_layer.kicad_pcb)` printed "Directory '/w/config' couldn't be created (error 13: Permission denied)", exit 3, no report. The image runs as `kicad` (1000:1000) with `HOME=/home/kicad` (0700); an unknown `--user` gets `HOME=/`, where both majors cannot create `.cache` and `.local`.

## 1. Facts first

- [x] 1.1 The command row and two rows of facts in `docs/formats/kicad/cli.md` ("Refill on a copy", "Per-run state"); S-0727 in `docs/evidence/sources.md` (read 2026-10-09). Proof: `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py -q`.
  - **2026-10-09.** Passed.

## 2. Runner

- [x] 2.1 `DOCKER_HOME`, `docker_rootless`, `docker_user`, `DockerCli.user`; `DockerCli._command` passes `--user` and `HOME` and makes the home folder. Tests in `tests/unit/backends/kicad/test_docker_cli.py`; the local test `tests/kicad/fill/test_docker_cli.py::test_container_writes_the_callers_run_folder` (skips without Docker or the image). Proof: `uv run pytest tests/unit/backends/kicad/test_docker_cli.py tests/unit/test_kicad_probes.py tests/kicad/fill/test_docker_cli.py -q`; `uv run pyright src`.
  - **2026-10-09.** Passed, the local test included (host user root, Docker 29.8.2, image `kicad/kicad:10.0.6@sha256:18693567…`; before the fix the same run gave exit 3 and no report); the same `drc` through `DockerCli("kicad/kicad:9.0.9@…")` exits 0 with a report.

## 3. Closing

- [x] 3.1 Run tests/residue. Proof: `uv run pytest tests/residue -q`.
- [x] 3.2 Update evidence labels: the measured row is `KICAD-VERIFIED (9.0.x, 10.0.x)`, the rootless row `INFERRED`; `H-K-CLI-DOCKER` keeps its label (it is about refill parity). Proof: `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 3.3 `CHANGELOG.md` under `[Unreleased]`, `### Fixed`; `openspec/README.md` row. Proof: `make check-fast PYTEST_WORKERS=2`.
