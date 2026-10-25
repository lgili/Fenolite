## 0. Entry check

- [x] 0.1 Pin the Chromium and font versions of the CI image; record them. Proof: `openspec validate c0191-viewer-visual-tests --strict --no-interactive`.
  - 2026-10-25: the container has Ubuntu 24.04, Node 22.22.0 and Node's Playwright 1.63.0, whose Chromium is 153.0.8010.12. Its fonts include many families beside DejaVu (`fonts-dejavu-core` 2.37-8).
  - **Pins:** the CI job `viewer` runs on `ubuntu-24.04` and installs `playwright@1.63.0` (a Playwright version pins its Chromium build) and `fonts-dejavu-core` (2.37-8 on that release).
  - **Fonts:** the harness starts Chromium with `FONTCONFIG_FILE=tests/visual/fonts.conf`, which loads DejaVu alone and maps every family to DejaVu Sans. Every text then renders the same here and in CI (design, decision 3).
  - Branch `c0191-visual-tests`, from `c0190-documentation-views`. Proof passed.

## 1. Tests

- [x] 1.1 Fixtures and the screenshot harness (scenario "A changed colour fails"). Proof: `uv run pytest tests/visual -q`.
  - 2026-10-25: proof passed.
  - **Fixtures:** eight, one per scene kind: KiCad board, Altium board, Altium sheet, KiCad sheet, footprint library, symbol library, Draftsman drawing and output job. They are authored files of `tests/data` or built from the tests' own data (the c0180 drawing, an output job).
  - **Pages:** each is written by `fenolite view … --export` (dry run, then the plan) and drawn at 1 100 × 700 px. The 8 references weigh 567 kB.
  - **Comparison:** done in the browser by `tests/visual/harness.js`: a channel differing by more than 2 levels; at most 0.1 % of the pixels.
  - **Stability:** two runs gave 0 differing pixels against the references.
  - **Scenario:** with the sheet colour changed, the test fails and writes the difference image.
  - **Fixed on the way:** a lone `.OutJob` or `.BomDoc` can now be opened by `fenolite view` (`view/project.py`), as a lone drawing could.
- [x] 1.2 Interaction tests. Proof: `uv run pytest tests/visual -q`.
  - 2026-10-25: proof passed (13 with 1.1).
  - Mouse and key events on the canvas of the `blink` project's page check four things: a click selects a pad and its part; `M` and two clicks measure between the two pad centres they snap to; `Q` switches to mil; a double-click on U1 on the board opens the sheet with U1 selected.
- [x] 1.3 CI job and `tools/update_view_refs.py`. Proof: the job's run on the branch.
  - 2026-10-25: the `viewer` job of `.github/workflows/ci.yml` runs `pytest tests/visual` with `FENOLITE_REQUIRE=browser` and keeps the screenshots and difference images as the artefact `viewer-differences` on a failure.
  - `tools/update_view_refs.py [NAME…]` rewrote the references.
  - `make visual` runs the tests. `make check-fast` does not collect `tests/visual`; the `unit` job does, and skips them where Playwright is absent.
  - 2026-10-25: proof passed. The CI run 40192579411 on commit `b556df4` ran the `viewer` job to success: Playwright 1.63.0 and its Chromium on `ubuntu-24.04`, with `FENOLITE_REQUIRE=browser`, so no test could skip. The references made in the container hold on the runner.

## 2. Closing

- [x] 2.1 Docs (`CONTRIBUTING.md`), fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 948 passed, 34 skipped).
  - Changed: `CONTRIBUTING.md` ("The viewer's visual tests"), the `needs_browser` marker in `pyproject.toml` and `tests/conftest.py`, and the LEGAL-ANNEX row.
