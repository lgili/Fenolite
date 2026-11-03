# Bounded immutable native-rule preservation

## Approved scope

The root reviewed the closed binding, two-build bootstrap, exact ownership,
readonly generated-input guard, generic native predicate profile and the sole
metadata normalization before implementation. No new public command, DSL
method/argument, canonical field or public format ID is added.

Only a native DRU with rule items left opaque by the existing reader activates
this fallback. Fully modelled programs keep their existing editable DSL
conversion, including supported NetName/NetClass conditions; no extra sidecar,
guard or capsule is emitted for them. Other existing lossy refusals remain.
The source input's DRU digest stays in the import read-set in either case.

The fallback preserves the ENTIRE original DRU byte-for-byte, including its
modelled rules, opaque rules, comments and priority/order. This does not assert
that the original board is DRC-clean, that native DRC results are equivalent,
or that all original caches survive. Existing unjudged rows/notices remain
visible. In particular the public source proof retains all27 routing notices
and L6's explicit custom-rule unjudged scope. The separate cache investigation
c0360 is not a dependency or an approved API of this change.

## Original-to-first-output qualification

`backends.kicad.native_rule_profile` owns a bounded generic grammar from official
format facts S-1296: Boolean combinations of Type, Layer, paired Net identity,
isPlated and the measured fabrication mark, with a bounded physical constraint
set. It never whitelists a board or rule name and evaluates no arbitrary native
expression. Unknown properties, functions, clauses or unsupported forms refuse.
The public author's17 rules are external proof data, not core constants/fixtures.

Before certifying a first output, compare native types, pad kinds/fabrication
marks, layers, physical copper net equivalence classes and silkscreen context
independently between original and emitted PCB reads. A.Net/B.Net compares
identity, not spelling: full physical-object partitions preserve NO_NET,
uniqueness and multiplicities. Empty nets have no selectable physical items.
Ambiguous nonempty partitions refuse; singleton generated net-name changes
cannot merge/split/swap memberships. Literal NetName predicates are not supported
by this native-only fallback; the existing fully modelled DSL path is unchanged.

The importer separately runs exact represented levels1–7, without profile
exclusions, through importer/check. The import/lens/backend layering table is
unchanged. Known derived-cache notices do not become an equality claim. The
new preservation policy remains INFERRED, with its own scoped hypothesis.

## Actual two-build bootstrap

1. Emit the existing code, libraries and declared project, without declaring
   the native-rule pair yet. Build it in the existing private import scratch.
2. A private ContextVar observer captures the REAL `target_design` immediately
   before write_triad, after ordinary lowering, and the REAL final emitted
   PCB/project bytes after native identity binding and other writer effects.
   Require exact script owner/name/target and exactly one early and late capture.
3. Independently qualify the original-to-output context above. Construct the
   internal receipt from this actual model/output/read-set, not a source-only
   approximation or a caller-supplied success boolean.
4. Add original `native/project.kicad_dru`, the closed receipt, and an explicit
   generated readonly guard requiring both exact relative paths. Leading-private
   guard aliases cannot collide with emitted user identifiers (the normal
   printer strips their surrounding underscores). A missing file or pair fails
   through the existing design-script FEN-3004 path even on a fresh build.
5. Build again. Both ordinary validation and every binding check apply. Capture
   never disables validation; a present DRU without its receipt refuses.

Capture/scope contexts reset in finally, reject nesting/wrong owners/zero or
multiple observations, and cannot bless a failed build. A failed scratch build
retains its primary diagnostic and emits no capsule or write plan. Conversion-
generated KiCad rules from an Altium input are not mislabelled original KiCad
input; that existing conversion path is unchanged.

## Closed internal receipt

The backend/lens-owned receipt is `native/project.rules-context.json`:

```json
{
  "version": 1,
  "target": 10,
  "project": {"path": "project.kicad_pro", "sha256": "<64hex>"},
  "rules": {"path": "project.kicad_dru", "sha256": "<64hex>"},
  "source_inputs": [{"path": "<portable original name>", "sha256": "<64hex>", "kind": "<existing KiCad kind>"}],
  "baseline": {
    "encoding": "canonical-design-v1-tool-version-neutral",
    "sha256": "<complete lowered model fingerprint>",
    "producer_tool_version": "<actual tool version>",
    "emitted_pcb_sha256": "<actual final PCB bytes>",
    "emitted_project_sha256": "<actual final project bytes>"
  }
}
```

Reject unknown/missing/duplicate keys, wrong types including bool-as-int,
unsupported versions/targets/encodings, unsafe or duplicate source paths,
invalid hashes, mismatched project/DRU source hashes, invalid UTF-8, symlinks,
missing inputs and oversized/deep invalid JSON. Apply the existing full-dialect
DRU target gates/self-check without rewriting its original bytes.

The fingerprint serializes a COPY of the COMPLETE actual lowered Design using
canonical.dumps, replacing ONLY `/header/fenolite_version` with the empty string.
The field remains present. No other version/schema, ID, provenance, CAD field,
default state, physical property, rule, source metadata or finding is exempt.
Do not use dump_texts, which also replaces schema metadata. Actual model and
actual output bytes are never normalized. Producer version is retained for audit.

Every build checks the complete model early AND the actual final PCB/project
byte digests late, in memory before a write plan. This also catches resolved
library changes, writer effects/options and preserve_minimums changes that do
not alter the early model. The project, DRU and receipt are plan dependencies;
changed inputs invalidate confirmation with FEN-4002. Existing modified output
DRU files refuse instead of being blindly overwritten.

The source/program binding is review provenance, not a security signature or
permission to accept electrical findings. It intentionally makes native-only
imports immutable: unsupported edits require a new reviewed import. Exact seed,
ID or target differences can refuse; no fuzzy normalization is added. Tool
0.7.0.dev0→0.7.0 is compatible only when the sole model metadata value changes
and all remaining model state plus native PCB/project bytes stay identical.

## Proof and publication boundary

Authored controls cover whole-model fields/mapping keys/defaults, tool-version-
only positive, header/schema and physical changes, net partition renaming/
merge/split/swap/NO_NET/multiplicity, unknown predicate refusals, closed receipts,
late byte guards, actual minimum-context changes, nested/leaking capture attempts,
primary failed-build diagnostics, missing pair and stale confirmation. Actual
native9.0.9/10.0.6 loading canaries keep all findings visible. Public source tests
use an immutable six-input external author bundle with licensed DRU; no CAD or
3D payload enters core. Default75 complete build maps and ordinary no-DRU import
maps remain byte-identical. Required full CI on the final integration commit,
item audit/review, catalog publication and release are separate pending gates.
