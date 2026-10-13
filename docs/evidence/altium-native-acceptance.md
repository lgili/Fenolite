# Native Altium acceptance campaign

Started 2026-10-13 under c0166, at the maintainer's explicit request to execute
the pending checks, record outcomes and repair defects. Runtime cases are authored
for Fenolite or fetched from the registered public corpus. Native binaries and
screenshots remain in ignored build storage. A pending row is not an approval.

The maintainer subsequently requested manual execution with files, full local
paths and a screenshot checklist. Automated GUI driving was stopped for that handoff. The runtime
handoff is `build/altium-testes-manuais-20261013/LEIA-PRIMEIRO.md`: corrected
Part T files, an untouched-input kit copy, authored legacy samples, copper
bisection/plane cases and generated script-copper/value/tenting/ASCII supplements.
The guide specifies per-step screenshots and native Save As destinations.
Preparing this handoff does not approve any pending native check; results will
be recorded after the maintainer submits observations and saved files.
Handoff proof: 31 projects and 210 files, every listed project document present,
input SHA-256 manifest and ZIP integrity verified. Added a standalone authored
long-footprint-name PcbLib. R5 remains blocked by the missing implementation;
Viewer access and a specific external custom-template case remain separate.
The maintainer then requested automation while working on a second monitor.
Authored native scripts execute through RunScriptFile in licensed Altium 26.5.0
without mouse input, SendKeys or explicit focus changes. The read-only probe
returned 165 pads for SCHEMATIC. The final serialized inventory collected all
21 boards, and native Save As wrote 11 documents. Proof command
`uv run python build/altium-native-scripts/Verify-Native.py` passed: both final
logs completed without errors, all outputs exist, input hashes are unchanged,
and native PADSTACK pad/via/component/polygon counts match the authored input.
The first overlapping inventory logged a wrong-path guard for flat during Save
As; it is retained. The launcher now blocks overlap, and the successful retry
has a separate log. Runtime scripts, instructions and results are in
`build/altium-native-scripts` and `build/altium-script-results`.
The first proof covers collection and saves; subsequent checks are recorded below.

Initial partial kit verification returned exit 5: seven steps pass, K1.2 fails and 24
steps remain skipped. K1.2 reports missing footprint/parity information in the
native-saved flat PCB. This result is superseded by the guarded serialized save
below. Results also
retain native local-path metadata and remain in ignored storage. Missing form
fields and remaining outputs are pending work, not a passing kit run.

### Subsequent native results, 2026-10-13

- K1.2: guarded serialized Save As preserves four components and 14 pads;
  equivalence and parity pass. The original empty output is retained in ignored
  storage. No PCB writer repair was needed for this case.
- K1.5: native project Save As through the registered `PcbProject` document kind
  writes the result project without modifying the input.
- K2.1-K2.5: all five projects compile successfully. Tree has two warnings about
  nets without a driving source; the other cases have only successful-compile
  information. The kit's unchanged `CompileAndExport`/`KitRoot` routines also ran
  for all five explicitly addressed projects. Automatic focusing of already open
  projects did not work for four cases in the first wrapper; those guards stopped
  before compilation, and explicit project references replaced that wrapper.
- K4.1-K4.4: native editor tree contains the five expected clearance/width rules;
  native DRC reports their expected scopes and values, one PWR width violation
  and one VIN/LED_A clearance violation. The report also has two unrouted and
  three antenna violations; its seven total findings are retained, not suppressed.
- K5.2-K5.3/K5.5: native PCB layer bar visibly indexes six copper layers ending
  at Bottom Layer. Native API confirms through, blind and buried via spans, and
  all four authored text strings/layers/rotations/mirror flags. The legacy stack
  API was unsupported; the layer count comes from the native layer bar screenshot,
  not a captured Layer Stack Manager view. Subsequent K5.4 native API measurement
  returns keepout mask 3 on the single authored keepout: vias and tracks only,
  using the bit mapping already recorded in `pcb-records.md` (S-0470/S-0020).
- K6.1: native polygon rebuild and save produce poured copper; resave, parity,
  poured and copper checks pass. The public SCHEMATIC saved copy also reads back
  with one polygon containing one fill, superseding its earlier unpoured result.
  This does not replace the remaining native DRC/ECO acceptance for SCHEMATIC.
- K7.1-K7.2: native OutJob views show all six outputs and correct fab/doc links.
  Both containers generated: 23 output names, including Gerbers, drill, placement,
  BOM and a 46709-byte PDF. Native binaries and screenshots remain ignored.
- K8.2-K8.3: the actual native rendered title block shows `Flat`, revision `B`.

