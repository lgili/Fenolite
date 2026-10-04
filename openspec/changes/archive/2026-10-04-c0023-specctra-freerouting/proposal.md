## Why

The second router of plan D11 is Freerouting (S-0220): GPL-3.0, mature, and independent of KiCad's file format. It reads a Specctra DSN file and writes a session (SES) file. `kicad-cli` exports no DSN and imports no SES on 9.0 or 10.0 (S-0022, S-0037), so Fenolite must write DSN and read SES itself, from the neutral model. The plan time-boxes this at two weeks.

This change is **cuttable**. If c0016's feasibility gate passes, KiCadRoutingTools covers v0.1's acceptance item 3 and the roadmap's accepted cut order moves this change to v0.2a first. It is proposed now so the decision can be taken with its cost and risks written down.

Two risks are specific to it. The only full description of the format is a vendor reference manual whose notice forbids copying (S-0224); Fenolite may record facts from it in its own words, and the maintainer decides whether that is acceptable (ADR-0006). And Freerouting sends usage data by default (S-0222), so the plugin must turn that off and say so.

## What Changes

- `backends/specctra/` (new codec package, not a registered backend): a lexer for the Specctra syntax, `dsn.write_dsn` from the model and board-frame pads, `ses.read_session`, and `ses.to_copper` back to model tracks and vias.
- `routing/plugins/specctra/freerouting.py`: runs `java -jar <jar> -de … -do … -mp N -mt 1 -da --gui.enabled=false` on a temporary folder, or the same in a container, and returns the session's copper.
- `fenolite route --router freerouting`: no command change; the router registers through c0016's entry-point group.
- `doctor`: the Freerouting jar, its version and the Java major it needs.
- Probes first, with Freerouting 2.4.1: the written DSN is accepted, coordinates come back within the resolution, protected wiring is kept, the routed blink passes `kicad-cli` on both majors, two runs compared, and a run with the network disabled.
- ADR-0006 (`Proposed`): facts from the restricted reference; a GPL router only across a process boundary; no cloud mode.
- Sources S-0220 to S-0226; hypotheses `H-G-DSN-ACCEPT`, `H-G-DSN-UNITS`, `H-G-DSN-PROTECT`, `H-G-DSN-ROUTE`, `H-G-DSN-REPEAT`, `H-G-DSN-OFFLINE`.

Budget: 10 days, time-boxed; the cut order is in the design.

## Capabilities

### New Capabilities
- `specctra-dsn`: syntax, the DSN writer, the session reader, the mapping to copper, facts and the decision record.

### Modified Capabilities
- `routing` (c0016): ADDED "Freerouting plugin".
- `kicad-oracle`: ADDED "Freerouting routes pass the oracle".
- `cli-contract`: ADDED "Freerouting in doctor".
- `ci-baseline`: ADDED "Freerouting in the routing job".

## Non-goals

- A DSN reader or an SES writer; DSN as an import format; any Specctra construct the writer does not emit.
- Freerouting's cloud API, its GUI and its own DRC output; `--router freerouting-cloud`.
- Planes for zones, differential pairs, component placement by the router, blind and buried vias.
- Vendoring, downloading or importing Freerouting; reading its source for format knowledge.

## Evidence level required

- Syntax and the session mapping: mechanical on authored files.
- DSN accepted and routed by Freerouting 2.4.1: `ORACLE-VERIFIED(freerouting 2.4.1)` (`H-G-DSN-ACCEPT`, `H-G-DSN-UNITS`, `H-G-DSN-PROTECT`).
- Routed boards under `kicad-cli`: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-G-DSN-ROUTE`).
- Repeatability and the offline run: recorded (`H-G-DSN-REPEAT`, `H-G-DSN-OFFLINE`); a plugin that cannot be shown to run offline is listed with `sends_data_offsite: true`.
- Format facts: `INFERRED` from S-0224 until a probe confirms them; no fact is labelled above the probe that proves it.
- Every `route` result: `UNVERIFIED`.

## Impact

- New `backends/specctra/`, `routing/plugins/specctra/`, `docs/formats/specctra/`, `docs/adr/0006-specctra-and-freerouting.md`; extended `pyproject.toml` (one entry point), `cmd_doctor.py`, `ci.yml`.
- No model or schema change; no runtime dependency.
- Depends on c0016 (protocol, command, layering delta), c0022 (`board_outline`) and c0028 (`BoardFrame`), archived first. The maintainer accepts ADR-0006 before archive.
