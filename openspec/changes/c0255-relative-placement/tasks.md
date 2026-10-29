## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `layout-lens`, `layout-reuse`, `placement`) and the changes it builds on (c0251 blocks, c0250 manual edits, c0210 and c0227 reuse). Write under this task, with the date and the base commit:
  - c0251's final names for the block builder, the instance handle, block paths and nested instances;
  - whether c0250 (or another open change) holds a delta of "Placement precedence", and whether one was archived (then regenerate the MODIFIED block from the living text, keeping both edits);
  - whether `level 3` is still `placements.toml` or already c0250's `edits.toml`;
  - the signatures of `reuse.fit_block`, `reuse.copy_copper` and c0227's group move that decisions 7 and 9 call;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0255-relative-placement --strict --no-interactive`.

## 1. DSL

- [ ] 1.1 `dsl/relative.py`: `RelativeRequest`, edge expressions, `BoardRef` returned by `Design.board`, `relative_requests(design)`; `Part.place` keywords (scenarios "A request is recorded, not resolved", "An edge expression"). Proof: `uv run pytest tests/unit/dsl/test_relative.py -q`.
- [ ] 1.2 Axis determination and locked references (scenarios "Conflicting sources", "A locked part next to an unlocked one"). Proof: `uv run pytest tests/unit/dsl/test_relative.py -k "axis or locked" -q`.
- [ ] 1.3 Block poses, `layout()` with `row`, `column`, `grid`, `pack` and `reuse=` on the block builder, the instance and `Design` (scenarios "A reference out of the block", "Instance strategy wins", "Strategy and reuse together"). Proof: `uv run pytest tests/unit/dsl/test_block_layout.py -q`.

## 2. Resolution and strategies

- [ ] 2.1 `placement/relative.py`: boxes, relations, alignment, `by`, topological order, `layout.relative-cycle` and `layout.relative-unresolved` (scenarios "A capacitor by its pad", "Turned part", "A cycle", "Reference left in staging"). Proof: `uv run pytest tests/unit/placement/test_relative.py -q`.
- [ ] 2.2 `placement/strategies.py`: row, column, grid, pack, `layout.strategy-overflow` (scenarios "A row of three", "Pack within a width"). Proof: `uv run pytest tests/unit/placement/test_strategies.py -q`.
- [ ] 2.3 Block poses composed with children and nested blocks; strategy groups without a pose staged as one box (scenarios "A block moved and turned", "A group stays together"). Proof: `uv run pytest tests/unit/placement/test_relative.py -k pose tests/unit/lens/test_staging.py -q`.

## 3. Precedence, build and records

- [ ] 3.1 `lens.preserve.effective_placements` with `resolver`, the six levels, and `cmd_build` injecting the resolver (MODIFIED "Placement precedence" and its three new scenarios; every earlier scenario still passes). Proof: `uv run pytest tests/unit/lens/test_preserve.py tests/unit/cli/test_build_cmd.py -q`.
- [ ] 3.2 Records: `result.placement.relative`, `result.placement.blocks`, block poses in `.fenolite/build.json`, byte-identical rebuilds. Proof: `uv run pytest tests/unit/cli/test_build_relative.py -q`.
- [ ] 3.3 Rigid block moves with c0227's copper rules and `layout.block-moved` (scenario "Moving a laid-out block in code"). Proof: `uv run pytest tests/unit/cli/test_build_relative.py -k block_moved -q`.
- [ ] 3.4 Codes in `lens` and `explain.toml` (scenario "Every code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.

## 4. Block layout reuse

- [ ] 4.1 An explicit transform for `reuse.fit_block` and an explicit net map for `reuse.copy_copper`; existing reuse tests unchanged. Proof: `uv run pytest tests/unit/reuse -q`.
- [ ] 4.2 Block reuse in the build: parts by path, nets by port, `reuse.port-unmapped`, locked copies (scenarios "A block placed from its own board", "Copper follows the ports", "A net without a port", "The code is explained"). Proof: `uv run pytest tests/unit/cli/test_build_reuse.py tests/unit/cli/test_explain_cmd.py -q`.

## 5. KiCad read-back

- [ ] 5.1 `examples/relative/` (pads, edges, a posed block with a row, a reused block with its authored reference board), each file with its authored-for-Fenolite line, built for targets 9 and 10 and read back (scenario "Read back what was resolved"). Proof: `uv run pytest tests/kicad/build/test_relative_build.py -q` (CI kicad jobs).

## 6. Docs and guide

- [ ] 6.1 `docs/dsl.md` ("Relative placement", "Block layout"), `docs/lens.md` ("Placement precedence", the six levels), `docs/placement.md`, `docs/cli-contract.md` ("Placement in code" codes). Proof: `uv run pytest tests/consistency -q`.
- [ ] 6.2 Agent guide: tested lines for the relations, `by`, `layout()`, `row`/`column`/`grid`/`pack` and the precedence list on `placement` and `board-floorplan`, and for the four `layout.*` codes and `reuse.port-unmapped` on `recovery`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 7. Closing

- [ ] 7.1 Residue: the examples and the reference board are authored for Fenolite. Proof: `make residue`.
- [ ] 7.2 Evidence: `H-G-REL-RESOLVE` in `docs/hypotheses.md` with its measurement; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 7.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.