Verification of that earlier kit: **26 pass, zero fail, six pending**, exit 0, with no kit or
form integrity problems. The whole kit remains incomplete. The first immutable
partial record is `2026-10-13-61513e18` (eight passed steps); the subsequent
record `2026-10-13-e8794749` retains that history and records 26 passed steps.
The first archive was preserved separately before writing the subsequent one.
The compile-log verifier now rejects
native error classes bracketed twice by the script; warning-only logs still pass.
The subsequent keepout measurement advances the working folder to 27 passed
steps and five pending; it is not yet included in that immutable 26-step record.
The maintainer authorized a foreground interval for the remaining UI commands.
K3.1 now passes after native ECO into an authored empty `eco.PcbDoc`: four
components, 14 pads, four nets and zero invalid changes (K3.2). Validation and
execution screenshots are retained locally. A preliminary dialog addressed
`flat.PcbDoc`; it was closed without execution before selecting the owned empty
target. Focus and menu invocation alone were never treated as a completed ECO.

The initial full library replacement found all seven symbols and executed seven
valid changes, but K9.1 failed: all footprint models disappeared and LED pad-net
memberships changed. The original working folder therefore has **30 pass, one
fail, one pending**, not an approved run. Both earlier immutable records remain
unchanged. An ownership-only retry also failed: resolved catalog symbols had no
footprint model to attach. The repair adds the common component footprint to
resolved library symbols, its shared pin map and the emitted PcbLib filename;
model records receive their parent indices. Conflicting user footprints remain
unselected. In a freshly built `build/altium-schlib-model-retry` kit, native full
replacement found all seven symbols, validated and executed seven replacements,
then saved `results/libs/libs.SchDoc`. `uv run python build/verify_libs_model.py`
reports no level-2 netlist or parity differences. Focused writer/map regressions:
39 passed. Failed outputs, native screenshots and fresh-kit receipt remain in
ignored storage. This successful retry is separate from the earlier run and
does not silently change its inputs, archive or recorded verdicts. K1.8 and the
remaining legacy campaign are still pending; the fresh kit needs the other
native steps repeated before a complete run can be recorded.

The fresh library retry is recorded as `2026-10-13-fccaa526`: K1.3, K9.1
and K9.2 pass, no failures, 29 steps pending. Its separate archive has SHA-256
`fccaa526b168dc5bce55060a1b7efa1708bf1dfeb4654ef2446215f28dd2c980`;
it remains unpublished in ignored storage. The three records are historical
measurements of their respective kit digests, not a combined complete run.

The corrected fresh kit now verifies **32 pass, zero fail, zero pending**,
with no input or form integrity problems. Native saves, five compiles, planted
DRC findings, six-layer/via/text/keepout checks and repour were repeated on that
kit. The complete run is recorded as `2026-10-13-462b38ba`. Its result archive
has SHA-256 `462b38ba3cc4812ddeea626865c8c097e50f0ed9f2473dc0f79a7455f80a4b93`
and size 1236513 bytes; the archive remains unpublished in ignored storage.
`kit verify` passes, reviewed `kit record` confirmation writes the immutable
record, and `kit status` reports no problems. Earlier partial records remain
unchanged. This completes K1-K9, not the remaining legacy/Part T/Viewer campaign.

Title/revision retry: an initial background screenshot contained stale PCB
pixels and was rejected. The first native PDF rendered blank special fields;
failed reprints preserved its timestamp because another application locked it.
The original PDF and error are retained. A new isolated copied project explicitly
attaches the OutJob and sets the guarded native project context. Its SchDoc is
byte-identical to the fresh kit (SHA-256
`a248b046695b833f015e5b59a9d4b4a03684a3c5aa6d15e90df9242f443800f6`).
The actual new two-page native PDF renders `Flat`, revision `B`, owner `Fenolite`
and date `2026-10-06`; extraction and a rendered crop were inspected. PDF SHA-256:
`979aa5c0ed02e9d8eb44b4ac890b0113f9ddd233648717506dd3331ea1d1f0dd`.
K8.2/K8.3 use this explicit copied-project rendering method. Native label API
values also resolve correctly. No title writer repair or blanket acceptance of
other printing contexts follows from this result.

A subsequent guarded view of the actual fresh-kit `flat.SchDoc` also renders
`Flat` and `B` correctly in the native GUI; its scoped capture is retained.
Fresh K7 generation produces 23 file names, including both Gerber faces, drill,
placement, BOM and a 44883-byte native PDF. Fresh K3 uses the documented native
File/New API to create a zero-component, zero-pad board. Twelve ECO changes
(four components, four nets, one component class, one net class, two rules)
validate and execute with zero invalid changes. Guarded native save confirms
four components and 14 pads; the verifier finds no netlist/parity differences.
K1.8 audit opens and natively saves ten new, byte-identical copies covering
K1.1-K1.7 (including all four tree sheets). Each job confirms Open/Show/Save As
and has no additional native top-level window afterward; no prompt was dismissed.
A busy-window preflight before the ASCII case was retried before opening it.
Source digests, saved-file digests, native logs and per-job window observations
are retained separately. This is the scoped API opening/saving method used for
K1.8, rather than an inference from missing repair messages in compile logs.
The owned submenu window needs its own handle for local clicks; routing through
the main window does not activate that popup action. Each command retained its
source/target guards, and no cursor movement was needed for this retry.

