## Context

- **Source.** `docs/research/circuit-as-code.md`, section 3 ("Reference designators and identity") and core
  change C. Step 2 of the batch order: c0249 is implemented with c0248 (devices), after c0246 and c0247.
- **What exists on `dev` (0.6.0).**
  - `Part(ref, lib_id, ...)`: the ref is required, and it is also the last segment of the component path
    (`<module path>/<ref>`, "Design structure and names").
  - Ids are derived from paths (`derived_id("cmp", "dsl", "component:<path>")`), never from refs. The
    model keeps `Component.ref` apart from `Component.path`.
  - The layout lens matches footprints by uuid, then by the `fenolite.path` property, then by alias, and
    "References, values and positions MUST NOT be used as keys" (`layout-lens`, "Footprint matching").
    A change of ref therefore already keeps the layout.
  - `design.moved(old, new)` and `dsl.moves()` give new → old part paths, with module aliases expanded.
    An alias is needed for one build only.
  - The build reads user files beside the script (`placements.toml`, `schematic-placements.toml`) but
    writes nothing there: "A build MUST leave the script folder unchanged" ("Reproducible builds").
    `sync --to-source` writes `placements.toml` through plan and confirm.
  - Exit code 7 means "lossy operation refused" (`FEN-7001` to `FEN-7003`).
  - The DSL "reads no library, file or environment".
- **What the public tools do** (concepts only). One keys layout on the hierarchical path and keeps refs,
  net names and picks stable across rebuilds, with a "frozen" mode for releases. One warns that renaming
  the design loses the stored layout. One keys manual edits on refs, so a rename orphans them. Fenolite
  takes the path as identity, and the lock as the reviewed record.

## Goals / Non-Goals

**Goals**

- A part can be written without a ref. Its ref is assigned deterministically and then never changes by
  itself.
- The refs, and later the picks and pin choices, live in one reviewed text file written only through plan
  and confirm.
- A release build can prove that nothing locked moved (`--frozen`).
- Existing scripts (explicit refs everywhere) build byte for byte as before and get no lock file.

**Non-Goals**

- See the proposal. In addition: refs stay board-wide unique (KiCad requires it). A block-local namespace
  is c0251's choice on top of this lock.

## Decisions

### 1. Identity is the path; a part's key

A component path is `<module path>/<key>` (or `<key>` at the top). The key of a part is, in order:

1. `name=` when given (matching `[A-Za-z0-9_.+-]+`);
2. the explicit ref when given, which is exactly today's rule, so no existing path changes;
3. otherwise the part's reference prefix (decision 2), which must be free in its container.

A second unnamed part with the same prefix in one container raises `DslError` at its call: `module buck:
the path buck/C is taken by an unnamed part; give this part name=...`. A counter (`C#2`) is not used,
because it would make a path depend on the order of the statements. The first part keeps its key `C`, so
adding a named second part changes no existing path.

```python
# Today (0.6.0)
c1 = Part("C1", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="10uF")
r3 = Part("R3", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="4k7")
design.add(c1, r3)

# Proposed
buck = Module("buck")
design.add(buck)
u = buck.part(device="Example:BUCK_6V_2A")  # path buck/U, ref U1
c_in = buck.part(name="c_in", device="Fenolite:C_0805", value=farad("10u"))  # buck/c_in, C1
c_out = buck.part(name="c_out", device="Fenolite:C_0805", value=farad("22u"))  # buck/c_out, C2
r5 = design.part("R5", device="Fenolite:R_0603", value=ohm("4k7"))  # explicit, path R5
x = design.part(lib_id="Device:Crystal", footprint="Crystal:HC49", prefix="Y")  # path Y, ref Y1
```

### 2. Reference prefixes

The prefix comes from, in order: `prefix=` (matching `[A-Z][A-Z_]*`), the device's `ref_prefix` (c0248),
or the `reference` of a `Fenolite:` catalog symbol. A part with no ref, no device, a non-catalog symbol
and no `prefix=` raises `DslError` ("give a ref, a prefix or a device"). The prefix is therefore known
when the script runs, and assignment needs no library.

### 3. Assignment

`fenolite.dsl.lock.assign_refs(design, lock, *, moves) -> RefAssignment(refs, lock, changes, issues)` is
pure. `to_model(design, *, refs=None)` takes its `refs`. Without `refs`, it assigns against an empty lock,
so tests and `fenolite.api` work without a file.

1. **Explicit refs** are taken as written. A lock entry of the same path with another ref is replaced
   (`explicit`).
2. **Carried entries.** For each alias new → old of `moves`, a lock entry at `old` moves to `new`
   (`moved`).
