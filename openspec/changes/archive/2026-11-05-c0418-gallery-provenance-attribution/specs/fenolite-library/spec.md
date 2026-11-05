## MODIFIED Requirements

### Requirement: Gallery with attribution
`fenolite library gallery` SHALL write a static site of images rendered by Fenolite only. Every card MUST show the title, the authors, the upstream link, the SPDX id, the Fenolite version, "Not endorsed by the authors" (for converted and seeded items), the proof result and the `fenolite get` command. The attribution and licence of every item SHALL come from its `PROVENANCE.json`, cross-checked with the release index: only an item whose provenance says `origin = "authored"` MAY say "Authored for fenolite-library"; a `seeded` item MUST name its upstream authors, link the upstream at its commit, name its licence and say that it was converted. A provenance that is missing, of an unknown origin, or that contradicts the index or itself MUST fail the command with `library.provenance-invalid` errors naming the item and write nothing; it MUST NOT fall back to "Authored" or to CC0. An item with `trademarks.restricted` MUST NOT appear.

#### Scenario: Card attribution
- **GIVEN** the release fixture with one converted board licensed `CERN-OHL-S-2.0`
- **WHEN** the gallery is planned with `--dry-run --json`
- **THEN** the planned card page of that board holds the attribution line with its authors, upstream link and `CERN-OHL-S-2.0`

#### Scenario: Restricted marks hidden
- **GIVEN** a fixture board with `trademarks.restricted = true`
- **WHEN** the gallery is planned
- **THEN** no card or image of that board is planned

#### Scenario: Authored and third-party attribution
- **GIVEN** the release fixture with the authored device `Demo:EXB` and the seeded `CC-BY-SA-4.0` footprint `Demo:SA_PAD`
- **WHEN** the gallery is written
- **THEN** the device page says "Authored for fenolite-library", and the footprint page and card say "Derived from Demo Pad Authors (https://example.org/demo-pads) at commit 000000000000, licence CC-BY-SA-4.0", link the upstream as its source and never say "Authored for fenolite-library"

#### Scenario: Contradictory provenance fails the gallery
- **GIVEN** the release fixture where the seeded footprint's `PROVENANCE.json` says `CC0-1.0` while its index row says `CC-BY-SA-4.0`, or has no upstream, or has no origin
- **WHEN** the gallery is planned
- **THEN** it exits 5 with a `library.provenance-invalid` error naming `Demo:SA_PAD` and the field, and plans no write
