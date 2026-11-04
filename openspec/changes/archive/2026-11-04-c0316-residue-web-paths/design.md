## Context

On 2026-11-01 the public-only history scan reported one finding in
`7f1834b83695:docs/research/enclosures.md`, byte offset 35427. Inspection showed a
public HTTPS reference whose path resembles a user directory. Its original bytes
remain unchanged; the paused enclosure work is outside this change.

## Decisions

Decided 2026-11-01: suppress only an `abs-user-path` match wholly inside the path
component of a parsed HTTP(S) URL with an authority. Use standard-library URL
parsing. Invalid URLs receive no exemption. Do not weaken the path regex or waive
an entire file. File URIs and query/fragment values retain the existing scan.

Decided 2026-11-01: private token/hash checks and all other structural patterns
continue to inspect the complete bytes, including URLs and archives. Report the
public history result separately from the unconfigured private gate. No history
rewrite, remote deletion or claim of a private release scan is authorized here.

## Evidence

This is an authored scanner correction, not a new CAD format claim. Tests construct
invented URLs and filesystem paths at runtime. The inspected historical reference
is existing public repository content, not a new fixture or imported source.
