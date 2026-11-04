# Altium polygon pour evidence (c0215)

What is known of Fenolite's computed pours (`backends/altium/pour.py`) against pours that Altium saved.
The documents are the eight public PCB documents of the corpus manifest (S-0835), read with Fenolite's own
readers from the corpus cache; the engine and the comparison (`backends/altium/pourcompare.py`, M1 to M4 of the design of
change c0215) run on them as `tests/corpus/test_altium_pour_census.py` runs them. A saved pour may be stale,
poured by another version or with AdvancedPour, so a disagreement here is a finding, not a verdict on
either side; nothing here raises a row above `CORPUS-VERIFIED`, and only the kit's group K6 says what
Altium does (`docs/altium-kit.md`).

## Census

Census of 2026-10-26 (`test_pour_census`, `FENOLITE_HEAVY=1` for row `-08`). `d` is the polygon's
`ARCRESOLUTION`, 0.5 mil in every document. "M1" is the XOR area over `d` times the boundary of the saved
pour (it passes at 1 or less).

| row | polygons | refused, by reason | compared | pass | worst M1 | M2 differences |
|---|---|---|---|---|---|---|
| `-01` | 5 | `polygon-cutout` 2, `depends-on-refused` 3 | 0 | 0 | — | — |
| `-02` | 12 | `polygon-cutout` 6, `depends-on-refused` 3, `outline-arc` 2, `outline` 1 | 0 | 0 | — | — |
| `-03` | 1 | none | 1 | 0 | 0.256 | 58, the largest 3.03 mm² |
| `-04` | 9 | `depends-on-refused` 5, `rule-scope` 4 | 0 | 0 | — | — |
| `-05` | 2 | none | 2 | 0 | 0.198 | 65, the largest 0.049 mm² |
| `-06` | 10 | `depends-on-refused` 6, `polygon-cutout` 3, `connect-scope` 1 | 0 | 0 | — | — |
| `-07` | 9 | `outline-arc` 4, `rule-scope` 3, `depends-on-refused` 1, `outline` 1 | 0 | 0 | — | — |
| `-08` | 33 | `depends-on-refused` 13, `rule-scope` 10, `outline-arc` 6, `connect-scope` 2, `polygon-cutout` 2 | 0 | 0 | — | — |

78 of 81 polygons are refused: the engine keeps their outline and says why. Three are compared; each passes
M1 and fails M2, so no polygon supports `H-A-POUR-CORPUS` yet.

## Disagreements

