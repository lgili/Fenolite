## 0. Entry check

- [ ] 0.1 Profile S-0187's board and record the split of the 12.7 s and of the 5 MB under this task. Proof: `openspec validate c0182-viewer-performance --strict --no-interactive`.

## 1. Cache and encoding

- [ ] 1.1 Add `view/cache.py` and use it in `cmd_view` and the server (scenario "A second open"). Proof: `uv run pytest tests/unit/view/test_cache.py -q`.
- [ ] 1.2 Write v1 scenes and decode them in the page (scenario "Same drawing"). Proof: `uv run pytest tests/unit/view/test_scene_v1.py tests/unit/view/test_page.py -q`.
- [ ] 1.3 Speed up the two largest parts of the profile. Record before and after under this task. Proof: `FENOLITE_HEAVY=1 uv run pytest tests/corpus -k scene_budget -q`.

## 2. Loading and export

- [ ] 2.1 Lazy scenes in `--serve`, compressed scenes and `--docs` in `--export` (scenario "Export of one document"). Proof: `uv run pytest tests/unit/cli/test_view_cmd.py tests/unit/view -q`.
- [ ] 2.2 Review in a browser S-0187's project page: open time and memory. Record them. Proof: the record under this task.

## 3. Closing

- [ ] 3.1 Docs, `LEGAL-ANNEX.md` row if needed, fast gate. Proof: `make check-fast`.
