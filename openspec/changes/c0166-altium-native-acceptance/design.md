# Design

## Scope and authority

On 2026-10-13 the maintainer explicitly requested that the agent execute all
pending Altium tests, record results, fix problems and archive/commit after the
tests pass. This authorizes native UI automation on Fenolite-authored and registered
public cases. Work on uniquely named disposable copies and guard every destructive
UI operation by document title and owned directory. Leave unrelated projects alone.

## Inventory

Use the most recent evidence report over an older release summary. Track schematic
A1-A6, B1-B3, L1-L6, N2-N3, H3-H4; PCB D1-D3, C1-C2/C6-C8;
Repeat R1-R4 and c0151 R5; remaining X8.6 counts and the supplementary c0132
long-via measurement; OutJob Gerber lists/border/old empty-output observation;
optional planted DRC and clearance matrices; project hierarchy modes and rule
export; native-template appearance and imported custom border; Part T on DIFAT,
SCHEMATIC and PADSTACK connector masks; formal kit K1-K9; and separate Viewer
requests V2, N4 and C5. Record an unavailable branch, app or required source as
blocked with a concrete reason, never as passed. Use kit results for overlapping
checks only when its case actually satisfies the older criterion.

## Results and repairs

Record date, exact Altium version, source case/hash, step, expected and observed
outcome, evidence level, and follow-up change. Keep screenshots and native saved
files in ignored runtime storage. Retain historic reports and identify superseded
results. Public format facts remain sourced; native observations qualify only the
measured case. A successful UI check is not a recorded formal kit run.

The initial full gate recorded 17 failures, 13376 passes, 3288 skips and 2 xfails.
Classify missing tools/cache, symlink privileges, fixture declarations, timing
failures and actual product defects before changing code. Restore prerequisites
first; do not change frozen measurements to match an incomplete corpus. Record any
test prerequisite handling explicitly and preserve execution where supported.
Add a focused repair task before every code change and run its proof before the
next repair. Do not run overlapping full suites. Archive each prerequisite change
in dependency order only when its tasks are complete; retain incomplete changes.

The public schematic conversion exposed missing copper offsets: KiCad keeps the
hole at the pad position and shifts copper by the drill offset in the pad frame
(existing `H-G-FRAME-OFFSET` evidence). Project the opaque offset into the model's
per-layer copper offsets before Altium lowering, including derived libraries.
Keep original slots unchanged and test rotated and bottom footprints independently.
Do not relax clearance rules to compensate for lost geometry. Native repour must
be established from actual saved filled copper, not merely sending a shortcut.

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
