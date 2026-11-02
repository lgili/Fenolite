# Nexar supplier evidence

Read 2026-11-01, change c0267. Primary sources: S-1105..S-1107 and S-1223..S-1227. Protocol facts are
`INFERRED`; missing rights remain `UNVERIFIED`. No live API, account, key, subscription or product data was used.

The supply client-credentials form posts `client_id`, `client_secret`, `grant_type=client_credentials`
and `scope=supply.domain` to `https://identity.nexar.com/connect/token` (S-1105). The token accompanies
JSON POST requests to `https://api.nexar.com/graphql` in `Authorization: Bearer ...` (S-1224). Tokens are
redacted like credentials and retained only within the current lookup; their lifetime grants no content
cache rights. Documented `AuthInvalidToken`/`AuthExpiredToken` GraphQL errors refuse the lookup, without
returning partial data, echoing response messages or automatically making extra requests (S-1225).

S-1223 documents `supSearch(q, limit)`, `results.part`, `mpn`, `manufacturer.name`, `sellers.company.name`
and `sellers.offers` (`inventoryLevel`, `prices.quantity`, `prices.price`, `prices.currency`). The authored
query selects those basic fields, starts at the first result and never pages. The common client cap of 50
is below the documented search maximum of 100; documented start/sum bounds are 1000/1100 (S-1227).

The older specs example (S-1106) does not establish entitlement. Current plan-add-on documentation
(S-1226) identifies specs/lifecycle, datasheets and ECAD as additional fields. This adapter does not
request them or invent a datasheet; its identity draft remains incomplete pending review. Seller offers
stay display-only. Missing/malformed selected response structure and any GraphQL errors fail closed.

The public Octopart terms page was reread, but its API-terms accordion body remains unavailable
(S-1107). No content-cache, prescribed attribution or durable identity-draft permission is established.
The subsequent plain public fetch returned 403; its error body is retained outside core as refusal
evidence, not read as API terms. It does not resolve the missing terms body.
The one request/minute policy remains a conservative client choice, not a provider quota or an account
entitlement. All production requests remain gated before credentials or transport.

## Runtime policy

The following values are executable metadata, compared with this page by the offline policy proof.
Acknowledgement identifies the source; required attribution wording remains unverified. `terms=[]`
means no adequate primary terms were readable, not absence of obligations. A registered but unreadable
terms page does not establish rights. A key's presence does not clear the readiness gate.

```toml
name = "nexar"
ready = false
cache = "none"
max_age_s = 0
terms_max_age_s = "unknown"
terms = ['S-1107']
persist = []
per_minute = 1
per_day = "unknown"
attribution = "Nexar (source acknowledgement; required wording is unverified)"
evidence = "UNVERIFIED"
```

Only canonical query keywords and the user's account credentials may leave the process after explicit
`--allow-offsite` and verified readiness. No disk or shared cache exists. JLC remains unregistered.
