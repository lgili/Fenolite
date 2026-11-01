# Nexar supplier evidence

Read 2026-11-01, change c0267. Public sources: S-1105, S-1106, S-1107. API field/endpoint facts are `INFERRED`
from primary documentation; missing permission facts remain `UNVERIFIED`. No live API, account,
response, key or product data was used.

The official authorization article recommends the supply client-credentials flow and names
`https://identity.nexar.com/connect/token` and `https://api.nexar.com/graphql` (S-1105). The sorting
article demonstrates `supSearch`, `results`, `part`, `mpn` and `specs` (S-1106). The complete current
authentication/response mapping and an account's quota are not established here, so no runtime mapper
or synthetic API response is invented.

The public Octopart terms page was readable but its API-terms accordion body was unavailable (S-1107).
Token expiry does not establish a content-cache licence. No 24-hour cache, prescribed attribution or
durable identity-proposal permission is claimed. The conservative limit of one request/minute is a
client choice, not a published provider quota. Registration is discoverable; lookup fails before
reading credentials or creating transport.

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