3. **Kept entries.** Every remaining lock entry whose path is a part of the design keeps its ref, unless:
   the ref is now an explicit ref of another part, in which case the part is reassigned (`taken`); or the
   part's prefix changed and the ref does not start with it (`prefix-changed`).
4. **Released entries.** Lock entries whose path is no part of the design are dropped (`released`).
5. **New refs.** Parts still without a ref are grouped by prefix. Within a prefix they are taken in
   **natural path order**, and each gets the lowest `n ≥ 1` such that `<prefix><n>` is not used by an
   explicit ref or a kept ref (`assigned`).

**Natural path order.** Split the path into maximal runs of digits and non-digits. Compare the runs in
turn: two digit runs by integer value, then by length; two non-digit runs by code point; a digit run sorts
before a non-digit run. So `ch2/R` comes before `ch10/R`. The order does not depend on statement order, on
`--seed` or on `PYTHONHASHSEED`.

- *Lowest free number vs. "highest + 1".* Lowest free fills gaps, as manual annotation usually does, and
  needs no counter in the lock. A released number can come back in a later build. The warning
  `lock.ref-released` names it, and `--frozen` refuses it (open question 1).
- *Why explicit refs are recorded too.* The lock is the whole ref table. A part whose explicit ref is later
  removed from the script keeps its ref through the lock, instead of being renumbered.

### 4. The lock file

- **Location.** `<script stem>.lock` beside the design script (`design.py` → `design.lock`), or
  `--lock FILE`. One folder may hold several scripts (`examples/roles/*/good.py` and `bad.py`), so the
  research's single `fenolite.lock` per folder would collide.
- **Schema** `fenolite.lock.v0`, canonical TOML:

```toml
# Design lock written by fenolite build. Review changes in git; hand edits are honoured.
schema = "fenolite.lock.v0"
design = "sensor"

[refs]
"R5" = "R5"
"Y" = "Y1"
"buck/U" = "U1"
"buck/c_in" = "C1"
"buck/c_out" = "C2"

[picks]                 # c0254: one table per component path; refused while c0254 is not merged
[pins]                  # c0257: one table per choice key; refused while c0257 is not merged
```

- **Canonical writing.** The header comment, then `schema` and `design`, then the sections in the order
  `refs`, `picks`, `pins`, leaving out empty sections. Keys are TOML basic strings sorted by code point.
  LF line ends, one final newline, no date and no absolute path. The same content always gives the same
  bytes.
- **Reading** uses `tomllib`.
  - An unknown top-level key, a value of the wrong type, a ref that is not a valid name, or two paths
    with one ref gives `FormatError` (`FEN-3004`), naming the file and the key.
  - A schema version higher than v0, or a non-empty `picks` or `pins` before c0254 or c0257 defines it,
    gives `FEN-3002`.
  - A `design` that differs from the script's design name gives `lock.design-renamed` (info), and the
    lock is rewritten with the new name.
- **Sections are generic.** The lock machinery (read, compare, carry by alias, release, write, freeze)
  works on every section through a small protocol `LockSection(name, resolve)`. c0254 and c0257 register
  their `resolve` and drop the refusal. Here `refs` is the only section with content.
- **Hand edits are honoured.** Editing `"buck/c_out" = "C7"` renumbers that part on the next build, if
  `C7` is free. Deleting the file renumbers everything from scratch.

### 5. Writing through plan and confirm

- `cmd_build` reads the lock (when the file exists), passes it to `assign_refs`, and plans a write of kind
  `lock` at the lock path when the canonical text of the new lock differs from the file's bytes. The plan
  then holds a path outside `--out`, as `sync --to-source` does for `placements.toml`. The receipt lists
  it with its SHA-256.
- **When a lock exists at all.** Only for a design with at least one part without an explicit ref, or one
  that already has a lock file (or later, a pick or pin choice). A design with only explicit refs and no
  lock plans no lock, so every existing example builds exactly as before.
- **"Reproducible builds"** is amended: the build may change the script folder only by writing the lock,
  and a second build of an unchanged script leaves the folder unchanged, the lock included.
- An error finding plans no write, the lock included ("Error findings plan no write").
- The Altium target uses the same lock.

### 6. `design.moved()` and the lock

- The aliases of `dsl.moves()` (new → old, module aliases expanded) carry lock entries of every section
  whose key is a component path or starts with one. The entry is rewritten under the new path, with the
  issue `lock.ref-moved` (info).
- Without an alias, a renamed path loses its entry (`lock.ref-released`, warning) and the part gets a new
  ref. Because numbers are lowest-free, the new ref is often the old one, but nothing promises it.
