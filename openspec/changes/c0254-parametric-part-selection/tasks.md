## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `cli-contract`, `fenolite-component-catalog`, `package-layering`) and the archived or open changes it depends on (c0246, c0248, c0249, c0251, c0252, c0253). Write under this task, with the date and the base commit:
  - the final names of c0246's range type and whether its exact core lives in `model` (decision 2 of `design.md`);
  - c0248's device schema and resolution step, and which of `kind`, `value`, `case`, `dielectric`, `tolerance` it lacks (decision 5);
  - c0249's lock module, its canonical form and whether `[picks]` is reserved as decision 7 expects;
  - c0251's block builder and path rules (`b.defaults`, `b.part`);
  - which open change holds a delta of "Allowed import edges" (regenerate the MODIFIED block from the living text if one was archived);
  - the next free `S-` numbers, and the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0254-parametric-part-selection --strict --no-interactive`.
  2026-10-29, base `a15e51ae` (circuits-as-code with c0246, c0247, c0248, c0249, c0250, c0251, c0278):
  - c0246's range is `fenolite.dsl.quantity.Range` and lives in `dsl` only. Instead of moving it to `model`,
    the plain records of a query (`PartQuery`, `GeneratorRequest`, `Bounds`, `Percent`, the closed key table)
    live in `fenolite.core.partquery`, which `dsl` and `pick` both import; the DSL computes the canonical text
    with `Quantity.text()` and `Range.text()`, so c0246's surface is unchanged.
  - c0248's schema (`fenolite.device.v0`, `fenolite.catalog.devices`) had `value` but lacked `kind`, `case`,
    `tolerance` and `dielectric`: they are added as optional keys (`DeviceDef`, `parse_device`, `device_text`,
    `schemas/fenolite.model.v0/library.json`; a default is omitted from the canonical JSON, so no digest
    changes). `load_devices` skips a `fenolite.family.v0` file in `devices/`. Resolution of `device=` ids stays
    at the call; a query part is resolved by the build.
  - c0249's lock is `fenolite.dsl.lock` (`fenolite.lock.v0`, `LockSection(name, resolve, exact)`); `[picks]`
    was reserved as expected. `picks` now has a resolver that delegates to the one `picks_resolver(...)`
    installs (the build and `fenolite pick` install `fenolite.cli._picks`); its tables keep the fixed key order
    `query, device, row, catalog, sha256, by, achieved`; four reasons were added (`picked`, `query-changed`,
    `row-changed`, `updated`); `needs_lock` is true for a design with a query part.
  - c0251: `Block` (a `Module`) with `b.part(name, ...)`; paths `<block path>/<name>`; `b.defaults` is added
    on `Block` and `Design.defaults` on the design.
  - No open change holds another delta of "Allowed import edges"; the MODIFIED block of this change is the
    living text plus `pick` → `model`, `catalog` (the import-graph test has the row).
  - Sources S-0940 to S-0944 (the numbers after S-0919, the highest one reserved by an open change). The open
    questions took the recommended answers (`design.md`, "Decided 2026-10-29").
  Left open: the proof `openspec validate c0254-parametric-part-selection --strict --no-interactive` could not
  be run in this session (the `openspec` CLI is not installed and running it through `npx` was refused);
  the coordinator runs it.
- [x] 0.2 Register the public sources: the E-series values (IEC 60063 values as published on a public page), the I2C specification (pull-up window and its constants) and the chip-resistor and chip-capacitor datasheets whose ratings the shipped families state, each with what is used and what is not copied. Proof: `uv run pytest tests/unit/test_provenance.py -q`.
  2026-10-29: S-0940 (E series, IEC 60063 values as published), S-0941 (NXP UM10204 Rev. 7.0: the pull-up window, VOL, IOL, tr), S-0942 (YAGEO RC_L v14: power and working voltage of 0402 to 1206, resistance ranges), S-0943 (KEMET C1002 X7R) and S-0944 (KEMET C1003 C0G) registered, each with what is used; `tests/unit/test_provenance.py` passes.
## 1. Package, queries and rows

- [x] 1.1 Add the package `src/fenolite/pick/` and its row in the import-graph test (scenario "Picks read the catalog, not the DSL"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
  2026-10-29: `src/fenolite/pick/` (stdlib-only) and its row in the import-graph test with the scenario test; passes.
- [x] 1.2 `pick/series.py`: E6 to E192 from the registered source, with the rule test (scenario "Series agree with their rule"). Proof: `uv run pytest tests/unit/pick/test_series.py -q`.
  2026-10-29: `pick/series.py` (E6 to E192 as integer mantissas) and the exact rule test naming E192's exception (index 185: 920); passes.
- [x] 1.3 `pick/query.py` and `dsl/query.py`: `PartQuery`, the closed keys per kind, the canonical text; `resistor`, `capacitor`, `inductor` exported by `fenolite.dsl` (scenarios "A query part", "Pins before the pick", "Refused queries", "Spellings give one text"). Proof: `uv run pytest tests/unit/dsl/test_query.py tests/unit/pick/test_query.py -q`.
  2026-10-29: `core/partquery.py` holds the record (see 0.1), `dsl/query.py` builds it, `pick/query.py` reads a canonical text back; `resistor`, `capacitor`, `inductor` exported by `fenolite.dsl`; a query part exposes pins 1 and 2 (`Part.call_query`, `Part.query`). Both proof files pass.
- [x] 1.4 `Design.defaults` and the block builder's `defaults`, merged design → block → call (scenarios "The block and the call win in turn", "Unknown kind"). Proof: `uv run pytest tests/unit/dsl/test_query.py -k defaults -q`.
  2026-10-29: `Design.defaults` and `Block.defaults`, merged design → block → call at read time (a range value ignores a default tolerance); passes.
- [x] 1.5 `pick/rows.py`: the `fenolite.family.v0` reader, family expansion, device ids `<family>@<code>`, c0248 device rows as candidates, `CASE_ORDER` (scenarios "A family expands to its series", "A malformed family"). Proof: `uv run pytest tests/unit/pick/test_rows.py -q`.
  2026-10-29: `pick/rows.py` (family reader, expansion `<family>@<IEC 60062 code>`, device rows, `CASE_ORDER`, project rows from `devices/` and `devices/proposed/`); a shipped `Fenolite:` family needs `sources`, a project family may omit them. Passes.
## 2. Matching, lock and build

- [x] 2.1 `pick/match.py`: matching and ranking (scenarios "A range value admits a neighbouring value", "An unknown rating never matches", "Ties are broken in order"). Proof: `uv run pytest tests/unit/pick/test_match.py -q`.
  2026-10-29: `pick/match.py`; the tie scenario uses `resistor(ohm("10k"), case="0603", tolerance=pct(1))` for its second half, since a range value with `tolerance=` is refused ("Refused queries"). Passes.
- [x] 2.2 `pick/lockpicks.py`: the `[picks]` table through c0249's lock reader and writer (scenarios "Round trip of the picks", "A project row in the lock"). Proof: `uv run pytest tests/unit/pick/test_lockpicks.py -q`.
  2026-10-29: `pick/lockpicks.py` over `fenolite.dsl.lock` (read and write of `[picks]`); the hypothesis round trip and the project-row scenario pass.
- [x] 2.3 `pick/resolve.py` and `cmd_build`: resolution with the states of decision 9, lock writes in the build's plan, `--frozen` refusal, `result.picks` (scenarios "A changed query is not a silent swap", "A cosmetic edit keeps the part", "A better match does not replace a lock", "Deterministic picks"). Proof: `uv run pytest tests/unit/pick/test_resolve.py tests/unit/cli/test_build_picks.py -q`.
  2026-10-29: `pick/resolve.py`, `cli/_picks.py` and `cmd_build` (resolution while the lock is planned; an error finding returns before the model is made, nothing written; `result.picks`, `result.generators`). `.fenolite/build.json` does not record the lock's SHA-256 yet (the lock is a planned write of its own, with its digest in the receipt). Both proof files pass.
- [x] 2.4 `pick/codes.py` and `explain.toml` entries (scenario "Every code is explained"). Proof: `uv run pytest tests/unit/cli/test_explain_cmd.py -q`.
  2026-10-29: `pick/codes.py` (`ISSUE_CODES`) in `explain.TABLES`, ten entries in `explain.toml` with `see = "pick"`, the section `## pick` in `docs/cli-contract.md`; passes.
