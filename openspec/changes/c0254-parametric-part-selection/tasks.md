## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `cli-contract`, `fenolite-component-catalog`, `package-layering`) and the archived or open changes it depends on (c0246, c0248, c0249, c0251, c0252, c0253). Write under this task, with the date and the base commit:
  - the final names of c0246's range type and whether its exact core lives in `model` (decision 2 of `design.md`);
  - c0248's device schema and resolution step, and which of `kind`, `value`, `case`, `dielectric`, `tolerance` it lacks (decision 5);
  - c0249's lock module, its canonical form and whether `[picks]` is reserved as decision 7 expects;
  - c0251's block builder and path rules (`b.defaults`, `b.part`);
  - which open change holds a delta of "Allowed import edges" (regenerate the MODIFIED block from the living text if one was archived);
  - the next free `S-` numbers, and the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0254-parametric-part-selection --strict --no-interactive`.
- [ ] 0.2 Register the public sources: the E-series values (IEC 60063 values as published on a public page), the I2C specification (pull-up window and its constants) and the chip-resistor and chip-capacitor datasheets whose ratings the shipped families state, each with what is used and what is not copied. Proof: `uv run pytest tests/unit/test_provenance.py -q`.

## 1. Package, queries and rows

- [ ] 1.1 Add the package `src/fenolite/pick/` and its row in the import-graph test (scenario "Picks read the catalog, not the DSL"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 1.2 `pick/series.py`: E6 to E192 from the registered source, with the rule test (scenario "Series agree with their rule"). Proof: `uv run pytest tests/unit/pick/test_series.py -q`.
- [ ] 1.3 `pick/query.py` and `dsl/query.py`: `PartQuery`, the closed keys per kind, the canonical text; `resistor`, `capacitor`, `inductor` exported by `fenolite.dsl` (scenarios "A query part", "Pins before the pick", "Refused queries", "Spellings give one text"). Proof: `uv run pytest tests/unit/dsl/test_query.py tests/unit/pick/test_query.py -q`.
- [ ] 1.4 `Design.defaults` and the block builder's `defaults`, merged design → block → call (scenarios "The block and the call win in turn", "Unknown kind"). Proof: `uv run pytest tests/unit/dsl/test_query.py -k defaults -q`.
- [ ] 1.5 `pick/rows.py`: the `fenolite.family.v0` reader, family expansion, device ids `<family>@<code>`, c0248 device rows as candidates, `CASE_ORDER` (scenarios "A family expands to its series", "A malformed family"). Proof: `uv run pytest tests/unit/pick/test_rows.py -q`.

## 2. Matching, lock and build

- [ ] 2.1 `pick/match.py`: matching and ranking (scenarios "A range value admits a neighbouring value", "An unknown rating never matches", "Ties are broken in order"). Proof: `uv run pytest tests/unit/pick/test_match.py -q`.
- [ ] 2.2 `pick/lockpicks.py`: the `[picks]` table through c0249's lock reader and writer (scenarios "Round trip of the picks", "A project row in the lock"). Proof: `uv run pytest tests/unit/pick/test_lockpicks.py -q`.
- [ ] 2.3 `pick/resolve.py` and `cmd_build`: resolution with the states of decision 9, lock writes in the build's plan, `--frozen` refusal, `result.picks` (scenarios "A changed query is not a silent swap", "A cosmetic edit keeps the part", "A better match does not replace a lock", "Deterministic picks"). Proof: `uv run pytest tests/unit/pick/test_resolve.py tests/unit/cli/test_build_picks.py -q`.
- [ ] 2.4 `pick/codes.py` and `explain.toml` entries (scenario "Every code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.

## 3. Shipped families

- [ ] 3.1 `src/fenolite/catalog/families/*.toml` (resistors E24 5 %, E96 1 %; C0G and X7R capacitors; 0402 to 1206), `CATALOG_VERSION` and `VERSIONS.toml`, `catalog list --kind family` (scenarios "Every family number has a source", "The version follows the data"). Proof: `uv run pytest tests/unit/catalog/test_families.py tests/unit/cli/test_catalog_cmd.py -q`.

## 4. Command

- [ ] 4.1 `cli/cmd_pick.py`: read-only listing, `--candidates`, `--update`, `--update-all` under the mutation protocol (scenarios "A stale pick is listed", "Update a stale pick", "Example is hermetic"). Proof: `uv run pytest tests/unit/cli/test_pick_cmd.py tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 4.2 `pick/propose.py`: `--propose --from FILE`, the `fenolite.suppliers` entry-point protocol, `--allow-offsite`, `UNVERIFIED` rows and `pick.row-unverified` (scenarios "Proposals from a file", "A proposal is not picked by itself"). Proof: `uv run pytest tests/unit/pick/test_propose.py tests/unit/cli/test_pick_cmd.py -k propose -q`.
- [ ] 4.3 The MCP tool for `pick` and the in-process runner follow the command. Proof: `uv run pytest tests/unit/mcp -k pick tests/unit/api -k pick -q`.

## 5. Generators

- [ ] 5.1 The generator framework: `GeneratorRequest`, rational enclosures, `gen.achieved` and `gen.unachievable`, re-evaluation of locked picks (scenarios "The achieved range encloses the exact one", "Results are reported in one text", "A wider target keeps the pair"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k "enclosure or relock" -q`.
- [ ] 5.2 `voltage_divider` in both modes (scenarios "A feedback divider with E96 1 %", "Unachievable by a hair", "A tighter family succeeds", "Divider parts and nets", "The search window must be stated"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k divider tests/unit/dsl/test_generators.py -q`.
- [ ] 5.3 `rc_lowpass` and `led_resistor` (scenario "An RC corner"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k "rc or led" -q`.
- [ ] 5.4 `i2c_pull_ups` and `shunt` (scenarios "Pull-ups inside the window", "A shunt with its dissipation"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k "pull_ups or shunt" -q`.

## 6. Examples, docs and guide

- [ ] 6.1 `examples/picks/` (a divider, a filter, an LED and pull-ups on the authored catalog, with its the design lock), each file with its authored-for-Fenolite line. Proof: `uv run pytest tests/unit/test_examples.py -k picks -q`.
- [ ] 6.2 `docs/picking.md` (queries, defaults, rows, ranking, the lock, the build states, `pick`, proposals, each generator with its formula and source), with sections in `docs/dsl.md` and `docs/cli-contract.md` ("Picks"). Proof: `uv run pytest tests/consistency -q`.
- [ ] 6.3 Agent guide: tested lines for `pick` on `commands`, for the queries, `defaults` and the generators on `parts` and `design-script`, and for the `pick.*` and `gen.*` codes on `recovery`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 7. Closing

- [ ] 7.1 Residue: every authored file carries its authored line, and no value, name or table comes from another project. Proof: `make residue`.
- [ ] 7.2 Evidence: `H-G-PICK-DETERMINISTIC` and `H-G-GEN-ENCLOSURE` in `docs/hypotheses.md` with their measurements; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 7.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.