- The layout follows the alias as today. A changed ref alone never loses layout, because footprints are
  matched by uuid and path (`layout-lens`, "Footprint matching").

### 7. `--frozen`

- `fenolite build ... --frozen` computes the assignment and compares the content of the new lock with the
  lock read (a missing file counts as an empty lock). Any change of entries in any section — assigned,
  released, moved, explicit, taken, prefix-changed, design renamed — refuses the build.
  - It exits 7 with `FEN-7004` ("the design lock would change under --frozen; nothing was written"; hint
    "build without --frozen, review result.lock.changes, commit the lock, then build frozen"),
    `retryable` false.
  - The envelope's `issues` hold one `lock.changed` (error) per change, naming the section, key, before,
    after and reason ("Refusals carry their issues").
- This holds with `--dry-run` too: a frozen build never writes the lock, and never plans one.
- A difference of formatting only (a hand-formatted but equivalent file) is not a change under
  `--frozen`, and a frozen build does not rewrite it.
- *Why exit 7.* The release asks that a reviewed identity never be lost silently. The build refuses to
  change it, just as `FEN-7001` refuses a lossy write. Exit 5 would suggest findings to fix in the
  design, while the fix here is to review and commit the lock.

### 8. Result and codes

`result.lock` (a key added under "Build command"):
`{"file": "design.lock", "exists": bool, "written": bool, "frozen": bool, "changes": [{"section", "key",
"before", "after", "reason"}]}`, sorted by section, then by key. `null` when the design needs no lock.

| code | severity / exit | when |
|---|---|---|
| `lock.ref-released` | warning | a lock entry's path is no longer a part, and no alias carries it |
| `lock.ref-taken` | warning | a locked ref is now another part's explicit ref; the part is renumbered |
| `lock.ref-moved` | info | an alias carried an entry to a new path |
| `lock.ref-explicit` | info | an explicit ref replaced a different locked ref of its path |
| `lock.ref-prefix-changed` | info | a part's prefix changed and its locked ref was replaced |
| `lock.design-renamed` | info | the lock names another design |
| `lock.changed` | error | under `--frozen` only: one per change of the lock, with its reason |
| `FEN-7004` | exit 7 | `--frozen` and the lock would change |
| `FEN-3004` | exit 3 | malformed lock (existing code) |
| `FEN-3002` | exit 3 | newer lock schema, or a reserved section with content (existing code) |

New refs (`assigned`) are listed in `result.lock.changes` only, not as issues, so that a first build of
a large design is not flooded with info lines.

## Risks / Trade-offs

- **A file beside the script written by `build`.** This is new for `build`. It is mitigated by the plan
  (the lock is listed and confirmed like every file), the receipt, and the rule that no lock appears for
  designs that do not need one.
- **Released numbers can be reused.** A BOM from an older revision may name the same `R5` for another
  part. `lock.ref-released` warns, and `--frozen` on releases prevents it.
- **Path keys from prefixes** make a part's path depend on whether it was named. Renaming it later needs
  `design.moved()`, as any path change does today.
- **Concurrent edits of the lock in git** merge like any sorted key-value file. A conflict that leaves
  two paths with one ref is refused with `FEN-3004`, and the message names both.

## Open questions

1. *Lowest free number or never reuse (a `[next]` counter per prefix)?* Recommended: lowest free, with
   the warning, and `--frozen` for releases.
2. *Should explicit refs be recorded in the lock?* Recommended: yes (decision 3), so that the lock is the
   full ref table and removing a hand ref does not renumber.
3. *File name: `<stem>.lock` or a single `fenolite.lock` per folder?* Recommended: `<stem>.lock`, because
   folders hold several scripts. `--lock FILE` covers other layouts.
4. *Should `fenolite check` also have `--frozen`?* Recommended: no. `build --frozen --dry-run` is the CI
   gate, and `check` reads projects that may have no script.

## Relation to the batch

- **c0248** (devices): `ref_prefix` and `design.part`. c0248 keeps the ref required; this change lifts
  that.
- **c0250** (manual edits): the three-way merge keys on the same paths. A ref edited in KiCad may be
  proposed into `[refs]` by `sync --to-source`; that is c0250's decision.
- **c0251** (blocks): `b.part()` without a ref takes a path under the block. A per-block numbering
  scheme, if wanted, is a policy on top of `assign_refs`.
- **c0254** (picking): fills `[picks]` (device id, query, catalog version, digest) and registers its
  `LockSection`. `fenolite pick --update PATH` writes through the same plan.
- **c0257** (pin assignment): fills `[pins]`.
- **c0256** (testing): `fenolite.testing.load` uses `to_model(..., refs=)` with the lock beside the script,
  so tests see the same refs as builds.
