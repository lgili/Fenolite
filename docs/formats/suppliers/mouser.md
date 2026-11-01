# Mouser supplier evidence

Read 2026-11-01, change c0267. Public sources: S-1103, S-1104. API field/endpoint facts are `INFERRED`
from primary documentation; missing permission facts remain `UNVERIFIED`. No live API, account,
response, key or product data was used.

The public overview states at most 50 results/call, 30 calls/minute and 1000/day (S-1103).
The primary Swagger schema documents `POST https://api.mouser.com/api/v1/search/keyword`, query
`apiKey`, and JSON `SearchByKeywordRequest` with `keyword`, `records`, `startingRecord` (S-1104).
The mapped response keys are `SearchResults.Parts`, `ManufacturerPartNumber`, `Manufacturer`,
`DataSheetUrl`, `ProductAttributes`, `Availability`, `LifecycleStatus`, and `PriceBreaks`. Attribute
and offer structures remain display-only. An unknown shape fails without echoing its body or URL.

The primary terms URL returned 403. Search snippets do not establish permission. Required attribution,
cache and durable identity-proposal rights remain unknown. The authored adapter is proved under an
explicit fictional test policy; the production policy cannot issue a request.

## Runtime policy

The following values are executable metadata, compared with this page by the offline policy proof.
Acknowledgement identifies the source; required attribution wording remains unverified. `terms=[]`
means no adequate primary terms were readable, not absence of obligations. A registered but unreadable
terms page does not establish rights. A key's presence does not clear the readiness gate.

```toml
name = "mouser"
ready = false
cache = "none"
max_age_s = 0
terms_max_age_s = "unknown"
terms = []
persist = []
per_minute = 30
per_day = 1000
attribution = "Mouser (source acknowledgement; required wording is unverified)"
evidence = "UNVERIFIED"
```

Only canonical query keywords and the user's account credentials may leave the process after explicit
`--allow-offsite` and verified readiness. No disk or shared cache exists. JLC remains unregistered.
