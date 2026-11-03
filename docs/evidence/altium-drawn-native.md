# Authored drawn projects in Altium Designer 22.2.1

Actual maintainer-host measurement, 2026-11-02, using only Fenolite-authored
projects. [The observation](altium-drawn-native.json) retains the writer source
commit, all native export hashes, complete compiler messages and raw name
differences. The external `fenolite-cac-altium22-native-20261102` archive holds
the reviewed builds, scripts and raw receipts. No third-party CAD is committed.

The documented native scripting entry point and workspace API compiled each
exact owned project. An independently authored SDK probe exported every
physical component pin and each native net object's memberships. Comparison
uses net-object identities, not names; uncovered native-net pins must be
source-open singletons, and duplicate/missing/extra pins refuse. This is an
actual native graph observation, not the complete kit or a GUI-authored proof.

| Original fixture, each binary and ASCII | Components | Pins | Groups | Raw name differences | Compiler messages |
| --- | ---: | ---: | ---: | ---: | --- |
| example | 4 | 38 | 33 | 1 | 3 errors, 2 warnings |
| full | 3 | 36 | 32 | 1 | 4 errors, 1 warning |
| repeat | 4 | 8 | 5 | 2 | compile-success information only |

All six complete pin partitions equal code. All 92 originally planned input
files retain their exact SHA-256 values after these native runs. Example/full
have intentional source singleton/floating input findings and a raw `IN` name
difference. Repeat retains reported instance qualification. None is silently
accepted or treated as a full native gate pass.

The original full fixture exposes a real writer defect: Altium rejects `{BUSA}`
as a wire label on a bus. Its declared members B0/B1 are exactly representable
as `B[0..1]`; c0331 owns the correction and independent connected-hierarchy
controls. Original failures remain historical evidence.

## Save observation

The first documented `DoSafeChangeFileNameAndSave` call, using document kind
`SCH`, returned true and changed the in-memory name but created no file. It is
not a save proof. On another owned root clone, explicitly marking modified and
using the documented format name `Advanced Schematic binary` wrote a 23552-byte
file, whose digest is retained. The later complete experiment saved all fourteen
schematic files of the six original projects and eight files of four corrected
controls, then reopened and recompiled all ten projects. Every saved file exists,
has native CFB bytes and a retained SHA-256. Both original output forms were
saved in this explicit native binary format. All complete pin partitions, raw
name findings and compiler messages equal their corresponding pre-save results.
No original input or unrelated document was saved. Native save is distinct from
GUI authorship.

## Corrected native controls and deliberate failure

Clean signed writer `c8faa50cabe8b1228b0362e775e127767761c84d` builds both forms
of the full fixture and a connected two-sheet alias control. Every planned byte
was reviewed, confirmed and hash-checked; all sixty files copied to Windows
match that receipt. Native compilation removes exactly the full fixture's
invalid bus-label error. All other compiler and raw name findings are unchanged.
The connected control has forty pins in thirty-six groups and zero raw name
differences in both forms; its remaining two errors/two warnings describe the
authored open inputs U1-11/U1-12. Native save/reopen preserves these outcomes.

A separate deliberate fault changes only the child bus port from `D[0..3]` to
`BROKEN[0..3]` in a copied authored ASCII case. Actual native export still covers
all forty pins, but splits exactly four two-pin groups into eight singletons:
forty groups instead of thirty-six. The comparator correctly refuses with exit
1; no missing/extra pin or accepted difference conceals the broken boundary.
All 167 declared original/corrected/negative input files remain byte-identical
after the native runs. A corrected saved positive sheet is left current in the
application; the deliberate fault is retained only as a separate test control.

## Complete local fast gate and model-0 boundary

`make check-fast` on clean signed c8faa50c completes with **1 failed, 20099
passed, 50 skipped** (pytest 798.45 s; whole command 890.86 s, make exit 2).
Only the existing Mac `board_40parts@altium` byte guard fails; the head and worktree
stay unchanged/clean throughout. Static, guide/generation, format, types and
private-list residue pass. This is a completed failing gate, not successful CI.

All seventy-five complete example plan maps equal the earlier clean de6c6f2f
Mac capture, including all 1172 file hashes and ten unchanged strict refusals.
That comparison does not make the old Linux golden match. Fresh model-0 capture
retains 174 dataclasses, 1244 fields, forty fixed extension keys and all twenty
v0 schema hashes. Model 1 remains inactive and its transition proof stays open.

