# Mouser supplier evidence

Read 2026-11-01, change c0267. Public sources: S-1103, S-1104 and S-1222. API field/endpoint facts are `INFERRED`
from primary documentation; missing permission facts remain `UNVERIFIED`. No live API, account,
response, key or product data was used.

The public overview states at most 50 results/call, 30 calls/minute and 1000/day (S-1103).
The primary Swagger schema documents `POST https://api.mouser.com/api/v1/search/keyword`, query
`apiKey`, and JSON `SearchByKeywordRequest` with `keyword`, `records`, `startingRecord` (S-1104).
The mapped response keys are `SearchResults.Parts`, `ManufacturerPartNumber`, `Manufacturer`,
`DataSheetUrl`, `ProductAttributes`, `Availability`, `LifecycleStatus`, and `PriceBreaks`. Attribute
and offer structures remain display-only. The documented `Errors` array is checked before any rows;
a nonempty array refuses the lookup rather than treating partial results as successful. Optional attribute,
price and identity containers are validated against their documented types (S-1104). An unknown shape fails without echoing its body or URL.

The first web read of the exact primary API terms URL returned 403. A subsequent plain public fetch
of the same URL returned a complete Search API Terms of Service body, last modified March 11, 2013
(S-1222), rather than only a challenge page. Read 2026-11-01: section 2 requires application approval
and application-specific credentials; section 4 prohibits caching, recording, prefetching or storing
API content and using it to create/update a business-listing database. Section 5 requires conspicuous
source attribution and preserved links/notices. Section 6 requires compliance with account-assigned
call limits; it establishes no additional numeric quota. Sections 5 and 7 require removing retained
content on termination. No exception for durable identity drafts is established. The production policy
remains unavailable, with no cache or persistence; authored fixtures grant no permission.

The reviewed HTTP-200 body was 128331 bytes with SHA-256
`e59c7416f2e979658091c098b838cebccd9844f56eb7ac644a02082466073b7f`.
Only source facts and this receipt metadata are recorded here; the HTML remains outside the repository.

## Reread attempt 2026-11-04

S-1222 and S-1103 could not be read again. A documentation fetch timed out twice; a plain public fetch
returned an 18684-byte "Access Denied" automation page (SHA-256
`35b75badca50d2f5e795e348fd1d5862f186badf5d17c29083c20c9afad6f88f`), and an ordinary browser received
HTTP 403. The bot gate was not bypassed. That error page is not terms evidence. The facts above therefore
rest on the 2026-11-01 primary body bound to its SHA-256; a later revision of the terms would not be
seen here, so their currency after 2026-11-01 is `UNVERIFIED`. The policy below is unchanged and stays
unavailable.

## Runtime policy

The following values are executable metadata, compared with this page by the offline policy proof.
Acknowledgement identifies the source. The reviewed terms require source attribution and impose other
application/approval obligations; this text does not establish compliance or an identity-storage grant.
No permitted positive cache age is established. Reading terms or entering a key does not clear the gate.

```toml
name = "mouser"
ready = false
cache = "none"
max_age_s = 0
terms_max_age_s = "unknown"
terms = ['S-1222']
persist = []
per_minute = 30
per_day = 1000
attribution = "Mouser (source acknowledgement; required wording is unverified)"
evidence = "UNVERIFIED"
```

Only canonical query keywords and the user's account credentials may leave the process after explicit
`--allow-offsite` and verified readiness. No disk or shared cache exists. JLC remains unregistered.
