## Context

On 2026-11-01 the exact frozen candidate
`96d687d18450f429bcc57b60087f9e6f43dfb707` completed `make check-fast` with exit 2:
23 failed, 19173 passed, 55 skipped. Lint, generated guides, format, source types
and public residue checks passed. The same commit separately passed all 104
browser cases. Neither the full gate nor a new exact-head CI pass is claimed.

## Decisions

Decided 2026-11-01: separate independent repairs into backend compatibility,
model/lens behavior, public registries, CLI/hermetic contracts and authored-data
licensing. Each owner reproduces its exact failure and proves the correction;
one coordinating branch reruns the entire local gate after integration.

Decided 2026-11-01: update stale expectations only when the implemented behavior
is already specified and independently proved. Fix production code for actual
wrong behavior. Do not disable assertions, normalize away fidelity differences,
accept new losses or broaden unavailable-resource skips to obtain a green run.

Decided 2026-11-01: executable authored fixture/usage data may retain their
explicit CC0-1.0 dedication. Core implementation Python remains Apache-2.0.
Both roles require SPDX and copyright as their first two lines; licence-specific
policy must not relabel authored data merely to satisfy an overbroad check.

Decided 2026-11-01: preserve the documented backend layering and experimental
write gates, complete issue registries using actual declared severities, and
preserve source/model defaults and native byte pins. Any needed native tool
measurement is reported at its actual installed version only.

CLI/hermetic reproduction, 2026-11-01: all three task 1.4 cases fail on the
entry source. Restore the start page's installed-version, copied-version and
placed-starter statements within its existing byte budget. The production
library/pick paging paths include proposals; retain them in the exact capability
expectation. The fast target deliberately includes authored tests/fidelity:
retain that directory and all three external-resource exclusions in its exact
recipe proof, then run the authored fidelity checks. No resource marker or skip
policy changes are needed.

Decided 2026-11-01 for task 1.3: identify authored-library measurements by relative source path and
symbol name. The 73 existing cases remain measured with the same geometry estimate, checked glyphs
and four known limitations; two Mini symbol pairs had collided only by basename. No new native
measurement is needed for a case-label correction. Local native availability is 9.0.2 only; this does
not repeat the existing 10.0.6 glyph calibration or establish Altium text measurements.

Decided 2026-11-01 for task 1.3: complete the documented circuit-warning waiver contract for the
parallel-I2C check, retaining exact row/digest matching and warning behavior without a matching waiver.
Preserve rating-missing and block-port-merged infos. Classify pin literals by their filename/readiness
role rather than skipping a source module; an unknown emitted issue, even named pins.toml, stays visible.
Draftsman explanation references use the existing Build target contract section; no native gate changes.

## KiCad 10 shared references and footprint names — task 1.15

Decided 2026-11-02: the exact `697cdf02` KiCad 10 job `125016358377` in run
`41362730027` reports eight failures. Seven retain expectations from before c0277's
specified pairing of equally repeated, singly placed references. Preserve the raw
reference census and dated conversion tables. Add a source/hash-bound current
comparison record for demo rows 08/16; assert every remaining difference and every
writer-ledger row without filtering comparison kinds or accepting new losses.

Decided 2026-11-02: the remaining failure is a production defect. `prepare` applies
the project/symbol filename sanitizer to footprint names, replacing the safe space
in `M Mount` with an underscore. Preserve interior ASCII spaces only for derived
footprint names. Retain reserved-name handling, path-character replacement and
case-insensitive collision allocation, with distinct `M Mount` and `M_Mount`
regressions. Keep the strict footprint-name comparator and c0318 identity selector
unchanged. Actual local native checks use 9.0.2; the independent KiCad 10 proof and
exact-head CI remain pending rather than inferred from authored readback.

## Evidence

These are repository-internal integration repairs using authored fixtures and
existing registered public facts. No new third-party parser or CAD data is
introduced. Physical/native/private/release proofs remain independently open.

## Native check expectations — task 1.8

Decided 2026-11-01: preserve the exact `96d687d1` CI failure receipt. Run
`41359100272`, KiCad 9.0.9 job `125005408720`, adds three native expectation
failures: two old literal stage lists omit the specified `topology.rules`, and
the authored device/control comparison now reports one `circuit.policy-missing`
info and one `circuit.value-unknown` info only for the device build. Update those
exact expectations. Keep the stage sequence literal, compare code and severity
together, and require the exact informational difference; no new warning or
error may be accepted. Preserve the earlier rating-missing-info exception.

The local proof uses the actually installed KiCad 9.0.2. Its version and results
do not repeat the CI 9.0.9 measurement or establish a KiCad 10 result. No runtime,
model, dependency, schema, refusal, byte pin or native gate changes are needed.

## Model/lens repair findings — task 1.2

The exact five cases reproduce on `2c707d00` (5 failed in 2.50s). Four test contracts are stale:
c0273 replaced the block-version hint with reviewed `blocks upgrade`; c0277 added nullable font
attributes to `FieldRequestLike`; the blink now connects its resistor through `series()`, so the old
generated-symbol helper's text replacements no longer select named/stacked pins; the layer census
replaces legitimate declared user layers with a default-only table. Repair those fixtures while
retaining the original version pin, name-order, connectivity and undeclared-layer assertions.

