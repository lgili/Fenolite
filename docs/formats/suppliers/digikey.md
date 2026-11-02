# DigiKey supplier evidence

Read 2026-11-01, change c0267. Primary sources: S-1100..S-1102, S-1220 and S-1221. Protocol facts are
`INFERRED`; fixture proofs establish local mapping only. No live API, account, key or product data was used.

S-1100 documents a form-encoded POST to `https://api.digikey.com/v1/oauth2/token` with `client_id`,
`client_secret` and `grant_type=client_credentials`. Its response has `access_token`, `token_type` and
`expires_in`; a Bearer token and `X-DIGIKEY-Client-Id` accompany product requests. Tokens remain local to
one lookup and are redacted like credentials. Expiry is not a content-cache permission.

The Swagger linked from S-1101 (S-1220) documents POST `https://api.digikey.com/products/v4/search/keyword`.
The authored request uses only `Keywords` (at most 250 characters), `Limit` (1..50) and `Offset=0`.
The response mapper reads `Products`, `ManufacturerProductNumber`, `Manufacturer.Name`, `DatasheetUrl`,
`Parameters`, `UnitPrice`, `QuantityAvailable`, `ProductStatus` and `ProductVariations`. Reported parameters
and offers are display-only; optional absence is distinct from malformed containers. The primary shared
concepts quota remains120 requests/minute and1000/day (S-1102), subject to the user's actual subscription.

The primary API User Agreement is now readable (S-1221). Sections 1–3 limit purposes, account/application
approval, use and attribution. Section 3.1.4 requires conspicuous DigiKey source attribution; section 5.1(e)
restricts using API content to create/update an information database. Sections 3.2 and 9 also constrain
redistribution, links and retained content after termination. This review establishes no exception for
Fenolite's durable identity drafts. `ready=false`, no cache and empty persistence remain in force.
The acknowledgement below does not establish compliance with every applicable approval/mark obligation.
Authored protocol tests do not grant production permission.

## Runtime policy

The following values are executable metadata, compared with this page by the offline policy proof.
Acknowledgement identifies the source. The readable agreement requires source attribution and imposes
other display/approval obligations; this text does not establish compliance or a durable identity grant.
Registering the agreement and entering a key do not clear the readiness gate.

```toml
name = "digikey"
ready = false
cache = "none"
max_age_s = 0
terms_max_age_s = "unknown"
terms = ['S-1221']
persist = []
per_minute = 120
per_day = 1000
attribution = "DigiKey (source acknowledgement; required wording is unverified)"
evidence = "UNVERIFIED"
```

Only canonical query keywords and the user's account credentials may leave the process after explicit
`--allow-offsite` and verified readiness. No disk or shared cache exists. JLC remains unregistered.
