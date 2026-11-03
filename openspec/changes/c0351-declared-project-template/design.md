# Declared native baseline and owned settings

## Measured missing carrier

On c0348 typed/context source, a fully authored Mini full project was given all
five non-default project controls. Actual API import dry-run, reviewed confirm,
build dry-run and reviewed confirm all exit0. The import reports unexpressed=[].
The generated script has no intersheet declaration. Fresh output resets every
control to its shipped default; original input hashes are unchanged. The external
receipt names every input and stage. Existing importer Source carries minimums,
classes, text variables, drawing sheet and curve error, not original project JSON.
The only current ExistingProject.project comes from an existing output folder.
The shipped project_template helper is not an original-source carrier.

## Recommended explicit request

Add `Design.kicad_project(path: str, *, sha256: str) -> None`, once per design.
The DSL records a relative native input path and mandatory lowercase64-hex digest;
it does not read a file. It is an explicit request, not ambient discovery. No
canonical entity or native opaque extension carries project JSON. No new Fenolite
file format is needed: the sidecar is the existing backend-owned .kicad_pro type,
with its digest declared in generated Python.

The CLI resolves the file within the script directory, verifies regular readable
UTF-8 bytes and the declared digest, parses exact project JSON and checks supported
versions before staging. Absolute paths, parent traversal, drive/UNC/URI forms,
missing/unreadable files and symlinks leaving that directory refuse. Raw JSON uses
the existing exact codec: objects only, no duplicate keys/NaN/Infinity, number
spellings retained, versions checked by the existing backend. A declared future
project refuses even with allow-lossy; no silent fresh-template replacement.

The input is data, not authority to discover/copy additional files. Known native
external-resource references must remain portable and agree with declared/modeled
inputs under existing import/build path checks; unsupported external/absolute
resources refuse rather than being followed. Unrecognized strings are not treated
as paths by heuristics. No additional file is read merely because JSON names it.
Tests must separate the declared sidecar path guard from embedded native resource
references and harmless metadata/text strings. Existing format knowledge remains
backed by the public project documentation and authored controls.

## Precedence proposal requiring review

When the request is absent, current build/output preservation behavior and bytes
remain exactly unchanged. When present, the declared native template is the
explicit baseline for unmanaged project keys, including on rebuilds with an
existing output project. This authoritative-input rule avoids old bad output
settings overriding a newly declared source template. Existing board/layout/custom
rule preservation is unaffected. Native GUI project edits are not silently adopted
as code: they must be incorporated into the declared input and its reviewed digest.

All typed/code-owned model, DSL and build settings win after that baseline through
the existing project writer: rule/class minima, stack-up/curve/error controls,
text variables/drawing-sheet inputs and fresh generated root/file/cache identities.
Do not delete typed-owned JSON patches, use template values to override them or
retain stale source UUID/page ownership. Plan geometry/planners and final output
must use the same effective baseline, avoiding disagreement between planning
constraints and the written project. Reuse ExistingProject.project as in-memory
input; never write a native output file first or construct a fake preserved board.

An alternative fresh-output-only fallback would retain manual unmanaged output
edits, but could keep an earlier bad output when the declared template changes.
The recommended authoritative-input behavior is concrete and reviewable; task0.2
must decide it before implementation.

## Import emission, inputs and replay

Source reading captures checked original project text in an appended ephemeral
Source/build field, bound to its existing declared input/digest. When an original
project exists, import emits a portable `native/project.kicad_pro` sidecar and an
explicit `design.kicad_project(..., sha256=...)` call. This intentionally extends
generated import output; ordinary scripts without the request retain old bytes.
Do not assume arbitrary unmanaged metadata is semantically modeled, suppress an
unexpressed physical item or widen an equivalence acceptance to make it pass.

The sidecar participates in build depends/read_files and plan hashing. Changing it
or the generated declaration invalidates a reviewed plan with existingFEN-4002,
without output changes. A mismatching declared digest is a located input failure
before a plan, never an implicit refresh. A caller must review new bytes/digest.
The pure in-memory builder can receive validated text without filesystem reads;
file-based public paths still require the explicit digest-bound request.

Altium output refuses this explicitly KiCad project request before staging,
including with allow-lossy. No experimental translation of unknown project JSON.
Generated Python remains portable after moving its entire folder. Every written
sidecar/output has a receipt digest; source snapshots remain immutable.

## Proof and compatibility

First reproduce the missing5 controls with the actual API and independent native
SVG effective reference text. Establish no-request exact native/canonical/default
bytes before implementation. Author path/hash/JSON/version and stale-plan negatives,
plus conflicting typed settings, stale root cache and existing-output precedence.
After correction, prove original→generated sidecar/Python→fresh/repeated build with
all5 controls and an independently authored physical native-rule knob retained.
Compare complete pins/partitions/names and actual native9/10 effective text/DRC
where claimed. Public Royal replay remains independently measured, not a baseline
change. Preservation alone is not global level6 semantic validation.

The new public DSL surface requires tested guide teaching, gen_agent_guide and
current gen_cli_surface review delta. Sidecar format ownership stays with the
existing KiCad project format. No runtime dependency, canonical model1 field,
int/canonical version bump, loss flag or default no-request behavior change.
Root owns combined fast and exact-head CI; archive only after literal proof.

## Coordinator decision — 2026-11-02

Task0.2 is approved with the recommended public method and authoritative unmanaged
rebuild precedence. Typed-owned floor/classes/stack/curve/textvars/frame and fresh
root/cache identities must win consistently for planning and final output. All
strictness and no-request compatibility boundaries above are mandatory. Ordinary
import output intentionally gains a declared native input; fixture changes must
be measured and reviewed, never blindly regenerated. No canonical field is added.
The public surface delta is an implementation change, not completion of the
separate pending maintainer surface-inventory review.
