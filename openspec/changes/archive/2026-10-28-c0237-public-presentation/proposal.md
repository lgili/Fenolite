## Why

Fenolite 0.5.0 is released, but its landing page still describes shipped viewer functionality as future work. Repository discovery metadata is empty and the README has no product screenshots. New users need a clear explanation, a reproducible first experience and a concise account of supported workflows.

## What Changes

- Rewrite the English README around shipped workflows, installation, real product screenshots and a short getting-started path.
- Add a documentation landing page, quickstart and a ready-to-review bilingual launch kit with repository metadata, social preview, release copy and a publication checklist.
- Capture screenshots and a short animated demonstration from Fenolite-authored examples using the released viewer, with source and reproduction instructions. Create an original social card from these captures.
- Update package description and documentation links to match current capabilities, retaining experimental Altium and conversion limits.
- Open the post-release development version as 0.6.0.dev0, matching the next release named in the 0.5 record; keep core and alias synchronized.
- Reconcile the release merge's missing weekly provenance record with a truthful release/presentation audit row; preserve the existing format-session records and weekly CI guard.
- Add focused checks for links, assets and release-facing claims; run the quick gate. Publication settings and announcement drafts are prepared locally; no commit, push, release publication or third-party message is implied.

## Capabilities

### New Capabilities

- `public-presentation`: accurate onboarding, demonstration assets and launch material.

### Modified Capabilities

- `release-gate`: replace the exhaustive release inventory with workflow sections and linked documentation; preserve the version/status, installation, executable loop and anti-overclaim guards.
- `repo-layout`: add the Documentation package URL while preserving the closed metadata set and Alpha classifier.

## Impact

README.md, pyproject.toml, docs/index.md, docs/quickstart.md, docs/media/, docs/launch/, tools/marketing/, tests/unit/test_public_presentation.py and CHANGELOG.md. No runtime API or CLI change.
