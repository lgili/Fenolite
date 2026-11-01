# Farnell supplier evidence

Read 2026-11-01, change c0267. Public sources: S-1108, S-1109. API field/endpoint facts are `INFERRED`
from primary documentation; missing permission facts remain `UNVERIFIED`. No live API, account,
response, key or product data was used.

The partner REST description documents `GET https://api.element14.com/catalog/products` with
`term=any:<query>`, `storeInfo.id`, `callInfo.apiKey`, `callInfo.responseDataFormat=json`,
`resultsSettings.offset`, `resultsSettings.numberOfResults` and `resultsSettings.responseGroup=medium`
(S-1108). The adapter's store choice is `uk.farnell.com`. Mapped keys are `keywordSearchReturn.products`,
`translatedManufacturerPartNumber`, `brandName`, `datasheets[].url`, `attributes`, `stock`, `prices`
and `productStatus`. Attributes and offers remain display-only.

Partner terms section 4(A) prohibits recording/storing API content; section 5 requires source attribution
and preserved links (S-1109). This review establishes no exception permitting durable identity proposals.
No regional terms are substituted for those partner terms. Therefore production lookup is unavailable,
cache is disabled, and persistence is empty. The one request/minute rate is a conservative client choice,
not a published quota. Authored mapping tests do not establish permission.

## Runtime policy

The following values are executable metadata, compared with this page by the offline policy proof.
Acknowledgement identifies the source; required attribution wording remains unverified. `terms=[]`
means no adequate primary terms were readable, not absence of obligations. A registered but unreadable
terms page does not establish rights. A key's presence does not clear the readiness gate.

```toml
name = "farnell"
ready = false
cache = "none"
max_age_s = 0
terms_max_age_s = "unknown"
terms = ['S-1109']
persist = []
per_minute = 1
per_day = "unknown"
attribution = "Farnell (source acknowledgement; required wording is unverified)"
evidence = "UNVERIFIED"
```

Only canonical query keywords and the user's account credentials may leave the process after explicit
`--allow-offsite` and verified readiness. No disk or shared cache exists. JLC remains unregistered.