## 3. Shipped families

- [x] 3.1 `src/fenolite/catalog/families/*.toml` (resistors E24 5 %, E96 1 %; C0G and X7R capacitors; 0402 to 1206), `CATALOG_VERSION` and `VERSIONS.toml`, `catalog list --kind family` (scenarios "Every family number has a source", "The version follows the data"). Proof: `uv run pytest tests/unit/catalog/test_families.py tests/unit/cli/test_catalog_cmd.py -q`.
  2026-10-29: sixteen families (E24 5 % and E96 1 % resistors 10 Ω to 1 MΩ; C0G 5 % and X7R 10 % 50 V capacitors, E12, spans read from the datasheets) in 0402 to 1206, `CATALOG_VERSION = "2026.10"`, `families/VERSIONS.toml`, `catalog list --kind family` and `catalog show <family>`. There is no `tests/unit/cli/test_catalog_cmd.py`: the catalog command's family test is in `tests/unit/catalog/test_families.py`, and `tests/unit/cli/test_catalog.py` passes unchanged.
## 4. Command

- [x] 4.1 `cli/cmd_pick.py`: read-only listing, `--candidates`, `--update`, `--update-all` under the mutation protocol (scenarios "A stale pick is listed", "Update a stale pick", "Example is hermetic"). Proof: `uv run pytest tests/unit/cli/test_pick_cmd.py tests/unit/cli/test_hermetic_examples.py -q`.
  2026-10-29: `cli/cmd_pick.py` (listing, `--candidates` paged by `--limit`, default 20, `--update`, `--update-all`); `examples/picks` with `EXAMPLE_PICKS`; the mutation example proposes into a prepared copy (`tests/_cliexamples.py`). Passes.