Documentation/evidence proof after the title diagnosis: 48 passed (136.11 s).
The final full gate is still running and has reported a failure; its complete
traceback is awaited before any repair or archive/commit decision.

The preceding full gate finished with 3 failures, 14485 passes, 2207 skips and
3 expected failures (3211.62 s). The router budget and public hierarchy conversion
pass on isolated retry with the restored KiCad executable configured. Inspection
of the public microwave board proves two modified POLY instances; its exact
conversion ledger was corrected, and the census/pad-offset proof passes all
9 cases. Broader library/readback/evidence tests pass 129 cases; pyright reports
zero errors or warnings. A new fast gate is running; final full approval remains
pending after these changes.

X8.6 native Save As of the authored `body2.PcbDoc` now measures three records
in `ComponentBodies6` and three in `ShapeBasedComponentBodies6`. None retains
the original MODELID, all three have a nonzero MODEL.CHECKSUM, and each saved
body has 35 property keys. The native-saved file and log remain ignored.
`test_body2_saved_report`, with the actual native output supplied, passes
(one test, 3.16 s). These are observed counts; identifier changes are retained
in the report and do not imply preservation of the original identifiers.

C8 initially fails: native opening/save discards all three tented combinations,
while the authored source records hold them. Native calibration identifies the
solder-mask cache: a tenting setter alone has no effect under the rule cache;
setting the documented cache to manual first preserves top tenting. The two
native-saved prefix changes are byte 1 (12 to 44) and byte 66 (1 to 2).
After the writer repair, the fresh authored `build/altium-via-tenting-retry`
case reports and saves none/top/bottom/both as expected. Native OutJob Gerbers
confirm actual openings: top mask has cases 1 and 3, bottom has 1 and 2, and
case 4 has neither. The openings are 1.0032 mm in diameter (0.8 mm copper plus
0.1016 mm radial expansion). `verify_tenting_masks.py` checks native saved flags,
the native Gerber coordinates/apertures and records file hashes; it passes.
Focused writer/copper/KiCad-import-oracle tests: 18 passed (19.72 s).
`Verify-Native.py` again confirms unchanged original input hashes. All failed
and calibration files remain ignored; this measured C8 acceptance is separate
from the formal kit runs and does not alter their historical digests.

Thirteen explicitly addressed legacy projects were compiled serially, preserving
their original hashes. The Messages manager was cleared per project and all
classes exported; DM_Compile returning true is not treated as an error-free
compile. `verify_legacy_compile.py` passes the scope/hash checks and N2/ASCII-N3
criteria: neither reports pins U1-2/4/8, while both retain the expected floating
input error for unmarked U1-3. Both also report one floating No ERC warning;
directive rendering/mode inspection remains separate. Hierarchy has no errors
and four warnings about multiple net names; exact membership/harness-file checks
remain pending. Repeated channels has eight errors and four warnings, including
duplicate Repeat(OUT), missing child-sheet and a sheet entry on a bus. The
existing authored two.Annotation fixture was loaded after an acknowledged native
warning; it is not a generated R4 annotation result. The other legacy messages
remain in ignored storage and are not silently counted as passes.

The inventory uses the latest reports in [schematic evidence](altium-schematic.md),
[PCB evidence](altium-pcb.md), [project reader evidence](altium-project-read.md)
and the [kit history](altium-kit/README.md). Some release summaries still list
Parts G, X8 and V as owed; the 2026-10-09 reports already settle their main cases.
Only their unreported supplementary measurements remain below.

