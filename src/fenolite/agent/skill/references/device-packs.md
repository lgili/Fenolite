---
topic: device-packs
title: Offline device items and seeding
summary: Use device items offline; seed CC0 data.
---

# Offline device items and seeding

Get a device and its exact symbol/footprint dependencies beside the design. Check the licence and plan
before confirming. Builds read TOML under `fenolite_library/`; they never execute library payloads or
fetch device data. Authored `design.devices(...)` / `devices/` wins, then vendored, then shipped.

```fenolite-cmd
fenolite get device FenoliteDevices:Example --from release --dry-run --json
fenolite get --locked design.py --offline --dry-run --json
fenolite build design.py --out out --frozen --dry-run --json
```

`result.devices[].origin` and `result.libraries` label used definitions `library`, `authored` or `builtin`.
`result.library_items` and a library device's `item` give kind, id and version. Two vendored items with
one id give `library.item-conflict`; an authored override gives `library.overrides-item`. Unused items
change no output bytes. Only `get` writes `[library.items]`; a missing pinned folder is `FEN-6004`.
Library picks record `library:device/NS:NAME@VERSION` and re-check a version change.

Seed only into an external `fenolite-library` checkout. The independent reader accepts the documented,
bounded format subset. The full CC0 legal code and a matching `.git` HEAD are required. Every result
stays `UNVERIFIED`, with the source library, commit, UUID, licence and `D-` source retained.

```fenolite-cmd
fenolite library seed --from-librepcb upstream --commit 1111111111111111111111111111111111111111 --library "LibrePCB Base" --into library-data --namespace FenoliteDevices --dry-run --json
```

Read every `library.seed-skipped` warning: unknown versions, unsupported pads and sub-nm lengths skip
the element and its dependants. Names may report `library.seed-renamed`. Confirm with the returned
`--plan`; changed inputs need a fresh plan. A reviewed existing seed is refused with `FEN-7001`, even
with `--allow-lossy`. CC0 is not proof of electrical correctness or the upstream contributor's rights.
The inferred parser has authored tests only; a live-library oracle and external review remain needed.

Read next: `library-items`, `library-review`, `parts`.
