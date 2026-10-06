## Why

An Altium build writes three kinds of rule (Clearance, Width, Routing Via Style), each as one rule for all nets plus one per net class. Every other rule of a script gives `altium.not-lowered` at `design-rules`: the board-edge clearance, the hole sizes, the six kinds that c0071 added for KiCad (hole to hole, hole clearance, annular width, courtyard, silkscreen, creepage), and every scoped `rule()`. The board then opens in Altium with Altium's defaults for all of them, and a design rule check there judges another design than the script.

The read side has the same gap: `read/rules.py` maps three kinds and holds `BoardOutlineClearance` as pending, so an imported board loses most of its rules and RT-A2 cannot compare them. The roadmap's v0.4 item "Rule lowering" is this.

## What Changes

- **A closed lowering table**: each neutral rule kind → the Altium rule kind that carries it, the scope it is written with, and the reason when it has no counterpart. `altium.not-lowered` names the kind and the reason, never the whole group.
- **Rule records in the PCB document** for the kinds of the table, with scopes: all nets, a net class, a net, a layer, and pairs of those.
- **Reading the same kinds** back onto the neutral rules (`read/rules.py`), so that what Fenolite writes it also reads, and an Altium board keeps these rules through an import.
- **A rule file**: `fenolite export --kinds altium-rul` writes the rules as an Altium rule file, which the PCB Rules editor imports; it is the same text form that c0042 reads.
- **An oracle without Altium**: the rules of a built PcbDoc are read back and compared with the design's (own readback), and with what KiCad's importer makes of them where it imports a kind.

Size: 7 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-pcb-writer`: ADDED "Rule lowering table", "Scoped rule records"; these supersede the three-kind limit of "Design rule records".
- `altium-build`: ADDED "Rules in an Altium build"; supersedes "Rule minimums in an Altium build".
- `altium-project-reader`: ADDED "More rule kinds onto the neutral model", "Rule file written".
- `manufacturing-exports`: ADDED "Altium rule file export".

## Non-goals

- No rule kind that the neutral model lacks (high-speed, signal-integrity, placement rooms, manufacturing testpoints): they stay opaque on read and are counted.
- No query language beyond the closed scope grammar of c0042 (`All`, `InNet`, `InNetClass`, `OnLayer`, and `and` of those).
- No Altium DRC run by Fenolite: Altium is not an oracle that runs in CI. c0088 adds Fenolite's own check; the maintainer's report confirms that Altium uses the written rules.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- What Fenolite reads back from its own file: `INFERRED` under `H-A-RULE-READBACK` (own readback proves consistency, not Altium's reading).
- That Altium lists each written rule with its value and scope, and that its design rule check applies them: `INFERRED` until the maintainer reports Part U; then `ALTIUM-VERIFIED(author-report; AD <version>; <date>; no artefact)`. The kit of c0091 repeats the same steps.
- The write stays `experimental` in `claims.py` (c0092 decides graduation).

## Impact

- Changed: `backends/altium/pcbrecords.py`, `pcbdoc.py`, `read/rules.py`, `read/rul.py`, `lens/altium_copper.py`, `lens/altium.py`, `exports/`; new `backends/altium/rulemap.py` (the table, shared by writer and reader).
- Pages: `docs/altium.md` ("Rules"), `docs/formats/altium/{rule-file,pcb-copper}.md`, `docs/evidence/altium-pcb.md`.
- `altium.not-lowered` at `design-rules` is replaced by one issue per kind that is not lowered.
- Depends on: c0038 (rule records), c0042 (rule files read), c0071 (rule kinds); nothing else of v0.4.
