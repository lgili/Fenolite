# DigiKey supplier evidence

Read 2026-11-01, change c0267. Public sources: S-1100, S-1101, S-1102. API field/endpoint facts are `INFERRED`
from primary documentation; missing permission facts remain `UNVERIFIED`. No live API, account,
response, key or product data was used.

The current OAuth2 tutorial documents `POST https://api.digikey.com/v1/oauth2/token` using
`grant_type=client_credentials` (S-1100). The v4 keyword page names
`POST https://api.digikey.com/products/v4/search/keyword` (S-1101). Its response-body schema was not
accessible in this review, so no mapper or synthetic API response is invented. Shared concepts lists
120 requests/minute and 1000/day for standard Product Information access and describes numeric
`Retry-After` (S-1102). The older shared-concepts OAuth wording conflicts with the current two-legged
tutorial; this records the current tutorial without inferring a subscription's scope.

Current primary API terms and durable identity-proposal permission were not accessible. No session
cache permission or prescribed attribution wording is claimed. Registration is available for discovery;
lookup fails before reading credentials or creating transport.

## Runtime policy

The following values are executable metadata, compared with this page by the offline policy proof.
Acknowledgement identifies the source; required attribution wording remains unverified. `terms=[]`
means no adequate primary terms were readable, not absence of obligations. A registered but unreadable
terms page does not establish rights. A key's presence does not clear the readiness gate.

```toml
name = "digikey"
ready = false
cache = "none"
max_age_s = 0
terms_max_age_s = "unknown"
terms = []
persist = []
per_minute = 120
per_day = 1000
attribution = "DigiKey (source acknowledgement; required wording is unverified)"
evidence = "UNVERIFIED"
```

Only canonical query keywords and the user's account credentials may leave the process after explicit
`--allow-offsite` and verified readiness. No disk or shared cache exists. JLC remains unregistered.
