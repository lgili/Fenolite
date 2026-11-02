## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`layout-reuse`, `cli-contract`, and `placement-in-code` once c0255 is archived) and the changes it builds on (c0251, c0255, c0268; c0250, c0270, c0273). Write under this task, with the date and the base commit:
  - whether c0255 is archived, the final names of `inst.place`, `b.layout`, `inst.layout`, the level-5 resolver hook and the `build.json` pose record (regenerate the ADDED blocks of `specs/placement-in-code/` against the living text if names changed);
  - whether c0255 kept the mirrored pose out (its open question 1) or another change took it;
  - c0268's record fields `id` and `version`, the module of the block codes, and the verbs of `fenolite blocks`;
  - whether c0250 is archived (decides which branch of design decision 7 is implemented first);
  - the function of the geometry kernel that flips a footprint to the bottom, and its hypothesis (`H-G-FLIP`).

  Proof: `openspec validate c0271-block-layouts --strict`; `make check-fast`.
  Entry inspection 2026-11-01, base `8d74a798`: c0251, c0255, c0268 and c0250 are
  implemented on the base but remain unarchived. The living `layout-reuse` and `cli-contract` were
  inspected; `placement-in-code` exists only in c0255's delta. Final DSL names are `inst.place`,
  `b.layout` and `inst.layout`; `cli._layout.plan_layout` injects `Scene.reuse` into
  `placement.relative.resolve`, and `LayoutPlan.resolver` enters `lens.preserve` through its resolver
  hook. `.fenolite/build.json` stores `layout.poses` as absolute `[x,y,rotation]` arrays and a digest.
  c0255 explicitly left mirrored poses out; c0271 owns them. c0268 uses decorator header `id` and
  `version` and model `Module.block` / `block_version`; block CLI codes live in `cli.cmd_blocks`, whose
  verbs are list/show/doc/where (c0270 concurrently adds test). c0250 is already in code, so decision 7's
  three-way code-side merge branch applies immediately. Footprint transforms use
  `geometry.Transform.placement(..., mirror=True)` (local Y flip), and native bottom embedding uses
  `backends.kicad.embed.flip_footprint_tree`, covered by `H-G-FLIP`. A block's vertical-axis mirror is
  that transform with a further half turn. The four recommended decisions are recorded as
  Decided 2026-11-01 in design.md. This task stays open because root schedules its full gate.

  Entry refresh 2026-11-02, integration base `697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`:
  c0251/c0255/c0268/c0250 and the block-test/package additions remain active and
  implemented; no living placement-in-code spec exists yet. The public names stay inst.place,
  b.layout and inst.layout. `cli._layout.plan_layout`/`LayoutPlan.resolver` feed the level-5
  relative resolver and lens hooks; the build record keeps layout.poses/digest, source hashes
  and layout-file summaries. Top poses stay [x,y,rotation], with a fourth "bottom" value
  only for bottom poses. c0255 deferred mirrors; c0271 supplies them. c0268 retains id/version,
  block codes live in `cli.cmd_blocks`, and verbs are list/show/doc/where/test/capture/index/upgrade.
  c0250's implemented three-way merge branch applies despite its unarchived status.
  `geometry.Transform.placement(...,mirror=True)` mirrors about local X (y -> -y);
  a vertical-axis mirror adds a half turn. Native lowering uses
  `backends.kicad.embed.flip_footprint_tree`, with the existing H-G-FLIP evidence unchanged.
  The four accepted recommendations remain a stale-layout warning, multiple layouts later,
  no layout payload in the lock, and capture without rewriting Python.

  Available proof: `openspec validate c0271-block-layouts --strict` passes without warnings
  (OpenSpec 1.16.0).
  The literal `make check-fast` is not run by this worker and has no applicable passing
  serialized receipt yet. Task 0.1 remains unchecked for that actual proof; independent
  CI, native/manual and release criteria are unchanged.


- [x] 0.2 Write `docs/formats/fenolite/block-layout.md`: the format of design decision 1 and the digests of decision 2, Fenolite's own format, evidence `INFERRED`. Proof: `uv run pytest tests/consistency -q`.

  2026-11-01: `uv run pytest tests/consistency -q`: 662 passed, 41 skipped.