There is one production omission: native `replace.FIELD_VALUES` lacks the supported `bold`, `italic`
and `face` properties already retained by the lens. Extend that tuple and prove manually edited fonts
survive same-side rotation and native write/read. The existing side-flip/library-default policy stays
in force. Native font extensions remain opaque to the reader: replacement recovers only these three
supported style properties from existing field effects when the corresponding model value is absent.
Explicit model values win; reader defaults, canonical pins and unrelated slots stay unchanged. Prove
the actual native font nodes through write/read and a second rotation, not an assumed reader projection.
The generated-symbol control uses explicit named connections and a matching authored pad
set rather than accepting an invalid pin/footprint combination. No schema, public API, byte pin,
comparison guard, resource skip or evidence level is relaxed.

The task owns `backends/kicad/replace.py` and its five test files. The separate c0318 part constructor,
component conversion, definition resolver, native footprint header and reserved-attribute hunks are
left to their owner. The new font readback control is local; exact native/whole-batch CI remains open.

## Combined field-scope finding — task 1.7

Decided 2026-11-01: the combined replay exposes the new optional
`Component.footprint_definition_ref` in RT-A2's complete-field documentation proof. This is explicitly
a KiCad definition selector; an Altium build already refuses nonempty values before writing. Name
that precise field and limitation in the existing exclusion table. Do not add it to the native write
scope, remove the completeness assertion or change any byte pin or refusal. The historical
`blocks/divider.py` node is an import-only helper rather than a Design; preserve the original failure
list, prove its role and rejection as a Design, and retain both actual design readbacks in the replay.

## Appended component field contract — task 1.9

Decided 2026-11-01: c0318 appends the optional/default-omitted definition selector after the existing
`value_range`, `board_only` pair. The old last-two-fields assertion is stale. Keep an exact last-three
assertion, in order, and the existing `value_range is None` default check. Rename the test and its
explanation to describe this actual append-only contract. Preserve model/schema bytes, constructor
ordering, identity guards and ordinary build pins; only the test expectation changes.

## Supplier fixture filename repair — task 1.10

Decided 2026-11-02: published `697cdf02` reproduces the strict residue rejection of four authored
DigiKey/Nexar authentication fixtures named `token.json` and `token.source.toml`. Rename their role
to `auth-reply` and update test/declaration paths. Preserve all four file bytes and their existing
S-1100/S-1105 source citations. Endpoint paths and authentication protocol fields keep their original
names. No runtime/provider policy, readiness flag, real credential, detector exception or waiver changes.
The original failure and before/after hashes are retained outside the repository; the focused supplier,
proposal, manifest/header and complete residue groups must pass before task 1.10 is checked.

## Canonical temporary paths — task 1.11

Decided 2026-11-02: preserve the original successful and exceptional cleanup
guards, but compare the actual temporary directory by its resolved path. Exact
commit `697cdf02` restores directories and completes the shipped blocks on
Windows; four new regression assertions instead compare short and long path
names. The same assertions fail on macOS temporary-directory aliases. Exercise
an equivalent parent-component alias on every host with an actual temporary
tree, without relying on symlink privileges. This repairs test identity, not
the production runner, cleanup ordering, isolation or authored exception.

Decided 2026-11-02: publish accumulated working branches to obtain CI results
while the complete local gate runs. Integration closure waits for the complete
gate and exact published-head required CI, as AGENTS.md workflow 4 requires.

## Windows portability — task 1.12

Decided 2026-11-02: use the actual L8 Windows job 125016358456 on `697cdf02`
as the failure receipt. Match a planned circuit cache by its normalized path
components, so a Windows separator cannot hide an available circuit difference.
Keep error builds unavailable and preserve all staged-plan input bindings.

Decided 2026-11-02: explicitly set the authored ZIP fixture's existing Unix
creator metadata, including its README entry. Preserve exact checked archive
and member payload bytes; prove the complete container remains identical when
the stdlib's host-default creator metadata is simulated as Windows.

Decided 2026-11-02: the Part F authored candidate kit uses a relative library
reference on one drive and a rooted, POSIX-spelled reference across drives.
Replace the whole project-relative library prefix when rooted, retain the
exact library source and ordinary plan digest bindings, and do not catch
unrelated path errors or claim native Altium acceptance.

The rooted-source negative control exposed an existing staged-plan omission:
ordinary Altium symbol resolutions did not declare their source library bytes.
Bind each actually resolved, non-authored symbol item and its library table in
`Result.depends`, beside the existing script/layout inputs. Retain the independent
drawn-unit alias bindings when this packet joins Alpha. Prove symbol and table
edits return FEN-4002 before any output, without broadening native write gates.

## Windows UTF-8 and library input paths — task 1.13

