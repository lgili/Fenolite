## Context

`release.yml` (c0154, c0171) builds both distributions and publishes them with PyPI trusted publishing
when a GitHub Release is published or by hand. Release pages for 0.1.0 to 0.4.0 were written by hand
(the body of 0.4.0 names the run, the PyPI files and the release record). `v0.5.0` points to `3a0bfb7d`,
the merge of the release pull request on `main`; PyPI holds 0.5.0 from run 2026-10-26.

## Decisions

1. **The tag is the trigger.** A pushed `v*.*.*` starts the run; a published GitHub Release no longer
   does (the workflow creates it, and a release made with the workflow's token would start nothing
   anyway). By hand, the run takes a tag and, with `create_tag`, tags the head of `main` through the
   REST API when the tag is missing, so a release can be made from the Actions page alone.
2. **Tools from the workflow's ref, sources from the tag.** Each job checks out its own ref into
   `tooling/` and the tag into `source/`. For a pushed tag both are the same commit; a manual run can
   release an older tag with the current tools (the case of `v0.5.0`, whose commit has no
   `tools/release.py`).
3. **Checks before anything is published.** The tagged commit must be an ancestor of `origin/main`; the
   versions, the alias pin and the changelog section must agree with the tag (`release.py check`); the
   metadata must pass `twine check --strict`; the wheel, installed alone in a fresh environment, must
   print `fenolite X.Y.Z`; the residue scan runs on the tagged sources.
4. **The published bytes are the attached bytes.** After `publish`, `release.py pypi-files` downloads the
   files PyPI serves for the version, checks each against PyPI's SHA-256 and attaches those. For a
   version already on PyPI, `publish` is skipped and nothing is rebuilt into PyPI. When PyPI does not
   answer yet, the built files (the same that were uploaded) stay.
5. **Notes from the changelog.** `release.py notes` writes the title, the PyPI links, the install lines,
   links to the release record (`docs/release/vX.Y.md` when it exists), the diff from the previous final
   tag on the tag's history and the changelog, the changelog section as is, and a table of the files and
   their SHA-256. A body over GitHub's 125 000 characters is cut at a line with a link to the changelog.
6. **Latest and pre-release.** Latest only when the tag is the highest final version among the tags;
   a version with a pre-, dev- or post-release suffix is a pre-release and never latest.
7. **Idempotent.** An existing release is edited and its files replaced (`--clobber`), so a run made
   again ends in the same page.

## Risks

- PyPI's JSON can lag right after an upload; the built files are then attached (identical to the
  uploaded ones). A later manual run attaches PyPI's.
- The `pypi` environment's protection rules apply to `publish` only; `github-release` needs
  `contents: write`.
