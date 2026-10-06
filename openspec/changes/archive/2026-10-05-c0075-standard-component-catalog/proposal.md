# Proposal: Fenolite standard component catalog

## Why

Fenolite can currently resolve libraries authored by the user or installed/fetched from a CAD backend, but it ships no independent library of schematic symbols and footprint drawings. That makes common, non-custom components depend on another application's library installation and leaves a large gap in Fenolite-only workflows.

## What Changes

- Ship an offline, Fenolite-authored catalog of drawn generic symbols and reusable standard-package footprints under a reserved `Fenolite:` namespace.
- Make catalog entries discoverable through a stable Python API and a read-only CLI query.
- Let `build` resolve catalog entries without KiCad library files or network access. Project-authored definitions with the same IDs take precedence, so users can refine or replace any standard entry.
- Record public evidence and an evidence level for every package geometry and pin fact. Generic inferred lands remain clearly identified as drafts.
- Establish a repeatable contribution model for expanding coverage by common component family and package, without promising every commercial MPN.

## Non-goals

- Copying or bundling KiCad, Altium, or other third-party library files or drawings.
- Claiming every commercially available component is already covered.
- Choosing a footprint for a part when the user has not selected its package, or asserting electrical/manufacturing qualification.
- Adding supplier search, network fetching, or a graphical part picker.

## Evidence level required

Fenolite-authored unit and build tests must prove stable catalog contents, offline resolution, custom override, and writer/readback of shipped symbol graphics and footprint definitions. Public manufacturer/package references must be cited in the catalog manifest for each physical dimension or pin fact. Any land pattern that is not explicitly recommended by a public source must be labelled `INFERRED` in its metadata and user-facing description.