The API facts reuse registered S-0501/S-0503/S-0504/S-0505. Native format names
come from the public IServerDocument reference, not vendor installation files
or decompilation. Native acceptance, remaining ERC/name/visual/save requirements,
full formal kit execution and exact-head CI remain open. H-A-DRAWN-WRITE stays
INFERRED; no source ERC finding, default byte guard or tolerance is waived.


## Current native24 clean-control acceptance (2026-11-03)

[The scoped clean-control receipt](altium-clean-drawn-native.json) records actual
Altium Designer **24.5.2.23**, one frontend started2026-11-03T00:58:08Z, and writer
`da89051f6bd7cfe81cae5fd3daedaa3e8d565629`. This is a new application-version
measurement; the original22.2.1 observations above remain historical evidence.
Only new isolated Fenolite-authored clones were opened, compiled or saved.

| Control | Complete pins | Groups | Declared-name differences | Every compiler message |
| --- | ---: | ---: | ---: | --- |
| Unmarked ASCII |40|36|0|2 errors,2 warnings on U1-11/U1-12|
| Marked binary, before and after native save/reopen |40|36|0|1 compile-success Info each; no error/warning|
| Marked ASCII, before and after native save/reopen |40|36|0|1 compile-success Info each; no error/warning|
| Independent child-port NAME-only broken ASCII |40|40|4|14 errors, strict partition difference|

The two marked controls declare only the truly unused U1-11/U1-12 inputs; each
root has exactly two active point-scoped NoERC directives and the child has none.
All original and saved marker coordinates, active/suppression flags and symbol
text are identical. The point's native SUPPRESSALL flag is retained; there is no
global ERC configuration change or marker on a connected bus pin. Every native
pin/net membership and all36 native short/full names are identical before
marking and after save/reopen. The broken control still splits four connected
two-pin groups into eight singletons and reports the unmatched bus boundary;
its40-pin universe and all14 messages are retained, not filtered.

Both original output forms were saved as `Advanced Schematic binary` into new
owned copies. Four files exist with native CFB headers and retained digests;
each was closed and independently reopened, then both complete saved projects
were recompiled/exported. All60 reviewed source files remain byte-identical on
Mac and Windows, and save-source clones remain unchanged. SDK scripts, raw
exports, versions, source/plan/input digests and every message remain in the
external `fenolite-cac-altium24-clean-drawn-20261103` packet. S-1293 records the
original authored controls; existing S-0501/S-0503/S-0504/S-0505 supply SDK facts.

This completes only c0276 task6.3's independent clean acceptance control. It
does not retroactively pass original6.2's source findings, claim GUI authorship
or all Altium versions/metadata, or promote H-A-DRAWN-WRITE from INFERRED. The
overall gate, required exact-head CI and maintainer reviews stay open.
## Original example correction on actual24 (2026-11-03)

[The separate current-example receipt](altium-drawn-example-native.json) binds source963f9cc0,
authored correctiona0e8e5ed and actual Altium24.5.2.23/PID8436. The original current source reproduces
all38pins/33groups with equal connectivity, but IN is named NetR2_1 and the compiler retains3errors/
2warnings. Historical22 observations and the independent40pin6.3 control above are unchanged.

The authored correction terminates the existing R2/R3 input chain at GND instead of VCC, giving a
real second ground terminal; explicitly marks only unused U1-11/U1-12; and labels the existing parent
IN wire. All four components and38pins remain. Binary and ASCII both export the complete33groups,
all declared names and Info1 only, with no global ERC setting or native writer change.
Four new-copy documents were saved as Advanced Schematic binary, closed/reopened and read back;
all four are actual CFB files and every root2/child0 marker position/flag/symbol is exact. The saved
binary project also recompiles/exports all38pins/33groups/names exactly with Info1 only.

The first saved-ASCII operator stopped after compilation at its own I/O32 sharing error in
FenoliteStage Append(stage.txt); that incomplete attempt and all failed transport/collection
records remain preserved. The user consciously stopped that owned SDK. An independent Windows
I/O control reproduced sharing error32, then passed1000 existence-only marker checks while a
producer held its exclusive marker and verified a closed export hash, without touching Altium.
A fresh ASCII-saved-v2 attempt uses unique immutable phase events and polls only final-marker
existence. Complete exports at10:28:59Z retain every38pins/33groups/all names and Info1 only;
the partition SHA matches both corrected forms and saved binary. No successful native case was
repeated and no active stage or final-marker content was read. This repairs the operator without
claiming that the original automation error was a CAD connectivity defect.

