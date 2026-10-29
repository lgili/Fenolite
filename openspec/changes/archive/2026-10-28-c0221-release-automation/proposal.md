## Why

Releases are made by hand. Version 0.5.0 reached PyPI through a manual run of `release.yml`
(2026-10-26), and no GitHub Release was made for it: `v0.5.0` is the only tag without one. The workflow
starts on a *published GitHub Release* or by hand, so the order of steps (tag, release page, PyPI) is the
maintainer's to remember, and the release page is written by hand each time.

The maintainer's request of 2026-10-28: the release must run when a tag is pushed, publish to PyPI
automatically and create a professional GitHub Release; and the missing release must be published.

## What Changes

- `.github/workflows/release.yml` starts on a pushed tag `v*.*.*` (and by hand with a tag, optionally
  creating it on the head of `main`). It no longer starts on a published GitHub Release.
- Job `build`: the tagged commit must be on `main`; `tools/release.py check` refuses the tag unless
  `fenolite.__version__`, the alias version and pin, and a `## [X.Y.Z]` section of `CHANGELOG.md` agree;
  both packages are built from the tagged commit; residue scan; `twine check --strict`; the wheel is
  installed alone and must report the tag's version.
- Job `publish`: PyPI trusted publishing as before (`skip-existing`), skipped when PyPI already holds the
  version.
- Job `github-release`: creates (or updates) the GitHub Release `Fenolite X.Y.Z` from the existing tag,
  with notes written by `tools/release.py notes` (install lines, links to the release record, the diff
  and the changelog, the changelog section, a table of files with their SHA-256), the files PyPI serves
  for the version checked against PyPI's digests, and `SHA256SUMS`; it marks the release latest only for
  the highest final version and a pre-release for a version with a suffix.
- `tools/release.py` (standard library only) and its tests; `docs/releasing.md`.
- The GitHub Release of `v0.5.0` is created by a manual run of the new workflow.

## Capabilities

### Modified Capabilities
- `release-gate`: ADDED "Release from a tag", "Release notes and files", "Release made again".

## Impact

- `.github/workflows/release.yml`, `tools/release.py`, `tests/unit/test_release_tool.py`,
  `tests/unit/test_ci_workflow.py`, `docs/releasing.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
- No product code changes. PyPI's trusted publishers stay as registered (workflow `release.yml`,
  environment `pypi`).
