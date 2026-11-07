# Why
The immutable public resistor symbol has2mm graphical pin lengths, which correctly
fail the10mil grid check. The maintainer requests an explicitly different curated
CC0 draft for human review, retaining the raw failed seed and provenance.

# What Changes
Prepare an external deterministic four-item draft: two original footprints,
resistor symbol and device. Change only the two graphical pin lengths from
2,000,000nm to2,032,000nm; preserve anchors, visible pin names/numbers, device
functions/mappings, footprints and physical dimensions. Record the modification
in existing provenance notice and NOTICE, regenerate content hashes, and produce
before/after native partition and full check/preview evidence. No waiver, parser
rounding, review acceptance or publication.

# Impact
External review artifacts only; no third-party payload or runtime/model change
in core. c0266 review/release gates remain open until actual review and CI.