| Request | Remaining acceptance | Current outcome |
|---|---|---|
| Schematic A1-A6 | ASCII opening, nets, ids, links, CRLF/LF and native ASCII save | A3/A5/no-UID native API/readback passed; LF loses eight components, CRLF retry passed; appearance/Properties pending |
| Schematic B1-B3 | ECO into an empty PCB, rebuild after a value edit, full/selected-attribute library update | pending |
| SchLib L1-L6 | pins, multipart/common pins, footprint models, keyed symbols, update connectivity and native save | native API/readback confirms 10 symbols/35 pins, common/hidden pins and saved models; Pin Editor appearance and L4/L5 updates pending |
| No ERC N2-N3 | suppression limited to marked pins, including the ASCII case | N2 and ASCII N3 compile criteria pass; marked pins suppressed and unmarked U1-3 reported, appearance/mode still pending |
| Hierarchy H3-H4 | compile messages, exact net memberships and native harness-file behavior | passed after naming-priority repair: zero errors/warnings, nine nets/25 memberships, two unchanged child harness files, no new top file |
| PCB D1-D3 | pad dimensions/holes, long names, library project listing, empty-board ECO and bottom-side placement | long-name native save preserves full name/two pads; other details pending, prior opening/matching-ECO reports retained |
| Copper C1-C2/C6-C7 | exact nets/sizes, stack thicknesses, internal-plane connectivity and script-authored copper | C1 native geometry and C2 stack passed; C7 preserves 11 tracks/7 vias; C6 plane/GND assignment preserved, direct connectivity pending |
| Via tenting C8 | none, top, bottom and both, including mask openings/expansion | passed after manual-cache repair; native saved flags and top/bottom Gerber apertures verified |
| Repeat R1-R4 | retest connectivity, designator/room formats, ECO and annotation | R2 naming matrix: twelve known combinations match native, mixed style observed at one level; R1 bus conflict and R3/R4 pending |
| Repeat R5 | c0151 bus split follow-up | remote 4958647d artefacts tested: three errors/six warnings, bus and OUT links still fail; implementation not integrated here |
| Bodies X8.6 | counts from the native saved file | measured: 3 plain/3 shape-based, 0 original MODELID retained, 3 nonzero checksums, 35 keys each; X8.1-X8.5/X8.7 prior reports retained |
| Via supplementary measurement | nine further bytes of the long via record before/after removing shapes and changing end-layer options | pending; Part V's layer-id mask already reported as expected |
| OutJob | Gerber counts/extensions, O6 border observation and exact-version confirmation of the historic empty-Gerber case | pending; current output generation/settings already reported |
| Rules | optional planted DRC, c0125 per-layer matrix and c0130 object-type matrix | pending |
| Project reader | five Net Identifier Scope values and exported RUL fields/encoding | pending |
| Templates | native-template logo/font/color appearance and imported custom border | pending; prior W report remains valid for its original case |
| Part T PADSTACK | connector masks and broader stack coverage | Full Stack four-layer case and PcbLib placement passed; masks pending |
| Part T SCHEMATIC | T1-T6, hierarchy and connectivity | T2 passed with 18 warnings; T5 retry matches all 68 components, four valid proposed removals, no ECO execution; remaining T1/T3-T6 acceptance pending |
| Part T DIFAT | T1-T6 on the large converted document | pending |
| Formal kit K1-K9 | actual execution, verified saved files and recorded run | complete: 32 passed, zero failed/pending; recorded run 2026-10-13-462b38ba |
| Altium 365 Viewer | binary-project ZIP V2, No ERC N4 and copper C5 | uploaded in isolated browser; all three remain processing after five minutes, native-saved control also stalls; no rendered acceptance |

## Measured results

- **PADSTACK, 2026-10-13, Altium Designer Professional 26.5.0:** generated PCB
  and native placement from its PcbLib show In1 circular 1.2 x 1.2 mm and In2
  rectangular 1.4 x 1.1 mm. See the [scoped native report](altium-padstack-part-t.md).
  This does not approve connector masks or other stack cases.
- **SCHEMATIC, 2026-10-13:** opened the owned public-source project and its root
  `complex_hierarchy.SchDoc` in the native interface; the root renders components,
  wires and two sheet symbols. Initial validation exposed four errors on U102
  pins 6 and 7: conversion lost explicit KiCad no-connect marks. After preserving
  marks and omitting their isolated pseudo-net wires, Project validation at
  09:27:14 in Altium 26.5.0 reports **Compile successful, no errors found**.
  The copied native Messages table has 18 warnings and one info row: four duplicate
  common-pin warnings (U201/U301 pins 4/8), and 14 nets without a driving source.
  No electrical rules were changed. Root SchDoc SHA-256:
  `aa6bfe293f0b3dd16ee6f91fec3bad952fb7e11a0a138ab6d57c2a299496ba7b`.
  Native screenshots and copied Messages are retained in ignored build storage.
  This verifies T2 of this case, not the remaining document/DRC/ECO steps.
- **Formal kit preparation, 2026-10-13:** built 42 files with seed 166 and timestamp
  `2026-10-13T00:00:00Z`, using the CLI's reviewed dry-run plan and confirmed receipt.
  Preparation is not a passing native kit run. Runtime directory:
  `build/altium-native-acceptance-kit`.

- **SCHEMATIC copper offsets, 2026-10-13:** the public source passes KiCad
  10.0.6 DRC (zero violations and zero unconnected items) and Fenolite's source
  copper check. Before repair, both Fenolite and native Altium report 23 clearance
  violations in the conversion. Preserving opaque KiCad drill copper offsets
  removes all 23: native Altium 26.5.0 DRC and the generated-document copper check
  both report zero clearance violations. The corrected PcbDoc SHA-256 is
  `f80f3dc6e0e735d997072de0ce4b2af40616b0ff4015aead243fe020030efa15`.
  Native DRC still reports 25 unrouted, 9 minimum solder-mask sliver, 152
  silk-to-mask and 60 silk-to-silk violations. These results do not approve T4.
  A native Save As after requesting Force Repour All retains one polygon with
  no read-back fill; the manager showed zero area. Repour remains unproved.
  Authored regressions cover four pad rotations on both board faces and the
  derived library, while retaining the original KiCad write bytes.