## 1. The file

- [x] 1.1 `reuse/blocklayout.py`: `BlockLayout`, `read_block_layout`, `write_block_layout` with the fixed key order and exact units (scenarios "A layout is read exactly", "Unknown key and inexact length"). Author `tests/data/blocks/lib/layouts/divider.toml` and its block, each with the authored-for-Fenolite line. Proof: `uv run pytest tests/unit/reuse/test_blocklayout.py -k "read or write" -q`.
- [x] 1.2 `parts_digest` and `nets_digest` from the built model (scenario "A value change keeps the digests, a case change does not"). Proof: `uv run pytest tests/unit/reuse/test_blocklayout.py -k digests -q`.

## 2. Applying a layout

- [x] 2.1 Level-5 adapter injected by `cmd_build` into c0255's resolver: positions composed with the pose, `result.placement.blocks[].layout`, the SHA-256 in `build.json` and `layout` in `fenolite blocks show` (scenarios "A divider placed from its layout", "A placement edit wins over the layout", "A block with a layout"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k "placed or edit or record" -q`.
- [x] 2.2 Refusals and notices: `reuse.layout-block`, `reuse.layout-stale`, `reuse.layout-nets`, `reuse.layout-older`, `reuse.layout-changed` (scenarios "A changed part set is never laid out wrongly", "A layout of another block", "A layout of version 1.0.0 on block 1.1.0"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k "stale or another or older or changed" -q`.
- [x] 2.3 Copper: net remap by port and local net, layer map, `pad-lost`, c0210's settling, locked copies with derived uuids (scenario "Copper follows the ports"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k copper tests/unit/reuse -q`.

- [x] 2.4 Saved copied tracks/arcs/vias/zones: protected persistent code/output snapshots; CAD-only edits and deletions survive repeated builds; unchanged CAD follows the asset; inconsistent changes refuse writes; explicit discard or recapture resolves, without expanding part --take grammar. Preserve clone/cache independence and mirrored edited copies. Proof: `uv run pytest tests/unit/cli/test_block_layout_merge.py -q`.

## 3. Mirrored poses

- [x] 3.1 `inst.place(..., side="bottom")` and its composition in `placement/relative.py`; register `H-G-BLOCK-LAYOUT` (scenario "The same block on both sides"). Proof: `uv run pytest tests/unit/placement/test_relative.py -k mirrored -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 3.2 Mirrored copper layers and rigid flips of kept children (scenario "A laid-out block flipped in code"). Proof: `uv run pytest tests/unit/cli/test_build_block_layout.py -k flipped -q`.

## 4. Capture

- [x] 4.1 `capture_block_layout`: frame by pose or anchor, c0227's group rule, `blocks.capture-copper-left`, `blocks.capture-escape` (scenarios "Capture from a bench board", "Port copper that leaves the block"). Author `tests/data/blocks/bench/divider.py` and its laid-out board. Proof: `uv run pytest tests/unit/reuse/test_blocklayout.py -k capture -q`.
- [x] 4.2 Round trip with `fit_block` at 1 µm, `blocks.capture-check-failed`, `blocks.capture-unplaced` (scenario "A part missing from the board"). Proof: `uv run pytest tests/unit/cli/test_blocks_capture.py -k "unplaced or round" -q`.
- [x] 4.3 The verb `fenolite blocks capture` with the output path rule, plan and confirm, `result.capture` (scenario "Not a block instance"). Proof: `uv run pytest tests/unit/cli/test_blocks_capture.py -q`.
- [x] 4.4 The ten codes in `reuse.codes`, the block codes, `explain.toml` and `docs/cli-contract.md`, "Block layouts" (scenario "Every block layout code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.

## 5. Example, KiCad, docs and guide

- [ ] 5.1 `examples/blocks/layouts.py` with one instance on each side and copper, and `tests/kicad/blocks/test_block_layouts.py` for targets 9 and 10 (scenario "Both sides in KiCad"); register `H-K-BLOCK-LAYOUT-DRC`. Proof: `uv run pytest tests/kicad/blocks/test_block_layouts.py` in the KiCad jobs on the pushed head; `make residue`.
- [x] 5.2 Docs: `docs/placement.md` ("Block layouts", mirrored poses, capture from a bench script), `docs/lens.md` (level 5 holds block layouts; the code side of c0250's merge), `docs/cli-contract.md` (`blocks capture`). Proof: `uv run pytest tests/consistency -q`.
- [x] 5.3 Agent guide: a tested line for `fenolite blocks capture` and for `side="bottom"` of a block pose on a focused page linked from `placement`, then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch (unit and KiCad jobs). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.2 Evidence: record the measurements of `H-G-BLOCK-LAYOUT` and `H-K-BLOCK-LAYOUT-DRC` in `docs/hypotheses.md` and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.

Implementation proof record, 2026-11-01:

- 1.1: exact read/write proof 9 passed; 1.2: digests proof 1 passed. Fixture digests use
  the resolved model, preserving repeated and unnumbered pads, and exclude values and pad geometry.
- 2.1: 4 passed; 2.2: 3 passed; 2.3: the written copper/reuse proof 18 passed. An additional
  focused regression run over reuse, build/layout/capture, block records, DSL and placement passed
  149 tests. The code-side copper is settled after the property merge, against the winning placements.
- 2.4: 17 passed. Protected root code/output observations preserve edited or deleted tracks, arcs,
  vias and zones across repeated cache-free builds. Asset-only changes update the copies; competing
  edits refuse writes, including under part `--take`, and explicit discard or checked recapture
  resolves them. Additional cases cover missing/corrupt observations, cache pose tampering, mirrored
  edits, derived zone-fill retention, settled-away candidates and exact retained CAD points at 33°.
  The optional snapshot is absent from old output surfaces without layout copper. UUID ownership,
  1 nm frame equivalence, stack-change refusal and the adapter's resolution limits are documented.
- 3.1: mirrored solver proof 2 passed; hypothesis/import-register proof 95 passed. Quarter-turn
  divider pad images are exact; asymmetric pads at non-quarter turns meet the 1 nm bound.
  3.2: flipped proof 1 passed; the existing board-file reuse also has a mirrored-copper regression. Old three-integer pose records still read; bottom transforms append
  a fourth side entry. The stored rotation follows the model transform's local-Y mirror convention.
- 4.1: capture proof 4 passed; capture uses c0227's joined-group selection supplied by the CLI. The authored bench board
  has an OUT route and a free ground via; the via is deliberately outside the selected group.
  Nondefault via protection is refused as a failed v0 round trip rather than silently removed.
  4.2: 3 passed; 4.3: 9 passed, including checked plan/confirm, deterministic bytes, default output,
  outside copper, shipped-package output refusal and changed-input refusal. 4.4: explanations proof 14 passed.
- 5.2: consistency proof 662 passed, 41 mutation skips. 5.3: all agent tests passed as part of
  the agent/capture run (127 passed, 19 existing KiCad-major skips), and guide generation/check passed.
  A focused block-layouts page keeps placement.md below its 12000-byte budget.
- 6.3: changelog selection 8 passed, 1 SDK collection skip; the branch is already on 0.7.0.dev0.
- Strict OpenSpec validation passed without warnings. Ruff check/format, import layering and residue
  scan passed. No source or FEN allocations were needed. Evidence matrix generation/check passed.
- Saved-copper follow-up: the final focused regression run passed 352 tests, including legacy
  preservation, part edit merge, script copper, zone fills and all layout/capture paths. Consistency
  remained 662 passed / 41 mutation skips; the guide suite passed 119 / 19 installed-KiCad-major
  skips. Final generated guide/matrix checks, residue (0 hits), lint/format, `pyright src` (0 errors)
  and strict OpenSpec passed.

Open gates remain deliberate: 0.1 includes the root-scheduled complete local gate; 5.1's example and
oracle tests (both initial sides and a kept block flipped between builds) are authored, and local
example builds for targets 9 and 10 pass, but its required exact-head KiCad jobs are not run here.
6.1 awaits the root local gate and exact-head required CI jobs. 6.2 records the measured unit evidence
at INFERRED; H-K-BLOCK-LAYOUT-DRC remains pending those KiCad jobs and has not been promoted.