Places are in the frame of the import, in nanometres (the import negates Altium's Y). "Candidate" is Fenolite's pour, "reference" the
saved one; "held by" names the side whose copper the difference is. The nearest object is the one whose
box is nearest the centre of the difference.

| row | polygon | failed | finding |
|---|---|---|---|
| `-03` | `B.Cu` `GND_L02_P000` | M2, M3, M4 | 58 differences: 36 next to a track of another net, 13 to a via of another net, 7 to `GND` pads, 2 to pads of other nets. The largest, 3.03 mm² held by the candidate at (24962320, -67945000), lies inside the box of a `NetJ5_2` track. At the `GND` pads of `J1` at (175768000, -108541248), (175768000, -119781246), (171768000, -119781246) and (171768000, -108541248) the reference holds 0.97, 0.97, 0.89 and 0.89 mm² that the candidate leaves void, where a free `GND` region overlaps each pad; at `S1` (136662945, -124556764) it holds 0.78 mm². M3: one piece holds 251 holes against 268. M4: the candidate touches 15 objects where the reference touches 27, and `GND` forms 5 connected groups against 1. |
| `-05` | `B.Cu` `GND_BOTTOM` | M2 | 27 differences, all held by the candidate, 0.004 to 0.049 mm², 0.1 to 0.2 mm from a track (11), a via (10) or a pad (6) of another net: copper left between two voids that the saved pour does not hold. |
| `-05` | `F.Cu` `GND_TOP` | M2, M3, M4 | 38 differences of the same kind (17 by vias, 16 by tracks, 5 by pads of other nets). M3: one piece against two (a neck of about 130 µm against the 127 µm threshold), whose holes do not match (24 against 0). M4 follows from M3: the one piece touches 47 objects. |

The differences by same-net pads of `-03` (the reference holds copper where Fenolite leaves a relief) and
the copper that Fenolite keeps between the voids of `-05` are the two open findings: rows `H-A-POUR-RELIEF`,
`H-A-POUR-CONNECT` and `H-A-POUR-NECK` of the register name the probes of K6 that settle them (P2 and P3).

## Time

The time of reading a document and pouring every polygon (`test_pour_time`, on an Apple M4, 2026-10-26),
the comparison of the census not included:

| row | seconds |
|---|---|
| `-01` | 0.7 |
| `-02` | 0.2 |
| `-03` | 7.5 |
| `-04` | 0.2 |
| `-05` | 1.1 |
| `-06` | 0.2 |
| `-07` | 0.1 |
| `-08` | 5.2 |

The limit of task 3.6 is 60 s for one document. Before the neck removal took one difference per polygon,
row `-03` took 36.6 s.

## Kit rounds

### 2026-11-04, actual `AD24.5.2.23`, K6 (source S-1572)

A Claude agent ran group K6 at the maintainer's request of 2026-11-04. It operated the Altium Designer
installed in the maintainer's Parallels Windows VM. This is not the maintainer's own review. The tool
reports `Client.GetProductVersion` 24.5.2.23 (Trial licence, not signed in), and the form says `AD 24.5`.

The kit was built at source `99d99244` (`0.7.0.dev0`) with `fenolite kit build --seed 1 --timestamp
2026-11-04T00:00:00Z` (`--dry-run`, then `--confirm --plan`). Its digests:

| file | SHA-256 |
|---|---|
| `kit.json` | `c7153f6b82c39973447c6b6c0339c623477b260e617793203088712609c224eb` |
| `kit_script.pas` | `685ab54f38e643789f2f3abb87d9a590854957d685c42a5067eec8375e26d197` |
| `routed/routed.PcbDoc` | `1667a11afaef4705ede9a4d5a50d1806366848baf82cbcb6e528497d43fce375` |
| `pour/reference/pour.PcbDoc` | `7e56bb3893bd87d2a02cf3cf9c5d435d3dfe7d153fda14acb81d3d003d4a0397` |
| `pour/computed/pour.PcbDoc` | `1c69951175f339971ce1a15addbda82c3696bab324c19ba9370ee84a877b237e` |
| `pour4/reference/pour4.PcbDoc` | `11b920e0ae0755b3c8c8a5c5c084f63745955dd08a2b84a22220c81cffabf5bf` |
| `pour4/computed/pour4.PcbDoc` | `3c7fb61175fa45c8c8c4e457ebff1128039d99d95d2b3651fac88c79f98cd608` |

**Method.** The agent ran the menu commands that the steps name through Windows UI Automation: Tools »
Polygon Pours » Repour All, the Polygon Pour Manager's Repour menu, Tools » Design Rule Check, and File »
Save As. Region counts and violations were read by authored read-only DelphiScript procedures, started with
File » Run Script. Only K6 was run. Groups K1 to K5 and K7 to K9 were not run, and their 40 steps are
`skipped`.

| step | observation | `kit verify` |
|---|---|---|
| K6.1 | `routed`: polygon `GND_L02_P000` (Bottom) had 0 regions before Repour All and 1 after | pass |
| K6.2 | `pour` reference: the manager's Repour menu read `Modified Polygons (0)`, `Violating Polygons (0)`. Force Repour All was confirmed with Yes. Afterwards 19 of 21 polygons hold regions, and `P5` and `P5_NONET` hold none | fail: `pour-match` M2 at P3 and P8 |
| K6.3 | `pour` reference reopened, 0 regions; after Repour All 19 of 21 polygons hold regions | pass |
| K6.4 | `pour` computed opens with no dialog; 19 of 21 polygons already hold regions; saved without a repour | pass |
| K6.5 | the manager lists `Modified Polygons (0)` and `Violating Polygons (0)`; typed `0` | pass |
| K6.6 | DRC: 42 violations (NetAntennae 21, UnRoutedNet 17, SilkToSilkClearance 4). One names a polygon: `Dead Copper - Net Not Assigned`, `Polygon (P5_NONET) on Top Layer`, rule UnRoutedNet. Typed `1` | fail: expected 0 |
| K6.7 | Repour All on `pour` computed showed no confirmation dialog; 19 of 21 polygons hold regions | fail: `pour-match` M2 at P3 and P8 |
| K6.8 | the Advanced Settings (filter All) list no `PCB.Polygon.AdvancedPour`. The searches `Polygon` and `Pour` find only `PCB.Multithreading.PolygonPourByLayer` and `PCB.Rules.UpdateQueryOnPolygonNameChange`. No value typed | skipped |
| K6.9 | `pour4` reference: 0 of 3 polygons with regions; Force Repour All (confirmed with Yes) gives 3 of 3 | pass |
| K6.10 | `pour4` computed opens with no dialog, 3 of 3 polygons with regions, saved | pass |
| K6.11 | Repour All on `pour4` computed (no dialog), 3 of 3 polygons with regions | pass |

**Verdict per probe.** Against Altium's repour in K6.2 and K6.7, Fenolite's pour of `pour` passes the
following probes with M1 to M5: P0, P1, P2, P4, P5, P6, P7, P9 and P10. It fails M2 at two probes:

- **P3 (necks).** Two differences of 0.0044 mm² each, held by Fenolite's pour, at (41.352, −85.993) and
  (41.448, −85.993) mm.
- **P8 (keep-outs).** Eight differences of 0.0083 mm² each, held by Altium's pour, at the corners of the
  keep-out voids, for example (63.255, −63.545) mm.

Both steps show the same ten differences. Against the K6.2 board, the K6.7 board also meets the step's
M1 to M4 condition. All probes of `pour4` (P0, P1 and P2) pass in K6.9 and K6.11.

`fenolite kit verify` exits 5, with three error findings (K6.2, K6.6 and K6.7); 7 steps pass and 40 are
skipped. Its row verdicts:

- **Fail:** `H-A-POUR-KIT`, `-NECK`, `-STEPS`, `-KEEPOUT`, `-OPEN` and `-REGION`.
- **Skipped:** `H-A-POUR-ENGINE`.
- **Pass:** the other K6 rows.

The saved documents hold VM paths, as the verifier's privacy findings report. They stay in the agent's kit
folder outside the repository.

**No record.** `fenolite kit record --dry-run` would write the record `2026-11-04-cda766bd` and give the
passing rows `ALTIUM-VERIFIED(kit; AD 24.5; …)`. The agent did not confirm it, for three reasons:

- The proof of task 7.4 needs `kit verify` to exit 0.
- The approved 24.5 scope does not raise evidence.
- The run was made by an agent.

Every `H-A-POUR-*` row keeps its level, and task 7.4 stays open. Three things remain for the maintainer:

- the P3 and P8 differences;
- the dead-copper finding on the netless sample polygon `P5_NONET` (K6.6);
- the absence of the K6.8 setting in 24.5.

## Approved pending-native scope — 2026-11-03

The maintainer explicitly authorized the pending Altium validations on the
available Altium Designer 24.5.2.23: "tenho so o24.5, mas eu autorizo as
validacoes serem no24, nao precisa ser na26". This replaces the version
prerequisite of pending runs only. Record the actual tool/build, input hashes
and each observed outcome. It does not complete a case, open a write gate,
raise evidence, prove26.5 equivalence or replace any historical26.5 report.
Do not combine different versions/input digests into one fictional kit run.
All existing acceptance criteria, facts-before-code rules and final CI remain.
The kit form keeps its existing AD major.minor dialect: use AD 24.5; keep full
build 24.5.2.23 in the separate native observation report, not a new form key.