## Local verification and execution blockers

- Initial full gate: 17 failed, 13376 passed, 3288 skipped and 2 xfailed, 1634.50 s.
  Static checks passed. The earlier eight-worker fast gate had 8 failures; its five
  non-symlink failures passed in isolation.
- The full gate's three routing/export failures passed on isolated retry: 3 passed,
  50.28 s. No assertion or production behavior changed for those retries.
- Restored the registered non-heavy rt0/Altium corpus: 343 selected items, 319
  fetched, 24 already cached, no download failures. Partial-cache measurements
  were retried against this complete selection: 22 passed, one unrelated heavy
  case skipped; its registered heavy file was subsequently fetched.
- Declared all 72 already committed, Fenolite-authored c0162 downgrade fixtures
  in the data manifest without changing their bytes. Manifest proof: 47 passed.
- The maintainer enabled Windows Developer Mode; all three previously failing
  symlink cases passed (5.13 s) without altering assertions or skipping tests.
- Native automation subsequently returned foreground window handle 0. Operations
  stopped before sending editing commands; the maintainer has been asked to keep
  the interactive Windows session unlocked/connected. Earlier opening observations
  remain valid. The maintainer restored the interactive session; native validation
  and message capture resumed successfully. Further cases remain pending.
- No-connect repair regressions: 106 passed, 14.56 s. The final full gate remains
  pending; isolated retries do not stand in for a passing full gate.
- Offset/conversion/stack regressions: 48 passed, 14.76 s. The latest four-worker
  fast gate reports 1 failed, 13065 passed and 151 skipped (1041.83 s), with static
  checks passing. Its only failure was a Hypothesis generation-speed health check
  in `test_split_rebuild_identity`; the same seed passed in isolation (5.92 s).
  No assertions or health checks were disabled. A final passing gate is still owed.
- Subsequent two-worker `make check-fast` passed: 13074 passed, 151 skipped,
  1560.36 s, with lint, formatting, agent guide, pyright and residue checks passing.
  The final full `make check` is still owed.

Multipart link retry, 2026-10-13 (S-0731): the initial conversion matches
66 of 68 components. U201/U301 have two schematic unit identifiers each; the
PCB links use unit 1, while the compiled native group uses unit 2. A fresh
owned calibration reverses lexical UID ordering between the two components:
native compilation still chooses the last written unit in both cases. The
first calibration compilation retained cached old IDs and is not proof; the
freshly reopened project is the measured result. This establishes the writer
case, not arbitrary imported unit permutations.

The writer now remaps PCB source links from the actual emitted sheet plans.
Twelve authored cases cover one/two/three units, flat/hierarchical sheets and
ASCII/binary output; the broader focused proof has 118 passes (16.01 s). The
corrected owned public conversion opens directly into the native ECO, matching
all 68 components without manual linking. Validate Changes reports four valid
removals: unconnected-(U102-LV-Pad6), unconnected-(U102-OSC-Pad7), and the
Default/power net classes. The two pins are explicitly unconnected in the source;
the classes are PCB-only. No component addition/removal or footprint replacement
is proposed. The ECO was closed without Execute Changes; captures and native
logs remain ignored. This is matching/validation evidence, not an executed T5
result or completion of Part T. Original handoff files remain unchanged.

Focused Repeat retry explicitly selects the owned project and opens root and
child documents before compilation. It reports three errors/eight warnings,
superseding the earlier eight/four result for this method: OUT1/OUT2 single-pin
nets and the Repeat(OUT) sheet entry placed on a bus remain. The missing-child
and duplicate-Repeat findings disappear. The existing annotation was loaded
after its own scoped warning; this remains distinct from generating R4 output.

Legacy D1 long-name and C7 native retries, 2026-10-13: separate guarded native
open/save jobs complete with no error log. D1 preserves the exact footprint name
`Fenolite_Authored_Footprint_Name_Longer_Than_31_Characters` and its two pads.
Source SHA-256 8430aba7eda56d51b905158a8806d618f436cb5febdf8fbac5a7631e058d7304;
native saved SHA-256 bf033a7423409364580f0c03e7cb98ef57650379795645c40aa2f053073bc130.
This proves preservation on open/save; direct library-list rendering remains
separate. C7 preserves 11 routing tracks and seven vias: tracks GND=4,
LED_DRV=4, LED_A=3; vias GND=6, LED_A=1. The native inventory's 35 total tracks
includes 24 component graphic tracks, which are excluded from the routing count
by their component ownership. Source SHA-256
6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a;
native saved SHA-256 8a5b29edde272eb25d48917587b13119819befee4f5a07458464b9e542b9d882.
`verify_legacy_d1_c7.py` passes native completion, exact counts/memberships and
all original handoff hashes. Native saved files remain ignored. Evidence:
ALTIUM-VERIFIED(author-report), Altium Designer 26.5.0 on Windows.

