## Context

c0254 supplies `pick.propose.Supplier`, `fenolite.suppliers` entry-point discovery and the explicit
`--propose --supplier --allow-offsite` mutation path. c0263 supplies exact grammar decoding. The base
is 8d74a798, with those prerequisites implemented and no runtime core dependencies. Source research
must distinguish documented protocol facts from permission to retain a supplier's content.

## Decisions (2026-11-01)

### 1. Optional stdlib framework and four discoverable providers

Use `fenolite.suppliers`, stdlib HTTPS/JSON, and `suppliers=["keyring>=25"]`. Keyring is lazy and
optional; environment-only credentials work without it. Four entry points register DigiKey, Mouser,
Nexar and Farnell. Importing them reads no credentials and sends no request. Preserve legacy
`Supplier.propose(query)->Sequence[Mapping[str,str]]` plugins. The rich optional `lookup` hook returns
`SupplierLookup` with typed identity drafts, issues and declared sent categories.

`suppliers` imports only its own package, core, pick, catalog and model. Other source packages never
import it, including CLI. The CLI reaches named providers through entry points; static discovery and
issue-code tables live in `pick.supplier_policy`. `suppliers.codes` re-exports that table. Existing
layering edges remain unchanged; a separate supplier-boundary requirement avoids overwriting concurrent
Allowed import edges deltas.

### 2. Evidence gates precede credentials and transport

The primary source review is recorded under `docs/formats/suppliers/`, S-1100..S-1110. DigiKey's current
terms were inaccessible; Mouser terms returned 403; Nexar's API-terms accordion body was unavailable;
readable Farnell partner terms prohibit recording/storing API content and establish no durable identity
exception. No session/24-hour content-cache licence is inferred from old research, snippets, token
expiry or regional terms. Prescribed attribution wording remains unverified.

All four production policies therefore have `ready=false`, `persist=[]`, `cache=none`, age zero and
`UNVERIFIED` evidence. Lookup fails before credentials or transport, with FEN-6001 and a source-review
hint. A key's presence and broad task authorization do not clear a source-rights gate. Mouser/Farnell
have source-shaped request/mapping code proved under explicitly fictional test permissions; this does
not enable production. DigiKey/Nexar response mapping remains unavailable rather than invented.
JLC task 5.1 stays open and its plugin unregistered until approved maintainer documentation exists.

### 3. Per-user secrets and bounded HTTP

Named credentials come from `FENOLITE_<SOURCE>_<NAME>`, then system keyring service
`fenolite.suppliers.<source>`. Never read project files, arguments or defaults for credentials. `Secret`
prints as `***`; response strings are redacted in raw, JSON-escaped and URL-encoded forms (percent-escape hex casing ignored) before
caching or constructing drafts. Transport exceptions, bodies and credential-bearing URLs are omitted
from errors. Missing credentials use FEN-6001; 401/403 use FEN-6005, exit 6 and not retryable.

Default TLS/proxy/CA behavior is supplied by urllib. HTTPS hosts and redirects are constrained by
policy; responses are bounded at 4 MiB. One lookup-wide monotonic deadline includes all requests,
pacing and a maximum of one numeric Retry-After retry. Network/timeout/5xx/repeated 429 use retryable
FEN-6003; unknown response shapes use FEN-3004. The warning supplier.rate-limited survives failures.
JSON decimal tokens are strings, never physical-model floats. Operational timeout clocks may be floats.

Use a conservative single-token request bucket and a run-local ceiling for published daily quotas.
DigiKey/Mouser metadata records documented limits; Nexar/Farnell use the explicitly chosen client rate
of one/minute and unknown daily quota. A run-local client does not claim to enforce account-wide quota
across tools. No global bucket, shared cache, user cache, credentials file or disk answer cache exists.
A future verified policy can permit one lookup object's memory cache with bounded age no greater than
known terms; unknown cache rights cannot enable it. Cache entries are redacted first.

### 4. Explicit query, identity drafts and grammar review

Only canonical query keywords and the user's credentials may be sent, after --allow-offsite. The
proposal command does not execute the script or send a board, netlist, project name or BOM. It may
read authored local grammar rows to provide a review suggestion. Inputs used for suggestions bind the
plan. --limit is 1..50 and --timeout is above zero and at most 300 seconds, default 30.

Where a reviewed policy explicitly permits it, rich proposals write
`devices/proposed/<safe-MPN>-<digest>.toml`, schema `fenolite.supplier-proposal.v0`. This distinct identity
draft contains only permitted manufacturer/MPN/datasheet fields plus UNVERIFIED, `see source terms`
and provenance (source, canonical query, retrieved timestamp, attribution). It does not misrepresent
unlicensed identity content as a usable DeviceDef. Picks skip drafts until human rights/datasheet review
and conversion to a complete authored record. Existing complete legacy rows keep their acceptance.

A unique valid c0263 decode adds `[decoded].device_toml`, a suggestion containing only grammar-owned
symbol, footprint, pins, kind, value and ratings, and `decoded_by`. It does not approve the draft for
picking. Unknown MPNs give supplier.row-incomplete. Supplier-reported attributes never set parameters.
Every displayed identity, text reply and draft provenance carries the policy acknowledgement.

### 5. Transient results and exact confirmation

Prices, stock, lifecycle and reported parameters appear only in the immediate `result.proposals`.
They must not enter persisted/replayed plan results or write bytes. `Result.staged_result` is an optional
filtered subset of result data: it cannot add/change values or replace framework plan/receipt metadata.
The dispatcher retains control of plan inputs, issues, write bytes, digests and receipts. The default
preserves all other command behavior.

Confirmation with --plan uses staged exact bytes without importing a provider or making another request.
Tests inspect every stored plan file and the confirmed row, compare its digest, and forbid a second
lookup. --timestamp fixes retrieved time. Credentials and offers are absent from staged/replayed data.

### 6. Scope and deferred work

No reported-parameter persistence, supplier-login command, disk cache, cart/ordering, scraping, bulk
fetch, shared keys or live supplier calls. Credentials use the keyring's own interactive CLI if desired.
No fabricated API-specific terms, endpoints or response fields. Source-readiness tasks remain open
until primary evidence permits completion. The maintainer owns serialized full validation, exact-head CI and
publication; focused local proofs do not claim those gates passed.

## Proof strategy

Patch socket construction to fail in supplier tests. Author fictional responses and CC0 sidecars from
registered primary field names, never downloaded product answers. Verify credential precedence and
redaction; bounded hosts, retries, size and timeout; cache expiry/scope; policy/page agreement; exact
query-only mapping; identity/grammar drafts; consent and unchanged legacy plugins; filtered plan replay;
and fresh-process isolation of capabilities, explain, build and ordinary pick. Add a focused guide page
because parts and recovery are at their budgets, generate command pages and existing schemas, and run
focused consistency, type, lint, residue and strict OpenSpec checks.


Rich plugin integration explicitly opts in with `proposal_api="fenolite.supplier-lookup.v0"` and
`lookup(...)->SupplierLookup`. A legacy plugin's unrelated `lookup` method does not change its
`Supplier.propose` behavior.
