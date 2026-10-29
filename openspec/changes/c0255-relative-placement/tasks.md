## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `layout-lens`, `layout-reuse`, `placement`) and the changes it builds on (c0251 blocks, c0250 manual edits, c0210 and c0227 reuse). Write under this task, with the date and the base commit:
  - c0251's final names for the block builder, the instance handle, block paths and nested instances;
  - whether c0250 (or another open change) holds a delta of "Placement precedence", and whether one was archived (then regenerate the MODIFIED block from the living text, keeping both edits);
  - whether `level 3` is still `placements.toml` or already c0250's `edits.toml`;
  - the signatures of `reuse.fit_block`, `reuse.copy_copper` and c0227's group move that decisions 7 and 9 call;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0255-relative-placement --strict --no-interactive`.

  2026-10-29, base `9c92302a` (circuits-as-code with c0246, c0247, c0249, c0250, c0251, c0278):
  - c0251: the builder is `Block` (`b.part`, `b.net`, `b.port`, `b.use`, `b.add`), the handle `BlockInstance` (`inst.part(local)`, `inst.port(name)`, `inst.module`), paths `<parent path>/<name>` (`buck1/U`), nested instances by `b.use`; `blocks(design)` lists them. `place` was already a reserved port name; `layout`, `module` and the six edges are reserved now.
  - c0250 holds a MODIFIED delta of "Placement precedence" and is merged in code but not archived; this change's delta is regenerated from c0250's text with both edits (`specs/layout-lens/spec.md`), so either can archive first.
  - Level 3 is c0250's `edits.toml` (a legacy `placements.toml` is read as its edits).
  - Signatures: `reuse.fit_block(reference, target, parts, *, anchor=None, mapping=None, tolerance=DEFAULT_TOLERANCE)`, `reuse.copy_copper(fit, reference, target, *, items=None, zones=None)`, c0227's group move `cli.place_group.moving_copper(design, pads, members)` with `_moved_item` and `backends.kicad.replace.move_footprint`.
  - Open questions: the recommended answers, written as "Decided 2026-10-29" in `design.md` (the maintainer delegated them).
  - Left open: the `openspec` command is not installed in this container and fetching it was refused here, so the strict validation is for the coordinator.

## 1. DSL

- [x] 1.1 `dsl/relative.py`: `RelativeRequest`, edge expressions, `BoardRef` returned by `Design.board`, `relative_requests(design)`; `Part.place` keywords (scenarios "A request is recorded, not resolved", "An edge expression"). Proof: `uv run pytest tests/unit/dsl/test_relative.py -q`.
  2026-10-29: 19 passed.
- [x] 1.2 Axis determination and locked references (scenarios "Conflicting sources", "A locked part next to an unlocked one"). Proof: `uv run pytest tests/unit/dsl/test_relative.py -k "axis or locked" -q`.
  2026-10-29: passed (the locked check runs when the requests are converted, `relative_requests`).
- [x] 1.3 Block poses, `layout()` with `row`, `column`, `grid`, `pack` and `reuse=` on the block builder, the instance and `Design` (scenarios "A reference out of the block", "Instance strategy wins", "Strategy and reuse together"). Proof: `uv run pytest tests/unit/dsl/test_block_layout.py -q`.
  2026-10-29: 9 passed.

## 2. Resolution and strategies

- [x] 2.1 `placement/relative.py`: boxes, relations, alignment, `by`, topological order, `layout.relative-cycle` and `layout.relative-unresolved` (scenarios "A capacitor by its pad", "Turned part", "A cycle", "Reference left in staging"). Proof: `uv run pytest tests/unit/placement/test_relative.py -q`.
  2026-10-29: 16 passed. The codes live in `placement.codes.LAYOUT_ISSUE_CODES` (a table of `explain.TABLES`; `lens` may not import `placement`).
- [x] 2.2 `placement/strategies.py`: row, column, grid, pack, `layout.strategy-overflow` (scenarios "A row of three", "Pack within a width"). Proof: `uv run pytest tests/unit/placement/test_strategies.py -q`.
  2026-10-29: 5 passed.
- [x] 2.3 Block poses composed with children and nested blocks; strategy groups without a pose staged as one box (scenarios "A block moved and turned", "A group stays together"). Proof: `uv run pytest tests/unit/placement/test_relative.py -k pose tests/unit/lens/test_staging.py -q`.
  2026-10-29: passed.

## 3. Precedence, build and records

