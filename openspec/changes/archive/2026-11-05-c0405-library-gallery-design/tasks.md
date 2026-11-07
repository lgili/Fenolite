# c0405 tasks

## 1. Images

- [x] 1.1 `catalog_scene` in `fenolite.view.catalog` and `fenolite.library.gallery_images`: symbol, footprint
  and device SVGs from the catalog scenes, pin 1 marked, placeholders with a reason. Proof:
  `uv run pytest tests/unit/library/test_gallery_images.py -q`.

## 2. Pages

- [x] 2.1 The designed index, item and benchmark pages, `assets/site.css` and `assets/site.js`, `--renders DIR`
  and `result.placeholders` (scenarios "Index page structure", "Item page structure", "Images for each
  kind", "Deterministic site", "Missing board render"); c0279's "Card attribution" and "Restricted marks
  hidden" keep passing. Proof: `uv run pytest tests/unit/library/test_gallery.py
  tests/unit/test_public_presentation.py -k library -q`.
- [x] 2.2 Docs and agent guide: `docs/library-repo.md` (Gallery), the `library gallery` arguments in the
  guide (`uv run python tools/gen_agent_guide.py`), CHANGELOG. Proof: `uv run pytest tests/unit/agent -q`.

## 3. Library

- [x] 3.1 The pinned-Fenolite action gives `kicad-cli` a writable `HOME`; `gallery.yml` takes its tooling from
  the workflow's ref and the items from the tag. Proof: library PR 2 checks and a gallery run with no
  "error 13" line. Done: PR https://github.com/lgili/fenolite-library/pull/2 merged as `b7e141ea` after runs
  42008760140, 42008759586 and 42008770439; gallery run 42010062912 on `b7e141ea` deployed with no
  "error 13" or `/.cache` line in its log.
- [x] 3.2 Once c0405 is on Fenolite `dev`: the library pin moves to that commit and `gallery.yml` passes
  `--renders` (board views through `kicad-cli pcb export svg --page-size-mode 2 --exclude-drawing-sheet`,
  the block usage sheets as `schematic.kicad_sch`), drops the old render tolerance, and writes
  `result.placeholders` into the job summary. Proof: library checks and a gallery run green on the PR, then
  the deploy from `main`.
  - Done on 2026-11-05: fenolite-library PR 3 (https://github.com/lgili/fenolite-library/pull/3) moved the pin to 3675515a and merged as 7ebbd960; gallery run 42039495006 deployed https://lgili.github.io/fenolite-library/ with the new template, all six boards (pic_programmer included) and the block sheet.
