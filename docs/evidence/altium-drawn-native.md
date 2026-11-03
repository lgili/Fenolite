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
