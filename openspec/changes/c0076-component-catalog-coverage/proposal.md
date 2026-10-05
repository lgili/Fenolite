# Proposal: Expand Fenolite's standard component catalog

## Why

The offline catalog introduced in c0075 establishes its API, evidence rules and build path, but its
first pack covers only passive symbols and generic chip lands. A useful Fenolite-first design flow
also needs reusable definitions for the other common component families and standard packages used
in real circuit designs.

## What Changes

- Expand the catalog with Fenolite-authored generic symbols for passive, semiconductor, protection,
  power-conversion, control and electromechanical component families.
- Add reusable footprints for standard package families needed by those catalog entries, including
  common chip, leaded, small-outline, transistor, diode, IC and connector package styles.
- Keep exact commercial part numbers, part-specific pinouts, and non-standard mechanical geometry
  outside generic entries unless a separately sourced, explicitly named definition is appropriate.
- Record public provenance and evidence per definition; keep inferred land patterns labelled as
  inferred.
- Define a repeatable contribution and coverage rule so future families can be added without
  claiming that the catalog is exhaustive.
- Expand c0076's acceptance target to 100 distinct, reusable footprint variants. Select them
  from measured occurrences in a fixed public-board corpus, then cover useful variants of the
  common package families identified there. Publish the exact inventory and provenance before
  implementing further geometry.

## Non-goals

- Importing, copying or bundling any third-party CAD library or private project file.
- Reproducing a particular board's BOM, designators, values, MPNs, or proprietary footprints.
- Selecting or qualifying a footprint for a particular purchased component.
- Network fetching, supplier search, or a graphical component picker.
- Modeling every manufacturer-specific symbol variant or package option.
- Claiming that a public-board sample establishes the 100 globally most-used commercial packages.

## Evidence level required

Catalog entries must be Fenolite-authored. Public datasheets, package standards, and public component
documentation must support factual pin and mechanical claims and be registered in the evidence
source list. A source that gives only package body dimensions does not support Fenolite-authored
copper lands; those lands remain `INFERRED` and are described accordingly. Tests must prove stable
discovery, offline build resolution, writer/readback for supported geometry, provenance checks and
custom project override behavior.
