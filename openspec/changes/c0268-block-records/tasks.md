## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `design-model`,
  `cli-contract`) and the state of c0249, c0251, c0259 and c0266. Write under this task the date, the base
  commit, and:
  - whether c0251 is archived, and the names of `BlockDef`, the builder's `port` and the model fields
    `Module.block` and `params`;
  - whether c0249's `LockSection` protocol, `design.moved()` carrying and `--frozen` are archived, and
    the order of lock sections written so far (c0254 `picks`, c0257 `pins`, c0266 `library`);
  - whether c0259's header vocabulary is archived, so that the id and version patterns are shared code;
  - whether another open change holds a delta of "Inspect command" or "Allowed import edges" (c0254 and
    c0256 do), or registers a `blocks` command. If one was archived, regenerate the MODIFIED block from the
    living text;
  - whether the source ids `S-` used by test data are free of collisions;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0268-block-records --strict`; `make check-fast`.

## 1. Records and parameter metadata

- [ ] 1.1 Add the record keywords to `@block` with their checks, the reserved namespace `Fenolite`, and the
  closed categories (scenarios "Version form", "Id without version", "Unknown category", "Reserved
  namespace in a project", "Name and id together", "Project block unchanged"). Proof:
  `uv run pytest tests/unit/dsl/test_block_records.py -q`.
- [ ] 1.2 Add `param` and `REQUIRED`, their checks at decoration and at `use`, and the port keyword `doc`
  (scenarios "Value outside the range", "Wrong unit", "Default not a choice", "Port doc in the record").
  Proof: `uv run pytest tests/unit/dsl/test_block_param_meta.py -q`.
- [ ] 1.3 Add `dsl/record.py`: `describe`, `BlockRecord`, `record_json` and the three digests, with the
  authored `tests/data/blocks/` (CC0, authored for Fenolite; scenarios "Ports from defaults", "Hermetic
  describe", "Required parameter", "Doc change keeps the definition", "Stable bytes"). Proof:
  `uv run pytest tests/unit/dsl/test_describe.py -q`.

## 2. Model and lock

- [ ] 2.1 Add `Module.block_version`, regenerate the schemas, set it in `to_model`, and use the id as
  the block name (scenarios "Older circuit file", "Version without a block", "Version in the model").
  Proof: `uv run pytest tests/unit/model/test_circuit.py -k block_version tests/unit/dsl/test_blocks.py -k identity -q`;
  `uv run python tools/gen_schemas.py --check`.
- [ ] 2.2 Register the lock section `blocks` and its resolution, the codes `lock.block-version`,
  `lock.block-replaced`, `lock.block-released` and `block.deprecated` with their `explain.toml` entries
  (scenarios "First build pins the versions", "Moved instance keeps its entry", "Newer block version is
  not taken", "Frozen build and a first pin", "Deprecated block used twice"). Proof:
  `uv run pytest tests/unit/dsl/test_lock_blocks.py tests/unit/cli/test_build_lock_blocks.py -q`.

## 3. Catalog and commands

- [ ] 3.1 Add the row `blocks` to the import-graph table (scenario "Shipped blocks build on the DSL only", with a
  test module), then create the empty package `fenolite.blocks` with `VERSIONS.toml`, `tools/blocks/versions.py`, the
  version test and the import side-effect test (scenarios "Port renamed under an id", "Default changed
  without a minor step", "Import of the shipped blocks is clean", "Unregistered source of a shipped block").
  The rules are tested with authored blocks under `tests/data/blocks/versions/`. Proof:
  `uv run pytest tests/unit/blocks tests/unit/test_import_graph.py -q`.
- [ ] 3.2 Add `cli/blocksrc.py` and the verbs `blocks list` and `blocks show` (scenarios "Shipped and file
  blocks", "List with a file source", "Show the authored divider", "Unknown id", "Replacement without
  deprecation", "Verbs in capabilities"). Proof: `uv run pytest tests/unit/cli/test_blocks_cmd.py -k "list or show" -q`.
- [ ] 3.3 Add `page`, the verb `blocks doc` and `tools/gen_block_docs.py` with `--check` in the
  consistency tests (scenarios "Page of the authored divider", "Page planned, not written", "Stale page").
  Proof: `uv run pytest tests/unit/cli/test_blocks_cmd.py -k doc tests/consistency -k block_docs -q`.
- [ ] 3.4 Add the verb `blocks where` and the view `inspect --blocks` (scenarios "Two designs use one
  block", "Where-Used in one design"). Proof:
  `uv run pytest tests/unit/cli/test_blocks_cmd.py -k where tests/unit/cli/test_inspect_cmd.py -k blocks -q`.

## 4. Documentation and guide

- [ ] 4.1 `docs/dsl.md`, section "Blocks": records, `param`, port docs, versions and the lock section.
  `docs/blocks.md`: the catalog, its sources, the warning on `--from` imports, the version rules and the
  pages. `docs/design-model.md`: `block_version`. `docs/cli-contract.md`: the `blocks` verbs and
  `inspect --blocks`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 4.2 Agent guide (AGENTS.md rule 6): a tested line for `param` and the block record keywords on the
  page `design-script`, and for `blocks list`, `blocks show`, `blocks doc`, `blocks where` and the codes on
  the page `commands`. Regenerate the generated pages. Proof: `uv run python tools/gen_agent_guide.py`;
  `uv run pytest tests/unit/agent/test_pages.py -q`.

## 5. Changelog and CI

- [ ] 5.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`,
  because at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof:
  `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 5.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on
  that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4).
  Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
