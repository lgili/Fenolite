---
topic: supplier-lookup
title: Supplier proposals and credentials
summary: Per-user supplier credentials, source readiness and review-only identity proposals.
---

# Supplier proposals and credentials

Start with offline discovery. The named built-ins are currently unavailable pending a documented
source-rights review; entering a key does not enable them. JLC is unregistered.

```fenolite-cmd
fenolite capabilities --no-tools --fields suppliers --json
fenolite pick examples/families --propose "capacitor(100nF, rating=25V, case=0603)" --supplier mouser --allow-offsite --limit 5 --timeout 30 --timestamp 2026-11-01T00:00:00Z --dry-run --json
```

That second line is the explicit lookup form for an enabled source. Current built-ins return
`FEN-6001` before reading credentials or creating transport. `result.suppliers` lists readiness,
reason, cache, sent categories, environment-variable presence and optional keyring installation.
Discovery reads names only, never credential values, and opens no connection.

Install `fenolite[suppliers]` only for optional keyring support. Credentials come from your own
`FENOLITE_<SOURCE>_<NAME>` environment variables, then service `fenolite.suppliers.<source>` in the
system keyring. DigiKey/Nexar use `CLIENT_ID` and `CLIENT_SECRET`; Mouser/Farnell use `API_KEY`.
Never put credentials in a project or pass them as command arguments.

`--allow-offsite` permits canonical query keywords and your account credentials. The lookup never
executes the script or sends a board, netlist, project name or BOM. `--limit` is 1..50; `--timeout`
bounds the complete lookup including pacing and one numeric `Retry-After` wait. No shared or disk
supplier cache exists. A reviewed future policy may permit memory within one lookup object.

Review `result.proposals`, attribution and the plan. Offers, stock, lifecycle and reported attributes
are display-only: they are absent from stored plans and written drafts. Where the source policy permits
identity persistence, confirm by repeating the command with `--confirm --plan ID`; it writes the exact
reviewed bytes without another request. The receipt's SHA-256 identifies those bytes.

The draft schema `fenolite.supplier-proposal.v0` is `UNVERIFIED` and requires human review of source
rights and the datasheet before conversion into a complete device record. Picks skip it. A unique valid
local grammar may give a review suggestion and `decoded_by`; supplier attributes supply no device
parameters. Without a grammar, fill symbol, footprint, pins, kind, value and ratings in a reviewed device.
Legacy complete supplier rows retain their existing acceptance rules.

```fenolite-cmd
fenolite explain FEN-6005 --json
fenolite explain supplier.proposed --json
fenolite explain supplier.row-incomplete --json
fenolite explain supplier.no-results --json
fenolite explain supplier.rate-limited --json
fenolite explain supplier.unmapped --json
```

| Code | Exit | Meaning |
|---|---|---|
| `FEN-6005` | 6 | Supplier credentials refused; check your own account and named credential source. |

`FEN-6005` means refused credentials, exit 6 and not retryable. Check the named variables/keyring
service and your own account access, without pasting their values into a report. `FEN-6003` covers
retryable network, timeout, source failure or repeated 429; `FEN-3004` covers an undocumented response.
All four adapters have authored offline fixtures. DigiKey/Nexar tokens stay within one lookup and
join credential redaction; Nexar omits paid add-on fields. API/GraphQL errors refuse partial answers.
These mechanics do not prove live access, plan entitlement or source-data rights. Local mechanics are `INFERRED`; proposed identities remain `UNVERIFIED`. See `docs/suppliers.md`.

Read next: `parts`, `recovery`, `library-items`.
