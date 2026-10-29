## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`layout-reuse`, `cli-contract`, and `placement-in-code` once c0255 is archived) and the changes it builds on (c0251, c0255, c0268; c0250, c0270, c0273). Write under this task, with the date and the base commit:
  - whether c0255 is archived, the final names of `inst.place`, `b.layout`, `inst.layout`, the level-5 resolver hook and the `build.json` pose record (regenerate the ADDED blocks of `specs/placement-in-code/` against the living text if names changed);
  - whether c0255 kept the mirrored pose out (its open question 1) or another change took it;
  - c0268's record fields `id` and `version`, the module of the block codes, and the verbs of `fenolite blocks`;
  - whether c0250 is archived (decides which branch of design decision 7 is implemented first);
  - the function of the geometry kernel that flips a footprint to the bottom, and its hypothesis (`H-G-FLIP`).

  Proof: `openspec validate c0271-block-layouts --strict`; `make check-fast`.
- [ ] 0.2 Write `docs/formats/fenolite/block-layout.md`: the format of design decision 1 and the digests of decision 2, Fenolite's own format, evidence `INFERRED`. Proof: `uv run pytest tests/consistency -q`.

## 1. The file

- [ ] 1.1 `reuse/blocklayout.py`: `BlockLayout`, `read_block_layout`, `write_block_layout` with the fixed key order and exact units (scenarios "A layout is read exactly", "Unknown key and inexact length"). Author `tests/data/blocks/lib/layouts/divider.toml` and its block, each with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/reuse/test_blocklayout.py -k "read or write" -q`.
- [ ] 1.2 `parts_digest` and `nets_digest` from the built model (scenario "A value change keeps the digests, a case change does not"). Proof: `uv run pytest tests/unit/reuse/test_blocklayout.py -k digests -q`.

## 2. Applying a layout

- [ ] 2.1 Level-5 adapter injected by `cmd_build` into c0255's resolver: positions composed with the pose, `result.placement.blocks[].layout`, the SHA-256 in `build.json` and `layout` in `fenolite blocks show` (scenarios "A divider placed from its layout", "A placement edit wins over the layout", "A block with a layout"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k "placed or edit or record" -q`.
- [ ] 2.2 Refusals and notices: `reuse.layout-block`, `reuse.layout-stale`, `reuse.layout-nets`, `reuse.layout-older`, `reuse.layout-changed` (scenarios "A changed part set is never laid out wrongly", "A layout of another block", "A layout of version 1.0.0 on block 1.1.0"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k "stale or another or older or changed" -q`.
- [ ] 2.3 Copper: net remap by port and local net, layer map, `pad-lost`, c0210's settling, locked copies with derived uuids (scenario "Copper follows the ports"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k copper tests/unit/reuse -q`.

## 3. Mirrored poses

- [ ] 3.1 `inst.place(..., side="bottom")` and its composition in `placement/relative.py`; register `H-G-BLOCK-LAYOUT` (scenario "The same block on both sides"). Proof: `uv run pytest tests/unit/placement/test_relative.py -k mirrored -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 3.2 Mirrored copper layers and rigid flips of kept children (scenario "A laid-out block flipped in code"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k flipped -q`.

## 4. Capture

- [ ] 4.1 `capture_block_layout`: frame by pose or anchor, c0227's group rule, `blocks.capture-copper-left`, `blocks.capture-escape` (scenarios "Capture from a bench board", "Port copper that leaves the block"). Author `tests/data/blocks/bench/divider.py` and its laid-out board. Proof: `uv run pytest tests/unit/reuse/test_blocklayout.py -k capture -q`.
- [ ] 4.2 Round trip with `fit_block` at 1 µm, `blocks.capture-check-failed`, `blocks.capture-unplaced` (scenario "A part missing from the board"). Proof: `uv run pytest tests/unit/cli/test_blocks_capture.py -k "unplaced or round" -q`.
- [ ] 4.3 The verb `fenolite blocks capture` with the output path rule, plan and confirm, `result.capture` (scenario "Not a block instance"). Proof: `uv run pytest tests/unit/cli/test_blocks_capture.py -q`.
- [ ] 4.4 The nine codes in `reuse.codes`, the block codes, `explain.toml` and `docs/cli-contract.md`, "Block layouts" (scenario "Every block layout code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.

## 5. Example, KiCad, docs and guide

- [ ] 5.1 `examples/blocks/layouts.py` with one instance on each side and copper, and `tests/kicad/blocks/test_block_layouts.py` for targets 9 and 10 (scenario "Both sides in KiCad"); register `H-K-BLOCK-LAYOUT-DRC`. Proof: `uv run pytest tests/kicad/blocks/test_block_layouts.py` in the KiCad jobs on the pushed head; `make residue`.
- [ ] 5.2 Docs: `docs/placement.md` ("Block layouts", mirrored poses, capture from a bench script), `docs/lens.md` (level 5 holds block layouts; the code side of c0250's merge), `docs/cli-contract.md` (`blocks capture`). Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.3 Agent guide: a tested line for `fenolite blocks capture` and for `side="bottom"` of a block pose on `placement`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch (unit and KiCad jobs). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.2 Evidence: record the measurements of `H-G-BLOCK-LAYOUT` and `H-K-BLOCK-LAYOUT-DRC` in `docs/hypotheses.md` and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
