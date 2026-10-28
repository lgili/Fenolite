## 1. Tool and workflow

- [x] 1.1 Write `tools/release.py` (`check`, `notes`, `latest`, `pypi-files`) with the standard library only, and its tests. Proof: `uv run pytest tests/unit/test_release_tool.py -q`.
  - 2026-10-28: 9 passed. On the tag `v0.5.0` (a worktree of it): `check` agrees; `uv build` of both packages, `twine check --strict` PASSED for the four files, the wheel installed alone prints `fenolite 0.5.0`; `pypi-files` fetched the four files of 0.5.0 from PyPI, each matching its digest; `notes` gives 62 867 characters; `latest` prints `true`.
- [x] 1.2 Rewrite `.github/workflows/release.yml` (Decisions 1 to 7) and guard it in `tests/unit/test_ci_workflow.py`. Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`.
  - 2026-10-28: `test_release_flow` and `test_release_publish_skips_existing_versions`; 43 passed.
- [x] 1.3 Document the release in `docs/releasing.md`, link it from `CONTRIBUTING.md`, add the changelog entry. Proof: `uv run pytest tests/consistency -q`; `make check-fast`.
  - 2026-10-28: `docs/releasing.md`, the section "Releases" of `CONTRIBUTING.md`, the `### Changed` entry under Unreleased and the row c0210 of `openspec/README.md`. `make check-fast PYTEST_WORKERS=3`: 14235 passed, 39 skipped; the five generators and strict validation (0 errors) pass.

## 2. The missing release

- [ ] 2.1 Run the workflow by hand for `v0.5.0` (PyPI holds it, so nothing is uploaded) and check the release page: title, notes, the four files with PyPI's digests and `SHA256SUMS`, latest. Proof: `gh api repos/lgili/Fenolite/releases/tags/v0.5.0` shows the release with five assets.
