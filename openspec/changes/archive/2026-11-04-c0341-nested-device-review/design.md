# Bounded discovery

For a directly loaded device with a valid adjacent `item.json` whose kind/id
match the record and whose payload list includes that record, recognize the
enclosing `devices` folder within four parent levels. Use its parent as the
support tree. This covers repository and vendored nested layouts without
unbounded ascent into unrelated directories. Missing/invalid/mismatched
manifests retain the existing local lookup and unresolved-device finding.

Only selected records are review targets. Dependencies remain included in the
sheet digest, stale detection and reviewed plan. Existing legacy shallow
`devices/foo.toml` lookup stays unchanged. Regression controls exercise nested
review, dependency mutation, and invalid/mismatched manifests.