- [x] 4.2 `pick/propose.py`: `--propose --from FILE`, the `fenolite.suppliers` entry-point protocol, `--allow-offsite`, `UNVERIFIED` rows and `pick.row-unverified` (scenarios "Proposals from a file", "A proposal is not picked by itself"). Proof: `uv run pytest tests/unit/pick/test_propose.py tests/unit/cli/test_pick_cmd.py -k propose -q`.
  2026-10-29: `pick/propose.py` (`--from` CSV or JSON, the `fenolite.suppliers` group and `Supplier` protocol, `--allow-offsite`, `UNVERIFIED` records with their source line, `pick.row-unverified`); passes.
- [x] 4.3 The MCP tool for `pick` and the in-process runner follow the command. Proof: `uv run pytest tests/unit/mcp -k pick tests/unit/api -k pick -q`.
  2026-10-29: the MCP tool `fenolite_pick` and `fenolite.api.run("pick", ...)` follow the command (tests `tests/unit/mcp/test_pick_tool.py`, `tests/unit/api/test_pick_api.py`); pass.
## 5. Generators

- [x] 5.1 The generator framework: `GeneratorRequest`, rational enclosures, `gen.achieved` and `gen.unachievable`, re-evaluation of locked picks (scenarios "The achieved range encloses the exact one", "Results are reported in one text", "A wider target keeps the pair"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k "enclosure or relock" -q`.
  2026-10-29: `pick/generators/__init__.py` (`Solution`, `PI` and `LN_7_3` enclosures, texts rounded outward), re-evaluation of locked groups in `resolve`; passes.
- [x] 5.2 `voltage_divider` in both modes (scenarios "A feedback divider with E96 1 %", "Unachievable by a hair", "A tighter family succeeds", "Divider parts and nets", "The search window must be stated"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k divider tests/unit/dsl/test_generators.py -q`.
  2026-10-29: `voltage_divider`, both modes; the worked numbers come out exactly (61.9 kΩ / 13.7 kΩ, 3.224694–3.399373 V; 373 µV above at ± 3 %; 3.272477–3.34954 V with 0.1 %). Without c0252's `Rail`, divider mode takes `vin=`. Passes.
- [x] 5.3 `rc_lowpass` and `led_resistor` (scenario "An RC corner"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k "rc or led" -q`.
  2026-10-29: `rc_lowpass` and `led_resistor`. The RC scenario as written (E24 5 % with a C0G 5 % capacitor within ± 10 %) has no solution: 1.6 kΩ reaches 902–1102 Hz; the test uses a 1 % C0G family. `led_resistor` takes `vs=` and `vf=` ranges until rails (c0252) and LED records carry a voltage, and a derating factor of 1 until c0253. Passes.
- [x] 5.4 `i2c_pull_ups` and `shunt` (scenarios "Pull-ups inside the window", "A shunt with its dissipation"). Proof: `uv run pytest tests/unit/pick/test_generators.py -k "pull_ups or shunt" -q`.
  2026-10-29: `i2c_pull_ups` (takes `vdd=` until c0252's rails; modes `standard`, `fast`, `fast-plus`) and `shunt` (part class `shunt`; derating 1 until c0253). Passes.
## 6. Examples, docs and guide

- [x] 6.1 `examples/picks/` (a divider, a filter, an LED and pull-ups on the authored catalog, with its the design lock), each file with its authored-for-Fenolite line. Proof: `uv run pytest tests/unit/test_examples.py -k picks -q`.
  2026-10-29: `examples/picks/` (`design.py`, `divider.py`, their locks, two illustrative project families, `rows.csv`), with the README row; passes.
- [x] 6.2 `docs/picking.md` (queries, defaults, rows, ranking, the lock, the build states, `pick`, proposals, each generator with its formula and source), with sections in `docs/dsl.md` and `docs/cli-contract.md` ("Picks"). Proof: `uv run pytest tests/consistency -q`.
  2026-10-29: `docs/picking.md`, the section "Part queries and generators" in `docs/dsl.md`, "pick" in `docs/cli-contract.md`, the new keys in `docs/devices.md`, a row in `docs/index.md`; `tests/consistency` passes.
- [x] 6.3 Agent guide: tested lines for `pick` on `commands`, for the queries, `defaults` and the generators on `parts` and `design-script`, and for the `pick.*` and `gen.*` codes on `recovery`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  2026-10-29: the pages `parts`, `design-script` and `recovery` are within a few bytes of the 12 000-byte limit, so the tested lines went to the page `files` ("Parts chosen by parameters": a design block using every new DSL name, four `fenolite pick` lines, the stale/update/proposal recovery in prose); the codes are explained by `fenolite explain`. Generated pages rewritten; `tests/unit/agent` and `--check` pass.
## 7. Closing

- [x] 7.1 Residue: every authored file carries its authored line, and no value, name or table comes from another project. Proof: `make residue`.
  2026-10-29: `make residue`: 0 hits.
- [x] 7.2 Evidence: `H-G-PICK-DETERMINISTIC` and `H-G-GEN-ENCLOSURE` in `docs/hypotheses.md` with their measurements; the evidence matrix regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
  2026-10-29: both rows measured in `docs/hypotheses.md`; the register test and `gen_evidence_matrix.py --check` pass.
- [x] 7.3 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev` (the guard of v0.6 keeps `[Unreleased]` empty until then). Proof: `uv run pytest tests/unit -k changelog -q`.
  2026-10-29: entry under `## [Unreleased]` (dev is at 0.7.0.dev0 on circuits-as-code); `-k changelog` passes.
- [ ] 7.4 Run `make check-fast`, publish the batch to its working branch, and read the required CI jobs on the exact commit. Proof: `make check-fast`; the required jobs green on the pushed head.
  2026-10-29: `make check-fast` result in the next note. Not pushed: CI runs with the batch.