Decided 2026-11-02: exact `697cdf02` CI run `41362730027`, Windows job `125016358456`,
shows locale-decoding failures in legal/starter/supplier assertions and generated review HTML.
Read and rewrite these UTF-8 documents explicitly; retain their licence, source and HTML bytes.
The library's source-register reads already specify UTF-8. Its actual CLI failure is the unguarded
`_library_check._relative`: `os.path.relpath` rejects inputs on another Windows drive, and the
error handler calls that same helper again. Match the existing `cmd_library` display convention:
relative POSIX text on the same drive, absolute POSIX text when Windows reports different drives.
Keep findings, warning thresholds, record validation, dependency hashes and sheet writes unchanged.

Prove the original nine Windows cases in a subprocess whose default `io.open` codec is cp1252,
with a non-cp1252 UTF-8 witness and no global UTF-8 environment switch. Separately inject the
Windows cross-drive exception at the path boundary and exercise actual library findings, record
errors, sheet plans and current-input dependencies. Do not transliterate content or weaken fixtures.
Native Windows and the complete integration gate/CI remain coordinator-owned.

## Drawn coordinate warning contract — task 1.14

Decided 2026-11-02: the exact L9 source `46d788ee` introduces the existing
`drawn.coordinate-rounded` warning, already taught and explained, but its CLI
issue-table row is absent. The unchanged consistency assertion reproduces that
single omission. Name the warning and its explicit `--allow-lossy` prerequisite
in the normative CLI table; preserve refusal without the flag, warning severity,
quantization behavior, native bytes and every existing documentation assertion.

## Drawn backend evidence declaration — task 1.16

Decided 2026-11-02: exact L9 reproduces three backend contract failures.
The new drawn writer already carries `H-A-DRAWN-WRITE` at INFERRED in its
build result, but declares no module evidence; its own-package facade import
also misses the existing pure-module boundary check. Declare the same existing
evidence in its owner, reuse that constant in the lens, and import the exact
pure `schdoc` module. Preserve import rules, levels, hypotheses, write gates
and native bytes. Regenerate the evidence inventory; no native application
acceptance or new hypothesis is asserted.

## Severity and current-week provenance — tasks 1.17 and 1.18

Decided 2026-11-02: exact L9 CI reports the one missing expected warning
`drawn.coordinate-rounded` and no session row for ISO week 2026-W45. Add the
existing warning to the exact severity expectation; preserve every severity,
waiver and refusal. Record the actual backend evidence/import review and reused
registered format notes in the annex under the required contributor identity.
No new source fact, private material or native Altium acceptance is asserted.

## CM5 native9 downgrade CI diagnostic

CI41611925152 native9 returned different for CM5_MINIMA_3 and its aggregate probes. First preserve the declared corpus source and conversion report, identify unexplained equivalence findings separately from actual project DRC/ERC type deltas, and retain complete native logs. A repair must address the demonstrated source of difference with an authored control and focused native9/10 validation. Existing expected types/probe outcomes, loss ledger and strict assertions remain unchanged; no vendor CAD enters core and no unknown difference becomes an acceptance waiver.

CM5 cause established before native execution: the sole unexplained difference is component-missing M705, an explicitly pinless off-board purchasing symbol absent from the PCB. The API read-back preserves c0334 source BOM identities but conversion preparation did not, producing a false addition. Coordinator approved a private shared API helper reusing the existing checked preserve traversal before writing, so the typed source identity reaches the writer/census. Keep SourceProject paths/files/rules/issues/evidence unchanged, retain ambiguous-unit refusal and Altium unsupported-BOM refusal, and add no convert-to-importer dependency or import-graph exception. Native CAD output maps and original probe expectations must remain unchanged.


### Historical release records and current continuation tasks

The historical v0.4/v0.5/v0.6 release and native-acceptance claims remain unchanged. Their existing guards continue comparing current task files: append explicitly dated current tracking for newly opened tasks rather than pretending they existed at the old release cut. A numeric continuation ID may have one lowercase letter suffix; it must remain a distinct task, including its checked/open state, and an unnamed open continuation must fail. Negative guards use authored temporary task files when their purpose is independent of a real task later completing. No checker exemption, freeze/graduation change or native evidence promotion is introduced.

### Windows documentary evidence encoding

The two failed Windows tests read UTF-8 tasks and the maintainer approval, and one writes a temporary archived tasks copy. Set UTF-8 explicitly on those three operations. Keep all assertions and evidence bytes unchanged. A focused CP1252-default I/O control reproduces both failures before the fix and runs the same tests afterward; this is a local portability control, not a passing Windows CI claim.

## Native visual proof lookup after archive (task2.19)

The documentary reader resolves exactly one active or archived c0276 directory
before reading `native-visual-proof.json` as UTF-8. It uses the same small candidate
selection rule as the existing census proof lookup, without importing one test
module from another or adding a production API. Missing, file-only and ambiguous
layouts refuse before reading. Temporary active/archive copies under a controlled
CP1252 default execute the original approval/scope checks and retain exact proof
bytes. All 171 prior assertions and all native evidence remain unchanged. This
prepares a later normal archive; it does not close c0276 or promote any hypothesis.