- [x] 3.1 `lens.preserve.effective_placements` with `resolver`, the six levels, and `cmd_build` injecting the resolver (MODIFIED "Placement precedence" and its three new scenarios; every earlier scenario still passes). Proof: `uv run pytest tests/unit/lens/test_preserve.py tests/unit/cli/test_build_cmd.py -q`.
  2026-10-29: `tests/unit/lens/test_preserve.py` (new) passed; `tests/unit/cli/test_build_cmd.py` does not exist, so the existing build tests ran instead: `uv run pytest tests/unit/cli -k "build or explain or place or sync" -n 2` (483 passed) and `tests/unit/lens` (all passed). The resolver runs in rounds against the merged placements (`preserve.resolving`).
- [x] 3.2 Records: `result.placement.relative`, `result.placement.blocks`, block poses in `.fenolite/build.json`, byte-identical rebuilds. Proof: `uv run pytest tests/unit/cli/test_build_relative.py -q`.
  2026-10-29: passed.
- [x] 3.3 Rigid block moves with c0227's copper rules and `layout.block-moved` (scenario "Moving a laid-out block in code"). Proof: `uv run pytest tests/unit/cli/test_build_relative.py -k block_moved -q`.
  2026-10-29: passed; the base entries of the moved parts move too, else c0250's merge reports a hand-moved part of the block as a conflict.
- [x] 3.4 Codes in `lens` and `explain.toml` (scenario "Every code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.
  2026-10-29: 13 passed.

## 4. Block layout reuse

- [x] 4.1 An explicit transform for `reuse.fit_block` and an explicit net map for `reuse.copy_copper`; existing reuse tests unchanged. Proof: `uv run pytest tests/unit/reuse -q`.
  2026-10-29: 27 passed; also `reuse.copy_block` (every item of the mapped nets, no fit needed).
- [x] 4.2 Block reuse in the build: parts by path, nets by port, `reuse.port-unmapped`, locked copies (scenarios "A block placed from its own board", "Copper follows the ports", "A net without a port", "The code is explained"). Proof: `uv run pytest tests/unit/cli/test_build_reuse.py tests/unit/cli/test_explain_cmd.py -q`.
  2026-10-29: 6 and 13 passed. The pad check compares each definition placed where its reference part lies (the build has no target board for `fit_block` yet).

## 5. KiCad read-back

- [x] 5.1 `examples/relative/` (pads, edges, a posed block with a row, a reused block with its authored reference board), each file with its authored-for-Fenolite line, built for targets 9 and 10 and read back (scenario "Read back what was resolved"). Proof: `uv run pytest tests/kicad/build/test_relative_build.py -q` (CI kicad jobs).
  2026-10-29: passed locally with `FENOLITE_KICAD_CLI=docker:kicad/kicad:9.0.9` (2 passed, 1 skipped: `pcb upgrade` is a 10 command) and `docker:kicad/kicad:10.0.6` (3 passed); the read-back is KiCad's position file, to the nanometre. The CI kicad jobs run with the batch.

## 6. Docs and guide

- [x] 6.1 `docs/dsl.md` ("Relative placement", "Block layout"), `docs/lens.md` ("Placement precedence", the six levels), `docs/placement.md`, `docs/cli-contract.md` ("Placement in code" codes). Proof: `uv run pytest tests/consistency -q`.
  2026-10-29: passed (the codes are a paragraph "Placement in code" of the `build` section).
- [ ] 6.2 Agent guide: tested lines for the relations, `by`, `layout()`, `row`/`column`/`grid`/`pack` and the precedence list on `placement` and `board-floorplan`, and for the four `layout.*` codes and `reuse.port-unmapped` on `recovery`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  2026-10-29: the lines and the design block are written and `--check` passes; every test of `tests/unit/agent` passes but `test_budget_holds`, which fails on the base already: the generated page `commands.md` holds 766 lines (limit 750) before this change, which adds no command. Open until that budget is fixed on the integration branch.

## 7. Closing

- [ ] 7.1 Residue: the examples and the reference board are authored for Fenolite. Proof: `make residue`.
- [x] 7.2 Evidence: `H-G-REL-RESOLVE` in `docs/hypotheses.md` with its measurement; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
  2026-10-29: 38 passed; the matrix holds no change. The register test also needed c0251's tasks to stop citing the renamed row `H-A-SCH-BLOCK-ENTRIES` (now `H-A-BLOCK-ENTRIES`).
- [x] 7.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `uv run pytest tests/unit -k changelog -q`.
  2026-10-29: the base is at 0.7.0.dev0; 8 passed.
- [ ] 7.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.
  CI runs with the batch.
