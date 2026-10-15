## Why

The copper check on an Altium PCB document (c0088) judges clearance with the Clearance rules that the rule table of c0084 maps. On three of the seven public PCB documents every Clearance record is outside that table, so no clearance is in force there: the stage judges shorts only, reports `copper.rules-incomplete` and carries `UNVERIFIED`. The maintainer decided on 2026-10-06 that more forms of the record are to be mapped: layer scopes and uniform matrices.

Measured before proposing (design, "Measured before"): the eight public PCB documents that the corpus holds have 17 Clearance records, 5 mapped and 12 not. The 12 fall into five forms. Two of them are what the decision names (3 records, all in one document) and can be said exactly by a neutral rule on that document's board; three cannot (9 records), and stay unmapped with a reason that names them.

## What Changes

- **A blank or uniform object matrix is one clearance.** `OBJECTCLEARANCES` that holds white space only, or whose every entry holds the length of `GAP`, maps as an empty one does. A matrix with an entry of another length stays unmapped; its reason now says "a matrix of differing clearances" and counts the entries, instead of quoting the whole text.
- **The keys of a clearance matrix between net classes are read.** A record that Altium's Constraint Manager writes for a cell of that matrix holds `ISMATRIX`, or `SOURCERULE`, `CELLROWNAME`, `CELLROWTYPE`, `CELLCOLNAME`, `CELLCOLTYPE` and `INNERLAYERS` or `OUTERLAYERS`. They are allowed with the values the public document holds; the record's scopes and `GAP` say what it governs.
- **Two layer conditions map where they are exact**, with the copper layers of the board, which only a PCB document gives:
  - `ExistsOnLayer('…')` terms joined by `Or`, the same on both scopes, that name every copper layer of the board: a clearance rule with `layers` = those layers.
  - `OnMid` on both scopes, on a board without an internal signal layer: the rule applies to no object. The record is listed with the new reason `no-layer` and is no unread rule for the copper check.
  - A layer condition that names some of the copper layers, and `OnMid` on a board with internal signal layers, stay unmapped (`scope`): the neutral layer condition is the layer a pair is judged on, and Altium's functions test the object, which differs for a via and a through-hole pad.
- **The copper check maps with the board's layers too**, so its count of unread Clearance records and the rules of the import come from one mapping.
- **Read only.** `rulemap.lower` writes none of these forms; a rule with `layers` is still `scope-unsupported` in a build.
- **Measured after: one of three, not three.** Of the three public documents without a clearance in force, ONE, `altium-third-party-pcbdoc-03`, gets one (5 mil on both copper layers) and the level `INFERRED`: its three records are the two forms that a neutral rule says exactly on its two-layer board. The two others (`-02`, `-06`) stay `UNVERIFIED` without a clearance in force: their records are a matrix of differing clearances or carry the option that ignores the pads of one footprint, which one neutral rule cannot say. The maintainer decided on 2026-10-06 that the matrix form goes to change c0130, that the option is not in v0.3, and that the slack of the unit goes to change c0131 (design, "Decisions of the maintainer").

Size: 1.25 design-days (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-project-reader`: ADDED "More forms of a Clearance record"; MODIFIED "Rules onto the neutral model" (the `layers` argument, the Clearance row, the reason `no-layer`).
- `altium-import`: MODIFIED "Rules where they map" (the import passes the board's copper layers).
- `altium-verification`: MODIFIED "Copper check on Altium boards" and "Clearance rules of a PCB document" (which records count as unread).

## Non-goals

- No change of the neutral rule model and none of `checks/copper.py` or `checks/clearance.py`: `copper.clearance` on a KiCad board is judged exactly as in 0.2.0, and no KiCad output changes.
- No committed Altium sample changes: the writer writes what it wrote.
- No matrix of differing clearances, no `IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE`, no scope function beyond the two layer conditions (`HasFootprint`, `InPolygon`, `InAnyDifferentialPair`, `InDifferentialPairClass`), and no operator spelled `AND` or `or`. The design lists each under "Out of scope" with what it would need.
- No conservative judging (the smallest or the largest entry of a matrix): decided against on 2026-10-06; change c0130 lifts the cells that are exact.
- No layer condition for Width or any other unary kind, and none for a rule file, which has no board.
- No code or constant from any private project or organisation; test records are authored for Fenolite, and corpus files are read from the cache through Fenolite's own readers.
- No format fact from a decompiled tool or a transcribed parser: every fact has a row in `docs/formats/altium/rule-file.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

`INFERRED` under the new row `H-A-RULE-CLEARANCE-FORMS`: the keys and scope texts are measured on public documents (`CORPUS-VERIFIED` rows), their meaning comes from Altium's public documentation (S-0555 to S-0558, read for facts), and only Altium's own rule check can confirm that a mapped record governs the pairs the neutral rule governs (a kit request; no step is run here).

## Impact

- Changed: `backends/altium/read/scope.py`, `read/rules.py`, `rulemap.py`, `adapter/layers.py`, `adapter/rules.py`, `adapter/board.py`, `backend.py`.
- Pages: `docs/formats/altium/rule-file.md` and `import.md`, `docs/altium.md`, `docs/evidence/altium-roundtrip.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`.
- Behaviour: the import of a PCB document with such records holds more clearance rules (one of them with `layers`); `fenolite check` on such a document judges clearance where it judged shorts only, and can exit 5 where it exited 0; the text of `altium.rule.unmapped` for a matrix is shorter; a rewrite (RT-A3) of such a document names the rule with `layers` as not written.
- Depends on: c0084 (the rule table) and c0088 (the rules source of the copper check), both implemented on the integration branch and not archived; c0042 and c0043 (archived). Archive after c0084 and c0088.
