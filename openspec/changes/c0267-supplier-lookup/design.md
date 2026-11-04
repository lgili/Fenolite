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

The primary review is recorded under `docs/formats/suppliers/`, S-1100..S-1110 and S-1220..S-1227.
DigiKey's now-readable API agreement restricts creating/updating an information database. Mouser's
primary API terms were later read through a plain public fetch and prohibit storing API content;
Nexar's API accordion body remains unavailable. Readable Farnell terms
prohibit recording/storing API content and establish no durable identity exception. No session/24-hour content-cache licence is inferred from old research, snippets, token
expiry or regional terms. Prescribed attribution wording remains unverified.

All four production policies therefore have `ready=false`, `persist=[]`, `cache=none`, age zero and
`UNVERIFIED` evidence. Lookup fails before credentials or transport, with FEN-6001 and a source-review
hint. A key's presence and broad task authorization do not clear a source-rights gate. All four sources
have documented request/mapping code proved under explicitly fictional test permissions; this does
not enable production. DigiKey/Nexar tokens remain per-lookup; Nexar requests basic fields without
assuming paid add-on access. A response mapping is not a source-data licence.
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

## Public adapter continuation — Decided 2026-11-01

The clean continuation starts at 17706a46; supplier paths match the current combined candidate.
Primary protocol facts are available for all four adapters. Complete their authored-only request and
mapping proofs independently of production permission. A checked 2.x implementation task records its
specific offline proof, not a ready policy, live access or granted identity rights. Task 0.2 stays open
while a required primary terms body/permission fact is missing; JLC 5.1 and exact-CI 6.4 stay open.

DigiKey's linked Swagger and readable API User Agreement are registered as S-1220/S-1221 after a
collision search. Its database restriction does not establish durable identity permission. Mouser's
exact primary terms URL still returns403. Nexar's API accordion body remains unavailable, and its
current add-on field table distinguishes paid specs/lifecycle/datasheets/ECAD; request only documented
basic identity and seller offers. Farnell's primary storage restriction is unchanged. All production
policies remain ready=false, persist=[] and cache=none. No key or paid entitlement is assumed.

Use the existing bounded stdlib client for token and search calls under one deadline; tokens join the
credential redaction set immediately and remain per-lookup. Authored fixtures use fictional tokens,
identities, prices and example.invalid links, with CC0 sidecars. Unknown token/container/error shapes
refuse without echoing remote messages; GraphQL partial data never overrides errors. A mapping failure
retains prior rate-limit warnings, including when a successful HTTP reply carries GraphQL errors. These implementation
choices do not copy any public SDK, parser or documentation schema into core and add no public fields.

## Cached public terms follow-up — Decided 2026-11-01

The initial Mouser web 403 gap is partly resolved by an approved plain public HTTP 200 fetch of the
same S-1222 URL. The body is actual Search API Terms of Service, last modified 2013-03-11, with all
sections 1–20 present; its SHA-256 matches the fetch receipt. Sections 2/4/5/6/7 require application
approval, prohibit content storage, require source/link attribution, refer to account-assigned call
limits and require removing content on termination. No new numeric quota or durable identity exception
is inferred. Register S-1222 as reviewed terms and correct only the existing policy metadata/reason;
ready=false, persist=[], cache=none and the absence of an affirmative positive cache age remain.

The Nexar raw fetch returned 403; its body is error evidence, not API terms. Task 0.2 remains open for
the missing primary Nexar terms body and unresolved permitted identity scope. JLC and full/CI tasks
remain open. No network permission, auth, API key, bypass, readiness or evidence-level promotion is used.

## Found on 2026-11-04

**JLC is cut from this change (maintainer decision, 2026-11-04).** A JLC plugin needs the maintainer's
own approved API access, documentation and terms; no session can supply them. c0267 now covers only the
four public suppliers. Task 5.1 leaves this change unimplemented, no JLC plugin, entry point, policy or
fixture is registered, and the "JLC remains unregistered" statements of the supplier pages stay true.
The work moves to a separate follow-up change, proposed below; its id is assigned by the coordinator.

Follow-up proposal (JLC supplier lookup): after the maintainer records the approved JLC API
documentation and terms in `docs/formats/suppliers/jlc.md` (endpoints, parameters, response keys,
limits, cache rule, attribution, each with a source and label), add `jlc.py` on the existing c0267
machinery with its policy, authored fake responses and entry point, gated exactly like the four public
suppliers (`ready=false` until rights are established). Proof: `tests/unit/suppliers/test_jlc.py` and
`tests/unit/suppliers/test_policy.py`.

The four public terms pages were reread for task 0.2. DigiKey (S-1221, S-1102) and Farnell (S-1109,
S-1108) were readable and unchanged in substance. Octopart/Nexar (S-1107) now serves its APIs section
body, which closes the 2026-11-01 missing-body gap without granting cache or identity-storage rights.
Mouser (S-1222, S-1103) blocked every automated and browser read with an automation-denial page or
403; the gate was not bypassed and its facts rest on the SHA-bound 2026-11-01 body. No policy value,
readiness, cache, persistence or evidence level changes: missing rights are a policy outcome
(`ready=false`, `persist=[]`, `cache="none"`), not a gap in the source register.