All45 reviewed original outputs and30 save-source copies retain their hashes at collection. The
three deterministic drawn byte rows are independently source-bound: original complete plans equal
the established table, and only circuit/board/PCB/root/child outputs change with the intended source
correction. Library/project/rule/manufacturing bytes and all unrelated rows remain fixed.
Task6.4 is complete. Wider6.2 acceptance, H-A-DRAWN-WRITE and exact-head CI remain open. S-1295 is separate
from S-1293; no version26.5, full fixture cohort, GUI authorship or evidence promotion is claimed.

## Current24 FULL/REPEAT memory batch — 2026-11-03

The maintainer started the reviewed `RunC0276MemoryBatch` once. All eight owned
cases compiled and produced closed message, component-pin and net-object dumps.
All126staged source/SDK files remain byte-identical. The exact source versions,
88-file collection and export hashes are retained in
[the memory observation](altium-drawn-full-repeat-memory-native.json), S-1300.

| Case, both binary and ASCII | Physical pins | Complete physical groups | Declared-name differences | Native messages |
| --- | ---: | ---: | ---: | --- |
| Immutable FULL baseline |36|32|1(IN)|3Error/1Warning|
| Corrected FULL |40|32|0|Info1 only|
| Parent REPEAT |8|5|2(FB0/FB1)|Info1 only|
| Canonical REPEAT |8|5|0|Info1 only|

The original net-object comparator is retained: every native physical pin is
accounted for; graph edges come from native net-object membership, not matching
names. Uncovered pins must be source-open singletons. FULL
DM_Component.DM_Pins includes U1-32, while DM_Nets omits its membership and
includes a zero-pin B[0..1] bus row. This raw API-view difference remains explicit;
U1-32 is verified against the source as open. No connected pin is discarded.
All declared native short/full names match in the corrected cases, and complete
pin dumps and every net-object name/member agree between the two source forms.

The corrected FULL includes actual R3/R4 10k B0/B1-to-GND loads and intentional
NoERC only on11/12. REPEAT now returns literal FB0/FB1 with the full original
eight-pin/five-group partition, instead of accepting its older qualified names.
Earlier implementation/focused repairs predated this current24 baseline
collection; the baseline was compiled before the corrected copies in this batch.

This phase invokes no Save/Close and does not satisfy native save/reopen.
Tasks6.5/6.6, aggregate H-A-DRAWN-WRITE graduation and exact integration CI remain
open until their independent remaining proofs pass. Historical22.2.1 findings
are not overwritten or combined with this24.5.2.23 batch.


### Current24 FULL/REPEAT native save/reopen — 2026-11-03

S-1300 follow-up: `RunC0276SaveReopenBatch` saved ten fresh owned schematic
copies (two sheets per corrected FULL project and three per canonical REPEAT
project), closed/reopened every document, then compiled/exported all four
projects. Both binary-origin and ASCII-origin inputs were natively saved as
binary. Every complete raw `messages.txt`, `pins.tsv` and `nets.tsv` is
**byte-identical** to its corrected memory export: FULL40pins/32groups and
REPEAT8pins/5groups, exact declared and generated names, Info-only compilation.
This retains empty bus metadata and the explicitly documented FULL source-open
U1-32 manager-view difference; no raw pin or net object is filtered.

The collection contains84 exclusively read, closed files, including all ten
native saved documents. All116 staged support/source/SDK files and all126
original memory inputs remain hash-identical. The operator invoked the exact
owned procedure once by keyboard after proving its focus and enabled OK;
unsuccessful earlier UIA selection did not invoke it. The temporary operator
task definition was removed before input was permitted. See
`altium-drawn-full-repeat-saved-native.json` for source, SDK, document and export
hashes. No personal project was saved or closed.

This completes the save/reopen portion of tasks6.5/6.6. Their earlier current24
baseline chronology is disclosed by the memory proof; this follow-up does not
rewrite it. Aggregate6.2, census7.1/7.2 and exact-commit9.2 CI remain independent;
`H-A-DRAWN-WRITE` remains `INFERRED` until all original acceptance gates pass.