Read-only native API geometry retry additionally verifies C1's five free tracks,
one arc and three vias against the authored protocol. Track/arc widths are
98425 internal coordinate units (approximately 0.25 mm), VIN tracks 196850
(approximately 0.5 mm); all vias are 236220/118110 (approximately 0.6/0.3 mm),
Top-to-Bottom. Nets/layers agree with Part C's table. C7's native InComponent
filter independently confirms the 11/7 routing count. The initial P46 script
used the track Width accessor for an arc and was canceled at its owned native
script dialog; its partial log is retained and not counted as a pass. P47 uses
the documented arc LineWidth accessor and completes. Actual airwire appearance
and C2 dielectric measurements remain pending.

The expanded full quality gate completed with 20 failed, 16300 passed, 377 skipped
and three expected failures in 9532.05 s. The last registered-probe test invokes
all probes with per-tool timeouts, explaining why 99% remained visible for a long
interval. Failures are retained for scoped diagnosis under task 1.18. This gate
preceded the multipart fix and is not approval to archive or commit.

Expanded conversion oracle diagnosis (S-0732/S-0733): seven measured public
boards import free PCB pads as separate blank-reference footprints. Counts by
case 01/04/07/12/13/16/17 are exactly 14/1/2/9/9/3/24, matching the independent
conversion census. These are explicitly counted importer wrappers, not permission
to ignore arbitrary reference ambiguity. In ecc83, eight rotated U1 slots import
with one-number oval drills (observed `(drill oval 0.762)`); the reader preserves
that unusual token rather than inventing missing slot dimensions.

A separate guarded native Altium collection on the same generated ecc83 board
confirms all nine U1 holes: HoleSize=401575, HoleWidth=799213, HoleType=2, with
rotations 144/108/72/36/0/144/108/72/36 degrees, approximately 1.02 by 2.03 mm.
Thus this discrepancy is in the external import, not a demonstrated missing hole
in Altium. The initial logs and imported native files remain ignored. The
triangle tests now require these exact wrapper counts and exact eight drill
locations/values, retaining all numbered-component and other geometry checks.

Additional gate repairs: the SchLib oracle's nine tests pass after expecting the
authored common component footprint on default-free symbols; source pins remain
compared exactly. Four rebuild identity tests pass after excluding internal
metadata with Path.parts on Windows. Twelve guide tests pass with both extra
rules examples covered. Corpus parity passes after using POSIX manifest keys
on Windows; all 132 schematic rows were already correctly cached.

Legacy library collection/save, 2026-10-13: the corrected scoped native job
reports four example symbols and six generic sample symbols, with 20 and 15
pins respectively. DUAL_OPAMP has two parts; pins 1/2/3 belong to part 1,
5/6/7 to part 2, and power pins 4/8 to common part 0. MCU8 pin 8 reports
IsHidden=True. Saved native libraries retain each source pin number/name,
electrical type, owner part and hidden flag, with unchanged original hashes.
Native saved DUAL_OPAMP keeps SOIC8/FenoliteDemo and RES keeps
R0603/FenoliteSample.PcbLib. `verify_legacy_libraries.py` passes.

Example source SHA-256 71abcfba4f4fc1d95f6ce37730817537d5432c26a78ef8e32e7b30f64d1a3b49;
saved SHA-256 519ec58cee52a762481c680bf2b0912e5eaa0b98af33485ef96635cb9ed69e94.
Sample source SHA-256 fbcf22282d5c274f7220bbe0b3c862f2fb6932aad2407a14d179da1367d6cf1e;
saved SHA-256 439cfb61ddd78f23ba09434b3fc9966eec0beacd34928601745f1b6a8381a08d.
This verifies L1/L2 metadata and L3/L6 saved-model/pin criteria through native
API/readback; direct Pin Editor appearance and L4/L5 legacy project/library
updates remain separate. Initial P49 used the sheet iterator and returned no
symbols; P50 collected pins but encountered an unsupported cleanup method.
Neither is treated as a complete pass. P51 uses the library iterator and shared
destroy method and finishes both native saves without a modal/error. All runtime
logs, partial outputs and native binaries remain ignored. Evidence:
ALTIUM-VERIFIED(author-report), AD 26.5.0 on Windows.

Stable multipart retry: a separate source-unit link override now avoids changing
the PCB component/document identities derived from the primary ID. On the same
authored units inputs, disabling only this remap recreates the previous pins;
normalizing only SOURCEUNIQUEID bytes makes the PCB files byte-identical. Only
the PCB and its build receipt digest change. Writer/project proof: 115 passed
(34.83 s); pinned/multipart proof: 95 passed (29.62 s). A fresh native corrected
public case again matches all 68 components and validates the four earlier
removals; the ECO was closed without execution. All 68 physical component IDs
also match the preserved handoff. The same-input document GUID proof uses the
authored units baseline, not the separately prepared handoff's header GUID.

