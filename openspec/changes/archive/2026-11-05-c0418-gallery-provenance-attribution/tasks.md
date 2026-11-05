# c0418 tasks

## 1. Gallery

- [x] 1.1 `attribution_problems` and origin-based `attribution_line` and "Source" fact in
  `fenolite.library.gallery`; `library gallery` reports `library.provenance-invalid` errors and plans no
  write; the explanation of the code names the gallery (scenarios "Authored and third-party attribution",
  "Contradictory provenance fails the gallery"; "Card attribution" and "Restricted marks hidden" keep
  passing). Proof: `uv run pytest tests/unit/library/test_gallery.py tests/unit/test_public_presentation.py
  -k "library or gallery" -q`.
- [x] 1.2 Docs: `docs/library-repo.md` (Gallery), `docs/evidence/sources.md` (S-1770..S-1772), the agent
  guide page on library items, CHANGELOG. Proof: `uv run pytest tests/unit/agent -q` and
  `openspec validate c0418-gallery-provenance-attribution --strict`.

## 2. Library

- [x] 2.1 Once c0418 is on Fenolite `dev`: the library pin moves to that commit and the gallery is redeployed;
  the LibrePCB items show the derived-from line. Proof: library checks and a gallery run green on the PR,
  the deploy from `main`, and the live LibrePCB pages without "Authored for fenolite-library".

  Closed: library PR lgili/fenolite-library#5 (squash 248913df, pin to Fenolite dev 5ab9d645), gallery run 42108815465 deployed from main; the four live LibrePCB pages say "Derived from LibrePCB Base" and none says "Authored for fenolite-library".
