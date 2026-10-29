## Context

- **Source.** `docs/research/component-library.md`, section 1 (the table of sources and terms, and the
  three consequences: ship only authored or CC0 data, never build a database from API answers, every item
  carries its licence and source) and section 4.8 ("Supplier data, per user"); table of section 5 (c0267:
  depends on c0254, size S). Not legal advice; each plugin's terms are re-read at task 0.2.
- **What c0254 defines** (this change implements it and changes none of it):
  - `fenolite pick PATH --propose QUERY (--from FILE | --supplier NAME --allow-offsite)`, under the
    mutation protocol, writing candidate rows to `devices/proposed/<row id>.toml` beside the script;
  - the protocol `pick.propose.Supplier` and the entry-point group `fenolite.suppliers`;
  - a plugin that sends data offsite declares `sends_data_offsite: true`, and the command exits 2 without
    `--allow-offsite`, as `route` does for an offsite router;
  - proposed rows carry `evidence = "UNVERIFIED"` and are never picked unless a query names them
    (`pick.row-unverified`); proposals never write the lock.
  - c0254 open question 4 recommended no extra "until a shipped plugin needs a package": the keyring is
    that package.
- **What exists on `dev`.** Router plugins under the entry-point group `fenolite.routers`, listed by
  `capabilities` with `sends_data_offsite`; the closed extras list of `pyproject.toml`, guarded by
  `tests/unit/test_pyproject_invariants.py`; `fenolite fetch` (downloads under `--confirm`, `FEN-6003`
  retryable on failure); the rule "Third-party imports only in extras-guarded modules".

## Goals / Non-Goals

**Goals**

- A user with an account at a distributor gets ranked proposals for a query in one command, with the
  attribution the terms require, without Fenolite holding a key or a copy of anyone's data.
- What may be cached, sent and written is data in the plugin, tested against the documentation page.
- Builds stay offline and deterministic: no build reads a supplier, and the written rows are the
  reviewed bytes.

**Non-Goals**

- See the proposal. Also: no background refresh, no lifecycle monitoring of a BOM, no proxy service.

## Today and proposed

**Today (after c0254):**

```
$ fenolite pick examples/picks --propose "capacitor(100nF, rating>=25V, case=0603)" --supplier digikey --allow-offsite
exit 2  FEN-2001  unknown supplier 'digikey'   hint: no plugin is registered under fenolite.suppliers
```

**Proposed:**

```
$ pip install "fenolite[suppliers]"          # optional: keyring support
$ export FENOLITE_DIGIKEY_CLIENT_ID=...  FENOLITE_DIGIKEY_CLIENT_SECRET=...   # the user's own app
$ fenolite pick examples/picks --propose "capacitor(100nF, rating>=25V, case=0603, dielectric=X7R)" \
    --supplier digikey --allow-offsite --limit 5 --dry-run --json
```

```json
{"result": {"proposals": [
   {"mpn": "EX03R104KAT", "manufacturer": "Example Passive",
    "datasheet": "https://example.invalid/ex-mlcc.pdf",
    "reported": {"capacitance": "100nF", "voltage": "25V", "case": "0603", "dielectric": "X7R"},
    "offer": {"stock": 12000, "price": "0.004 USD @ 4000", "lifecycle": "active"},
    "decoded_by": "Example:EX_MLCC 1.0.0", "row": "Proposed:EX03R104KAT", "complete": true,
    "attribution": "<the attribution text the source requires>"}],
  "plan": [{"path": "devices/proposed/EX03R104KAT.toml", "action": "create"}],
  "plan_id": "…"},
 "evidence": {"level": "UNVERIFIED"}}
```

(All names in this example are illustrative and authored for Fenolite; the fake response the test serves
has the same shape.)

The planned row holds the identity, the provenance and, because c0263 decoded the MPN, the parameters of a
Fenolite-authored grammar, never the supplier's:

```toml
schema = "fenolite.device.v0"
id = "Proposed:EX03R104KAT"
summary = "Proposed by a supplier lookup; review against the datasheet"
manufacturer = "Example Passive"
mpn = "EX03R104KAT"
datasheet = "https://example.invalid/ex-mlcc.pdf"
evidence = "UNVERIFIED"
licence = "see source terms"
# symbol, footprint, pins, kind, value and ratings: from Example:EX_MLCC 1.0.0 (c0263 decode)

[provenance]
source = "supplier:digikey"
query = "capacitor(100nF, rating>=25V, case=0603, dielectric=X7R)"
retrieved = "2026-10-29T00:00:00Z"        # --timestamp, else the time of the dry run
attribution = "<the attribution text the source requires>"
decoded_by = "Example:EX_MLCC 1.0.0"
```

## Decisions

### 1. One in-tree package behind an extra, stdlib HTTP

`src/fenolite/suppliers/` holds the shared machinery and one module per source. HTTPS uses
`urllib.request` with the default TLS context (which honours the user's proxy and CA settings), JSON uses
`json`, OAuth2 client credentials are two form posts. The only third-party package is `keyring`, imported
inside `credentials.py` under `try/except ImportError` (rule "Third-party imports only in extras-guarded
modules"). The extra is `suppliers = ["keyring>=25"]`; without it, environment variables still work.

- **Plugins are registered** in `pyproject.toml` under `[project.entry-points."fenolite.suppliers"]`, as
  the routers are. A plugin is `available()` when its credentials are found; it never reads them before it
  is named.
- **Import edges.** `suppliers` → `pick` (the `Supplier` protocol and the row model), `catalog`, `model`
  (and `core`). No other package imports `suppliers`; `pick` reaches it only through the entry points.
- **Alternatives.** A separate distribution `fenolite-suppliers`: cleaner isolation, but a second release
  train for five small modules, and the policy tests would live away from the contract they guard.
  `requests`/`httpx`: a dependency for what the standard library does. Rejected; a separate distribution
  stays possible later without changing the protocol.

### 2. Credentials: the user's own, never stored by Fenolite

`credentials.lookup(source)` reads, in order: environment variables `FENOLITE_<SOURCE>_<NAME>` (for example
`FENOLITE_DIGIKEY_CLIENT_ID`, `FENOLITE_DIGIKEY_CLIENT_SECRET`, `FENOLITE_MOUSER_API_KEY`,
`FENOLITE_NEXAR_CLIENT_ID`, `FENOLITE_NEXAR_CLIENT_SECRET`, `FENOLITE_FARNELL_API_KEY`), then the keyring
service `fenolite.suppliers.<source>` when the extra is installed.

- Never from a project file, `.fenolite/`, a command argument (it would land in shell history and in the
  reply's echoed arguments) or a Fenolite default. No Fenolite key exists, so no key is ever shared.
- Secrets are held in a `Secret` value whose `repr` and `str` are `***`; every error, log line, reply,
  plan and receipt is checked by a test that injects a canary secret and greps every output for it. Query
  strings that carry a key (one source sends it in the URL) are redacted before any message is built.
- Missing credentials: exit 6, `FEN-6001`, hint naming the variables and the keyring service (never their
  values). Rejected credentials (HTTP 401 or 403): exit 6, `FEN-6004` (new, not retryable).
- `fenolite suppliers login` to store a key in the keyring is left out: the keyring's own CLI does it
  (open question 2).

### 3. Source policy as data

Each plugin declares one frozen `SourcePolicy`:

| field | meaning |
|---|---|
| `name`, `title` | `digikey`, `DigiKey` … |
| `terms` | source ids of the terms pages in `docs/evidence/sources.md` |
| `attribution` | the text and link the terms require, shown with every proposal and kept in the row's provenance |
| `cache` | `none` or `process`, with `max_age_s`; never longer than `terms_max_age_s` |
| `terms_max_age_s` | what the terms allow: Farnell 0, Nexar 86 400, DigiKey and Mouser the session (process) |
| `rate` | requests per second and per day the documentation states, enforced client-side |
| `sends` | what leaves the machine: the query keywords and the credentials, nothing of the design |
| `persist` | the fields of an answer that may be written to the project: `manufacturer`, `mpn`, `datasheet` |
| `evidence` | of the plugin's facts (`INFERRED` or `UNVERIFIED`) |

- **Chosen cache scopes.** `none` for Farnell; `process` (one command run) for DigiKey, Mouser and Nexar.
  Nexar's terms would allow 24 h on disk; Fenolite keeps no disk cache at all, so nothing outlives a run
  and nothing can become a database (open question 3).
- `docs/formats/suppliers/<name>.md` records each value with its source and label; a test compares every
  plugin's policy with its page, so a terms change is one reviewed edit in two places.

### 4. What is sent

A plugin turns the **canonical query text** (c0254 decision 8) into the source's keyword or parametric
search: value, case, dielectric, rating, tolerance. Nothing else of the design is read: no script, no
netlist, no board, no project name. `capabilities` and the plan state `sends` for the named plugin. The
offsite gate is c0254's `--allow-offsite` (exit 2 without).

### 5. What is written: identity, provenance, and a Fenolite grammar's parameters

The research is explicit that answers are "written nowhere persistent". A proposal row is the user's
decision to consider one part, so it keeps only the policy's `persist` fields (manufacturer, MPN,
datasheet link) and the provenance (source, canonical query, retrieval time, attribution).

- **Parameters.** When a c0263 grammar family decodes the MPN inside its validity matrix, the row gets that
  candidate's symbol, footprint, pins, kind, value and ratings from the Fenolite-authored grammar, with
  `decoded_by`, and is `complete`. Otherwise the row has the identity only, `supplier.row-incomplete` (info)
  names the keys to fill from the datasheet, and c0254's reader reports the row as not pickable until they
  are filled.
- **Shown only.** The supplier's reported parameters, stock, price, packaging and lifecycle appear in
  `result.proposals` (and the text view) with the attribution, and are written to no file, cache or log.
- **Determinism.** `--confirm --plan ID` writes the bytes reviewed in the dry run without a second request
  (the mutation protocol already stores the planned bytes); `--timestamp` fixes `retrieved`.
- **Alternative considered:** write the reported parameters into the row so that it is pickable at once.
  It turns each proposal into a cached copy of the supplier's product data, which Farnell's terms forbid
  outright and the others limit. Rejected; open question 1 asks whether a source whose terms allow it may
  opt in.

### 6. Never in the build path

`build`, `check`, `place`, `route`, `export` and every other command except `pick --propose --supplier`
never import `fenolite.suppliers`. A test runs `build` and `pick` (without `--supplier`) on the picks
example with `socket.socket` patched to raise and asserts `fenolite.suppliers` is absent from
`sys.modules`. `capabilities` lists the plugins from the entry-point metadata and each plugin's static
policy, without reading credentials beyond their presence and without a network call.

### 7. Rate limits and failures

- A token bucket per source per process, from `policy.rate`, with an injectable monotonic clock; a request
  waits for a token up to `--timeout` (default 30 s) and then fails.
- HTTP 429: honour `Retry-After` up to the remaining timeout, once, with `supplier.rate-limited`
  (warning); still refused: exit 6, `FEN-6003` (retryable), naming the source.
- Network errors, timeouts and 5xx: `FEN-6003` (retryable). 401/403: `FEN-6004`. A response that does not
  match the documented shape: `FEN-3004` naming the source and the missing key (not retryable).
- Responses are capped at 4 MiB, redirects are followed only within the policy's host list.

### 8. The plugins

| plugin | auth | search used | notes |
|---|---|---|---|
| `digikey` | OAuth2 client credentials, the user's app | keyword search of the Product Information API v4 | 1 000 requests a day (research, section 1) |
| `mouser` | API key in the request | keyword search of the Search API | terms page read second-hand: `UNVERIFIED` until task 0.2 |
| `nexar` | OAuth2 client credentials | GraphQL part search | process cache only, though the terms allow 24 h |
| `farnell` | API key | keyword search of the product search API | no cache of any kind |
| `jlc` | the user's approved credentials | — | not registered until task 5.1 reads the approved documentation |

Each endpoint, parameter name and response key is a fact of the public API documentation, recorded in
`docs/formats/suppliers/<name>.md` with its source; no SDK or client code of a source is copied.

### 9. Offline tests with authored fake responses

`http.py` sends through a `Transport` protocol; tests inject `FakeTransport`, which serves files from
`tests/fixtures/suppliers/<name>/*.json`. Each file is authored for Fenolite after the documented response
shape, uses illustrative manufacturers, MPNs and `example.invalid` links, and its sidecar
`<file>.source.toml` names the documentation page and the authored-for-Fenolite line (JSON has no
comments). Every supplier test runs with `socket.socket` patched to raise. No test calls a live service;
`make supplier-smoke` (not in CI) lets a maintainer run one query per source with their own keys.

### 10. Codes

| code | severity | when |
|---|---|---|
| `supplier.proposed` | info | one per proposal row planned |
| `supplier.row-incomplete` | info | a row with identity only; names the keys to fill |
| `supplier.no-results` | info | the source returned nothing for the query |
| `supplier.rate-limited` | warning | a request waited on `Retry-After` |
| `supplier.unmapped` | info | a reported parameter that maps to no query key (shown, not used) |

They are `fenolite.suppliers.codes.ISSUE_CODES`, explained by `fenolite explain` (heading `suppliers`).
New `FEN-6004` "supplier refused the credentials" (exit 6, not retryable, hint: check the variables or
the keyring entry named). `FEN-6001` (credentials missing) and `FEN-6003` (request failed, retryable) keep
their meanings.

## Files and public API

- `suppliers/base.py`: `SupplierPlugin` (implements `pick.propose.Supplier`: `name`, `policy`,
  `available()`, `propose(query, limit) -> list[Proposal]`).
- `policy.py`: `SourcePolicy`, `CacheScope`, `RateLimit`. `credentials.py`: `lookup`, `Secret`.
- `http.py`: `Transport`, `UrllibTransport`, `request_json`. `cache.py`: `ProcessCache`.
  `ratelimit.py`: `TokenBucket`. `rows.py`: `proposal_row(proposal, families)` (c0263 decode).
- `digikey.py`, `mouser.py`, `nexar.py`, `farnell.py`; `codes.py`.
- `docs/suppliers.md` (setup per source, what is sent, what is written, attribution).

## Relation to the other changes of the batch

- **c0254**: the hook, the gate, the `UNVERIFIED` rule; nothing of it changes.
- **c0263**: decode of an MPN gives the row its parameters from a Fenolite grammar.
- **c0248**: the proposed row is a device record; its `provenance` keys follow c0248's stamp where they
  overlap.
- **c0265** (datasheet proposals) completes an incomplete row from the datasheet the row links to.
- **c0266**: supplier answers never enter the data repository; a row moves there only after a review
  against the datasheet, and then without supplier-derived fields beyond the MPN.

## Risks / Trade-offs

- **Terms change.** Mitigation: policy as data, one page per source, re-read at each plugin release; the
  plugin is `UNVERIFIED` for terms read second-hand.
- **Incomplete rows feel useless.** They are the honest result when no grammar knows the series; c0263
  grammars and c0265 close the gap without copying supplier data.
- **A user commits a key.** Keys are never written by Fenolite; `make residue` already scans for absolute
  paths, and the docs say to use the keyring.

## Open questions

1. **Opt-in persistence of reported parameters** for a source whose terms allow it. Recommended: no for
   now; parameters come from grammars or the datasheet.
2. **A `fenolite suppliers login` helper.** Recommended: no; document `keyring set fenolite.suppliers.<source>
   <name>`.
3. **Nexar's 24 h disk cache.** Recommended: no disk cache for any source; one run is the session.
4. **JLC.** Recommended: register the plugin only after the maintainer, with approved access, has
   recorded its documentation and terms; until then it is not listed.
5. **Naming distributors in public files.** The research page names them; recommended: allowed for
   plugin names and policy pages, as public services, never in examples or fixtures (illustrative names).