Native ASCII A3/A5/A6, 2026-10-13: the compiler reports the expected eight
components and every one of the six nets/19 pin memberships of Part A. Native
Advanced Schematic ASCII Save As of the CRLF sample preserves all eight
components and netlist/parity. The no-UID variant also preserves them, generating
eight distinct component UIDs where the source has none. The LF-only variant
opens but saves with zero components, losing all eight; this remains a failed
LF import observation. A fresh copy differing only by LF-to-CRLF conversion
then saves with all eight components and empty netlist/parity differences.
Fenolite's ASCII writer already uses CRLF by default, so this is a measured
native input limitation, not a reason to change source electrical data. Exact
hashes/outcomes remain in ignored legacy-ascii-proof.json; no failed output is
counted as acceptance. Direct sheet appearance and U2 Properties remain separate.

Native hierarchy H3/H4 repair, 2026-10-13 (S-0734): a freshly focused baseline
reproduces four SPI_* multiple-name warnings, while retaining the correct nine
nets/25 pin memberships. In a paired owned project, setting the documented
AllowPortNetNames and AllowSheetEntryNetNames to zero removes all four warnings
without changing a single membership. The writer now sets those options only
for generated harness projects. Flat/no-harness bytes remain unchanged.

A new generated hierarchy project compiles with zero errors/warnings and the
expected six components, nine nets and all 25 memberships. Its two child
.Harness files retain their exact authored bytes; no top .Harness is created.
Focused project/hierarchy proof: 76 passed (1.36 s); golden/manifest proof: 78
passed (2.11 s). Only the authored hierarchy PrjPcb golden changes, exactly by
the two naming options; its source protocol hash is updated. Failed baseline
messages and all native/generated runtime files remain ignored.

Copper C2 native stack inspection/save, 2026-10-13: the owned routed board's
Layer Stack Manager shows four signal rows and Prepreg/Core/Prepreg dielectrics
of 7.874/39.37/7.874 mil, approximately 0.2/1.0/0.2 mm. The native saved copy
confirms Top Layer/Mid-Layer 1/Mid-Layer 2/Bottom Layer and the three heights
within 2 nm of the requested values after displayed-text rounding. Saved file
SHA-256 5e5a91861c10603898fa6c2d7a25b8265b8ba1e2c17f4153910fffa5afbab943.
The ignored grid capture corroborates types/thicknesses; names are checked in
the native saved file because the conservative crop excludes their column.

C6's first collection script stops at its owned script dialog and is canceled;
its partial log is retained as failure. A byte-identical isolated source copy
then opens/saves normally: native saved copper chain (1,39,3,32) comprises Top
Layer, Internal Plane 1, Mid-Layer 2, Bottom Layer, with plane 1 assigned GND.
Saved-file proof remains ignored. This is stack/net-assignment evidence; direct
plane connectivity and appearance remain pending. Original handoff hashes
remain protected.

Viewer access attempts, 2026-10-13: isolated headless Edge 155.0.4283.45 reaches
the official standalone Viewer and uploads only authored V2 ZIP, N4 SchDoc and
C5 PcbDoc inputs. Essential-cookie-only choices are made in isolated temporary
contexts; no user browser profile or desktop input is used. Each input remains
at Processing the Design for the full five-minute observation, without a
rendered result. A separate native-Altium-saved flat SchDoc control also remains
processing for two minutes. Observed failed network requests concern analytics,
not a demonstrated Viewer document request. The reason remains unknown; neither
a Writer defect nor a Viewer pass is established. Input hashes, screenshots and
logs are retained ignored, and no persistent sharing link is created. V2/N4/C5
remain unverified pending a successful render.

Latest fast quality gate after the source-link identity and harness naming
repairs: 13092 passed, 151 skipped (1444.83 s), all static gates passed. A single
full gate now runs with the restored KiCad CLI and heavy corpus cases enabled.
The earlier failed gates remain retained. The subsequent cleanup commits and
eligible archives are recorded below; this campaign remains open.

Repeat R5 remote-commit probe, 2026-10-13: local remote ref
origin/c0151-repeat-bus-split contains commit 4958647d, which is not integrated
in this working branch. Its three Fenolite-authored project/sheet artefacts
are extracted byte-for-byte into a uniquely named runtime copy. After explicit
project focus and opening both sheets, native compilation still reports three
errors (OUT1/OUT2 single-pin nets and Repeat(OUT) sheet entry on a bus) and six
missing-footprint warnings. Six components/11 pins are collected: the channel
capacitor output pins remain NetC12_CH1_2/NetC12_CH2_2 rather than OUT1/OUT2.
Thus the remote proposed correction does not settle R5 on this native run.
Commit/input hashes and the full result log remain ignored; no merge/cherry-pick
is applied. The branch absence is no longer an inability to test its artefacts,
but current integration and the native bus/connectivity defect remain open.

