# Releasing Fenolite

A release is a tag. Pushing `vX.Y.Z` runs `.github/workflows/release.yml`, which checks, builds, publishes
`fenolite` and its alias `phenolite` to PyPI and creates the GitHub Release (change c0221).

## Steps

1. On the release branch, set the version in `src/fenolite/__init__.py` and in
   `packaging/phenolite/pyproject.toml` (its `version` and the `fenolite==` pin), move the entries of
   `## [Unreleased]` of `CHANGELOG.md` under `## [X.Y.Z] - <date>`, and write `docs/release/vX.Y.md`.
2. Merge the release into `main` once its checks pass.
3. Tag the merge commit and push the tag:

   ```sh
   git fetch origin main
   git tag -a vX.Y.Z origin/main -m "Fenolite X.Y.Z"
   git push origin vX.Y.Z
   ```

   Or, without a terminal: **Actions » release » Run workflow**, tag `vX.Y.Z`, with *create tag* on: the
   run tags the head of `main`.

## What the workflow does

| job | what |
|---|---|
| `build` | the tagged commit must be on `main`; `tools/release.py check` refuses the tag unless the two versions, the alias pin and a `## [X.Y.Z]` changelog section agree; builds both packages from the tag; residue scan; `twine check --strict`; installs the wheel alone and checks `fenolite --version` |
| `publish` | PyPI trusted publishing (environment `pypi`, no token stored); skipped when PyPI already holds the version |
| `github-release` | the release `Fenolite X.Y.Z`: install lines, links to the release record, the diff and the changelog, the changelog section, the files PyPI serves (checked against PyPI's SHA-256) and `SHA256SUMS`; latest for the highest final version, pre-release for a version with a suffix |

A failed check stops the run before anything is published. Running the workflow again for the same tag
(by hand) uploads nothing that PyPI holds and edits the existing release page, so a release page that is
missing or wrong is fixed by running it again.

## PyPI

Each project name (`fenolite`, `phenolite`) has a trusted publisher: owner `lgili`, repository
`Fenolite`, workflow `release.yml`, environment `pypi`. Renaming the workflow file or the environment
breaks publishing until the publishers are updated on PyPI.
