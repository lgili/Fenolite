## ADDED Requirements

### Requirement: Supplier extra and plugins
The extra `suppliers` SHALL add only `keyring`, and `fenolite.suppliers` SHALL register the plugins `digikey`, `mouser`, `nexar` and `farnell` under the entry-point group `fenolite.suppliers`, each implementing c0254's `pick.propose.Supplier` with `sends_data_offsite` true. HTTPS and JSON MUST use the standard library, and `import fenolite.suppliers` MUST succeed without the extra.

#### Scenario: Plugins without the extra
- **GIVEN** an environment where `keyring` cannot be imported
- **WHEN** `uv run pytest tests/unit/suppliers/test_registry.py` loads the entry points
- **THEN** the four plugins load, and each reads credentials from environment variables only

### Requirement: The user's own credentials
A plugin SHALL read credentials only from the variables `FENOLITE_<SOURCE>_<NAME>` and then the keyring service `fenolite.suppliers.<source>`, never from a project file, an argument or a default. Secrets MUST never appear in a reply, error, plan, receipt, log or written file; missing ones MUST exit 6 with `FEN-6001` naming the variables, never their values.

#### Scenario: A secret never leaks
- **GIVEN** a canary secret in `FENOLITE_DIGIKEY_CLIENT_SECRET` and a fake transport answering 401
- **WHEN** `uv run pytest tests/unit/suppliers/test_credentials.py -k canary` runs the proposal
- **THEN** the exit code is 6 with `FEN-6004`, and the canary appears in none of stdout, stderr, the plan or any file under the project

### Requirement: Source policy as data
Each plugin SHALL declare one `SourcePolicy` with `terms`, `attribution`, `cache`, `terms_max_age_s`, `rate`, `sends`, `persist` and `evidence`, equal to the values recorded with their sources in `docs/formats/suppliers/<name>.md`. A cache age MUST NOT exceed `terms_max_age_s`, and Farnell's cache MUST be `none`.

#### Scenario: Policies agree with their pages
- **WHEN** `uv run pytest tests/unit/suppliers/test_policy.py` runs
- **THEN** every plugin's policy equals its documentation page, every `terms` id is registered in `docs/evidence/sources.md`, and no cache outlives its terms

### Requirement: No persistent cache
Supplier answers SHALL be cached at most for one process and only when the policy's scope is `process`; nothing of an answer MUST be written to disk, a user cache folder or the project, except the `persist` fields of a confirmed proposal row.

#### Scenario: Nothing outlives the run
- **GIVEN** a fake transport and a temporary home and cache folder
- **WHEN** two proposals for one query run in one process, then a third in a new process
- **THEN** the second sends no request, the third sends one, and no file was created outside the planned rows

### Requirement: What is sent offsite
A plugin SHALL build its request only from the canonical query text and its credentials, and MUST NOT read the script, netlist, board or project name. `capabilities` and the plan MUST state the policy's `sends` for the named plugin.

#### Scenario: Only the query leaves
- **GIVEN** a fake transport that records every request, and a script whose design is named `secret-board`
- **WHEN** a proposal runs for `capacitor(100nF, rating>=25V, case=0603)`
- **THEN** every recorded request holds only terms of the query and the credentials, and none holds `secret-board`

### Requirement: Proposal rows
A confirmed proposal SHALL write `devices/proposed/<MPN>.toml` with only the policy's `persist` fields, `evidence = "UNVERIFIED"`, `licence = "see source terms"` and `[provenance]` (`source`, `query`, `retrieved`, `attribution`). Price, stock, lifecycle and reported parameters MUST appear only in `result.proposals`.

#### Scenario: Offers are shown, not written
- **GIVEN** the fake DigiKey response `tests/fixtures/suppliers/digikey/keyword_mlcc.json`
- **WHEN** the proposal is confirmed with `--confirm --plan <plan_id>`
- **THEN** `result.proposals` held stock and price, and the written row holds neither, nor the reported capacitance

### Requirement: Parameters from a grammar
When a c0263 family decodes a proposed MPN inside its validity matrix, the row SHALL take that candidate's symbol, footprint, pins, kind, value and ratings and `decoded_by`; otherwise it MUST hold the identity only and give `supplier.row-incomplete` naming the keys to fill.

#### Scenario: A decoded and an unknown MPN
- **GIVEN** `examples/families/` and a fake answer holding `EX03R104KAT` and an MPN no family decodes
- **WHEN** the proposal runs with `--dry-run --json`
- **THEN** the first entry is `complete` with `decoded_by` `Example:EX_MLCC 1.0.0`, and the second gives `supplier.row-incomplete`

### Requirement: Confirm writes the reviewed bytes
`--confirm --plan ID` of a supplier proposal SHALL write the bytes of the dry run without a new request, and `--timestamp` MUST fix `retrieved`; two dry runs over the same fake responses with the same timestamp MUST plan the same bytes.

#### Scenario: No request on confirm
- **GIVEN** a dry run over a fake transport
- **WHEN** it is confirmed with its plan id
- **THEN** the transport records no request during the confirm, and the receipt's SHA-256 equals the planned bytes'

### Requirement: Attribution
Every proposal in `result.proposals`, in the text view and in a written row's provenance SHALL carry the policy's `attribution` of its source.

#### Scenario: Attribution travels with the row
- **WHEN** `uv run pytest tests/unit/suppliers/test_rows.py -k attribution` confirms one proposal per plugin
- **THEN** each reply entry and each written row holds its source's attribution text

### Requirement: Rate limits and failures
A plugin SHALL enforce its policy's rate per process, honour one `Retry-After` within `--timeout` with `supplier.rate-limited`, and map failures: 401/403 to `FEN-6004`, network errors, timeouts, 5xx and a repeated 429 to `FEN-6003` (retryable), an undocumented response shape to `FEN-3004`.

#### Scenario: A repeated 429
- **GIVEN** a fake transport answering 429 with `Retry-After: 1` twice and a fake clock
- **WHEN** a proposal runs
- **THEN** the exit code is 6 with `FEN-6003`, `retryable` true, and `issues` held `supplier.rate-limited`

### Requirement: Never in the build path
No command other than `pick --propose --supplier` SHALL import `fenolite.suppliers`, and `capabilities` MUST list plugins from entry-point metadata and static policies without a network call.

#### Scenario: A build stays offline
- **GIVEN** `socket.socket` patched to raise and supplier credentials set
- **WHEN** `fenolite build examples/picks --dry-run` and `fenolite pick examples/picks` run in process
- **THEN** both succeed and `fenolite.suppliers` is not in `sys.modules`

### Requirement: Offline tests with authored responses
Every supplier test SHALL run with `socket.socket` patched to raise, through a fake transport serving `tests/fixtures/suppliers/<name>/*.json`. Each fixture MUST be authored for Fenolite after the documented shape, with illustrative names and `example.invalid` links, and a sidecar naming its source and the authored line.

#### Scenario: Fixtures are authored and offline
- **WHEN** `uv run pytest tests/unit/suppliers -q` runs
- **THEN** it passes with the socket patched, and every fixture has a sidecar whose source id is registered

### Requirement: Supplier codes
`supplier.rate-limited` (warning), `supplier.proposed`, `supplier.row-incomplete`, `supplier.no-results` and `supplier.unmapped` (info) SHALL be `fenolite.suppliers.codes.ISSUE_CODES`, each explained by `fenolite explain`.

#### Scenario: Every supplier code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** every `supplier.*` code has an entry whose `see` is the heading `suppliers`