Repository cleanup, 2026-10-13: the maintainer requested separate commits for
completed work and eligible archives. Twelve signed-off Conventional Commits
separate campaign planning, pad stacks, fixture provenance, no-connect markers,
copper offsets, kit checks, library models, via tenting, multipart links,
harness naming, portable acceptance proofs and measured native evidence.
Their proof scope is recorded in each commit body; a pending full gate is not
reported as passed.

| completed change | archive commit | updated living specifications |
|---|---|---|
| c0163-opaque-net-stored-name | cb962d7e | kicad-file-backend |
| c0156-kicad-cli-docker-user | cfa8ccf9 | kicad-oracle |
| c0157-yardstick-route-order | 741559b0 | release-gate |
| c0158-equivalent-public | da39b667 | cli-contract, design-equivalence, package-layering |

Each archived change had all tasks checked with its existing proof record,
passed strict change validation and was archived through OpenSpec. Every updated
living specification passed strict validation. These archives do not assert
completion of the broader Altium campaign or the current full gate.

Other task-complete changes remain open in dependency order: c0123 waits for
c0083; c0126 waits for c0123; c0077 and c0114 wait for c0126; c0137 waits for
c0123; c0139 waits for c0091; c0131 waits for c0125/c0130; c0132 waits for
c0130/c0131; c0152 waits for that clearance chain. Optional native tasks of
c0125/c0130 remain unchecked. c0160/c0161/c0162 and c0166 retain their explicit
incomplete tasks. No pending native test or probe is silently marked passed.

Cleanup proof: the focused verification-docs, hypotheses, provenance and
repository-layout tests pass (61 passed, 71.20 s). Strict c0166 validation and
the whitespace check also pass. The single full suite continues separately;
this focused proof does not close the full-gate task.

Continuation in dependency order, 2026-10-13: c0091 is reconciled with the
completed current kit and archived in edc3f5a4. Fresh native verification passes;
status has four records, no stale rows and no problems. Publication stays under
c0092 and no write kind graduates from this archive alone.

Part R naming matrix (S-0736): eight documented formats and five room styles
were compiled in thirteen uniquely named authored projects. All twelve resolved
predictions match the physical R1/C12 designators exactly. The one-level mixed
style yields alpha suffixes; its general mapping stays unknown. Every case
retains the three OUT/bus errors. Keyword case, child endpoint/I/O/wire, project
scope/naming flags, bus label/line geometry, native setters and native save/reopen
controls have not repaired the underlying connectivity failure.

Part R annotation (S-0737): the original R4 menu path opens sheet numbering.
The component workflow is Tools / Annotation / Board Level Annotate. On one
owned authored project, the naming-scheme checkbox of a resistor row is disabled
and a custom physical designator is proposed. The native ECO contains one
physical-component annotation, validates and executes with green check/done
states. Its Annotation document is saved through the native client as a
305-byte indexed INI file, then reloaded in a fresh project. The file stores
LogicalDesignator0, LogicalPartID0, DocumentName0, ChannelName0, UniqueID0,
PhysicalDesignator0 and PhysicalDesignatorLocked0 under DesignatorManager, and
SheetNumberOrder/SheetNumberMethod under SheetNumberManager.

The UI proposal label names R1_CH1, but the saved channel/UID and the fresh native
compile identify the CH2 resistor as the changed component. The actual result
is R1_CH2 to R101_CH1, while R1_CH1 remains unchanged; the stored/reloaded identity
is authoritative. No cause or general native UI defect is asserted. The repaired
reader retains every byte and reads one mapping with zero annotation issues;
the repaired one-level Repeat association agrees with all six native physical
designators and exactly seven internal VCC/MID pin memberships. OUT/bus
connectivity still fails and PCB transfer is not proved. Nested Repeat annotation
paths remain unresolved. Initial reader regressions: 17 passed; combined reader,
Repeat and channel proof: 93 passed; pyright: zero errors/warnings. Native files,
UI captures and the scoped proof JSON stay ignored.

Full gate checkpoint before the annotation repair: 16397 passed, 331 skipped,
three expected failures and two failures (7394.12 s). The failing net-tie case
ungrouped-touching has an extra native shorting_items finding; its probe records
different rather than the frozen equal verdict. The failed gate is preserved.
It does not validate the subsequent annotation repair, and no probe baseline is
silently updated. c0083 and the current campaign remain open.

Native KiCad diagnosis after the failed gate: five serial DRC runs on the same
authored board SHA-256 vary without any input-byte change. Ungrouped-touching
reports shorting_items plus solder_mask_bridge four times and mask only once;
ungrouped-close reports clearance once and no counted copper violation four
times. Five further runs restricted to one inherited CPU also vary (touching
short three times, close clearance three times). This establishes native oracle
instability for these exact cases; CPU affinity does not resolve it, and the
underlying cause is not established. All ten reports and the identical input
hash are retained ignored. No test expectation, probe baseline or production
KiCad behavior is changed to turn this into a pass.
