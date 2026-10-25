## 0. Entry check

- [x] 0.1 Profile S-0187's board and record the split of the 12.7 s and of the 5 MB under this task. Proof: `openspec validate c0182-viewer-performance --strict --no-interactive`.
  - 2026-10-25, measured in the container with the c0181 code:
    - **Time:** the backend read 9.72 s, `native_view` 3.46 s, the scene 2.28 s, JSON 0.05 s.
    - **Size:** 5 924 KiB, of which the primitives are 4 843 KiB (zone fills 2.1 MB, tracks 1.3 MB, circles 0.75 MB) and the labels 427 KiB.
    - **Hot spots of the read:**
      - `PropertyRecord.get_all` upper-cased every field of a record on every lookup (69 million `str.upper` calls);
      - `iter_entities`, run by `Design.validate` and `by_id`, walked 4 million nodes, mostly strings and the `Provenance` and `Evidence` of each entity.
    - `native_view` was slow for the same lookup.
    - The branch is `c0182-viewer-performance`, from `c0181-altium-native-layers`. Proof passed.

## 1. Cache and encoding

- [x] 1.1 Add `view/cache.py` and use it in `cmd_view` and the server (scenario "A second open"). Proof: `uv run pytest tests/unit/view/test_cache.py tests/unit/cli/test_view_cmd.py -q`.
  - 2026-10-25: proof passed (16). The default is the user's cache folder, because the contract says `view` writes nothing into the project without `--serve` or `--export`. `--cache project` writes `.fenolite/view-cache/`. `tests/conftest.py` points `FENOLITE_CACHE_DIR` at a folder of the run.
- [x] 1.2 Write v1 scenes and decode them in the page (scenario "Same drawing"). Proof: `uv run pytest tests/unit/view/test_scene_v1.py tests/unit/view/test_page.py -q`.
  - 2026-10-25: proof passed. The page's `decodeV1` ran under Node and gave the v0 primitives exactly.
  - The encoding writes points as offsets, and labels as templates with numbers.
  - On S-0187 the primitives went from 4 254 to 2 057 KiB (48 %), and the packed scene is 424 KiB (8 % of 5 208 KiB).
- [x] 1.3 Speed up the two largest parts of the profile. Record before and after under this task. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_view_budget.py -q`.
  - 2026-10-25: proof passed.
    - **Key lookup:** a record now indexes its upper-case keys once.
    - **Entity walk:** `iter_entities` skips values that hold no entity (strings, numbers, points, provenance, evidence) and caches each type's fields.
    - **Before → after:** the read went from 9.72 s to 4.75 s, `native_view` from 3.46 s to 0.27 s, and the whole scene from 12.7 s to about 7 s.
    - The fast suite went from 6:00 to 4:22. Results are unchanged: 13 907 tests passed, and 67 Altium corpus tests passed.

## 2. Loading and export

- [x] 2.1 Lazy scenes in `--serve`, compressed scenes and `--docs` in `--export` (scenario "Export of one document"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view -q`.
  - 2026-10-25: proof passed.
    - The server already built a scene on its first request; it now sends v1 and reads the cache.
    - The exported page keeps each scene packed and decodes it when its document is opened.
    - `embedded()` returns the v0 scenes for tests and tools.
- [x] 2.2 Review in a browser S-0187's project page: open time and memory. Record them. Proof: the record under this task.
  - 2026-10-25, the agent, in the Chromium of the container (Playwright, headless), on the exported page of S-0187's board.
    - **Page:** 523 KB, against about 5.9 MB before.
    - **Open:** the board is drawn 1.2 s after the page starts loading, with 39 407 primitives and a JS heap of 45 MB; no page error.
    - **CLI:** `fenolite view --export --dry-run` took 8.3 s on the first run and 1.4 s on the second (a cache hit), Python start included.

## 3. Closing

- [x] 3.1 Docs, `LEGAL-ANNEX.md` row if needed, fast gate. Proof: `make check-fast`.
  - 2026-10-25: proof passed (13 907 passed, 34 skipped).
  - Changed: `docs/viewer.md` ("Speed and size") and the `view` section of `docs/cli-contract.md`.
  - The agent guide was regenerated. The skill folder is now 1 byte under its 150 000-byte budget, after shortening the `view` help texts and one line of `files.md`; the next change to a guide page needs room made first.
  - No format fact was added, so no `LEGAL-ANNEX.md` row is needed.
