# Supplier lookup

Fenolite registers DigiKey, Mouser, Nexar and Farnell as optional supplier plugins. All four production
policies currently report **unavailable**: the source review has not established permission to persist
identity proposals. Credentials cannot override that gate. JLC is unregistered until approved maintainer
documentation and terms are recorded. Source facts, gaps and policy values are in
[`docs/formats/suppliers/`](formats/suppliers/).

Run discovery offline:

```sh
fenolite capabilities --no-tools --json --fields suppliers
```

`available` includes the source-rights gate. `credential_env_present` checks variable names only;
keyring values and environment values are never read during discovery. `extra_installed` reports
optional keyring installation. Source acknowledgement text is not a claim that required attribution
wording has been established. Current policies use no cache, no persistence and `UNVERIFIED` evidence.

## Your account and credentials

Install `fenolite[suppliers]` for optional system-keyring support; the core has no runtime dependencies.
Environment-only credentials work without keyring. Obtain access through your own supplier account and
read the applicable documentation and terms. No Fenolite key, shared account or default credential exists.
Readiness also requires a reviewed implementation and documented rights; entering a key is insufficient.

| Source | Environment variables | Keyring service / user names |
|---|---|---|
| DigiKey | `FENOLITE_DIGIKEY_CLIENT_ID`, `FENOLITE_DIGIKEY_CLIENT_SECRET` | `fenolite.suppliers.digikey` / `CLIENT_ID`, `CLIENT_SECRET` |
| Mouser | `FENOLITE_MOUSER_API_KEY` | `fenolite.suppliers.mouser` / `API_KEY` |
| Nexar | `FENOLITE_NEXAR_CLIENT_ID`, `FENOLITE_NEXAR_CLIENT_SECRET` | `fenolite.suppliers.nexar` / `CLIENT_ID`, `CLIENT_SECRET` |
| Farnell | `FENOLITE_FARNELL_API_KEY` | `fenolite.suppliers.farnell` / `API_KEY` |

For each named credential, the environment takes precedence, then the optional keyring is queried.
The keyring's own `keyring set SERVICE USERNAME` command can store a value interactively. Never put
credentials in a script, project file, command argument, report or shared key store.

## Explicit proposal workflow

For an enabled provider or a separately installed legacy plugin, the proposal form is:

```sh
fenolite pick examples/families --propose 'capacitor(100nF, rating>=25V, case=0603)' --supplier mouser --allow-offsite --limit 5 --timeout 30 --timestamp 2026-11-01T00:00:00Z --dry-run --json
```

Current built-ins stop with `FEN-6001` before reading credentials or transport. An enabled rich lookup
sends only the canonical query keywords and that user's credentials after `--allow-offsite`. It does not
execute the design script or send a script, board, netlist, project name or BOM. `result.sends` identifies
the allowed categories. `--limit` is 1..50; `--timeout` bounds the whole lookup, rate waits included, above
zero and at most 300 seconds. The generic HTTP client enforces HTTPS host allowlists, bounded response
size, run-local request pacing and at most one numeric `Retry-After` retry that fits the remaining time.
Run-local limits do not replace a provider's account-wide quota; concurrent tools share that quota.

Rich results contain `result.proposals`: identity, attribution, grammar suggestion status and transient
`offer` / `reported` fields. The latter appear only in the immediate reply. They are excluded from
stored and replayed plan results, written drafts, receipts and disk caches. The same attribution
travels with the displayed identity, text reply and draft provenance.

Where an enabled source policy explicitly permits identity persistence, confirmation writes the reviewed
`devices/proposed/<safe-MPN>-<digest>.toml` bytes. The distinct schema `fenolite.supplier-proposal.v0`
carries `UNVERIFIED`, `licence="see source terms"`, permitted identity fields, and provenance (`source`,
canonical `query`, `retrieved`, `attribution`). It is a review draft, not a complete DeviceDef. Picks skip
these drafts, including explicit queries, until a person verifies rights and datasheet facts and authors
a complete device record. Legacy complete `Supplier.propose` rows retain their existing acceptance rules.

A unique valid local c0263 grammar may provide a `[decoded].device_toml` review suggestion and
`decoded_by`; those parameters come from the authored grammar. Supplier attributes never supply device
parameters. An unknown MPN gives `supplier.row-incomplete`; fill symbol, footprint, pins, kind, value and
ratings in the reviewed device. `complete=true` means a grammar suggestion exists, not approval to use it.
`--timestamp` fixes provenance time for deterministic planned bytes.

Review the plan, then repeat its command with `--confirm --plan ID` in place of `--dry-run`.
Confirmation writes the staged bytes without importing a supplier or requesting again. It still refuses
changed targets or bound grammar inputs. The file SHA-256 in the receipt identifies the reviewed output.
There is no disk/shared supplier cache. A future source with verified process-cache rights may use one
lookup object's bounded memory cache, never a module global or a cache shared by runs or users.

## Errors and evidence

`FEN-6001` means missing credentials or unavailable source policy; the hint distinguishes them.
`FEN-6005` means refused credentials (401/403), exit 6 and not retryable; check your own account and the
named variables/keyring service. Network/timeout/source failure or repeated 429 gives retryable
`FEN-6003`. Undocumented response shapes give `FEN-3004`. Error messages omit credential values,
credential-bearing URLs and response bodies. `fenolite explain supplier.rate-limited` and the other
`supplier.*` codes explain the findings.

All four documented request/response mappings have authored offline fixtures. DigiKey and Nexar
obtain a per-lookup Bearer token through the same timeout/host/rate client; received tokens join the
redaction set and never enter a persistent cache. Nexar requests documented basic identity/offers only;
paid specs, lifecycle, datasheets and ECAD add-ons are not assumed. Source/GraphQL errors refuse partial
answers, and malformed selected containers are not treated as absent fields. These tests do not clear
any production rights gate. The socket-blocked tests
prove local mechanics (`H-G-SUPPLIER-OFFLINE`, `INFERRED`); they do not verify a live API, account access,
licensing, current quotas or a supplier's response. No live supplier smoke test runs in CI.


Rich plugin integration explicitly opts in with `proposal_api="fenolite.supplier-lookup.v0"` and
`lookup(...)->SupplierLookup`. A legacy plugin's unrelated `lookup` method does not change its
`Supplier.propose` behavior.
