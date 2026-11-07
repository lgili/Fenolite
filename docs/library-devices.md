# Offline device items and LibrePCB seed

`fenolite get device NS:NAME` vendors a device and its exact symbol/footprint dependencies beside the
design, under `fenolite_library/{devices,symbols,footprints}/NS/NAME/`. Records are TOML data; builds never
import an item as Python, contact a server, or resolve payloads from a cache. The newest cached index is
read only to suggest `fenolite get device NS:NAME --dry-run` for an unknown device namespace.

| item kind | payload | dependencies |
|---|---|---|
| `symbol` | one pins record with `[symbol]` drawing | none |
| `footprint` | one package record | none |
| `device` | one device record with orderable `[[part]]` rows | exact symbol and footprint versions |
| `device` family | one c0263 family record | the items needed by the family |

Each local record's kind, id, version and licence must match `item.json`. The audit also rejects the
reserved `Fenolite:` namespace and local imports that `shippable()` rejects. Authored items use CC0,
the `cc0` family, and `D-NNNN` sources registered in the library's `sources.toml`. Each source table
names its id, title, URL, source licence, retrieval date and use. The published authored namespace is
`FenoliteDevices`; converted items keep their upstream licence and source namespace. The shipped
catalog continues using its own `S-` source register.

Resolution precedence is `design.devices(...)` / authored `devices/`, then vendored items, then the
shipped catalog. An authored override reports `library.overrides-item`; two vendored items with the same
record id report `library.item-conflict` and plan no build output. Definitions the design does not use
do not enter its generated libraries. Adding an unused item leaves all output bytes unchanged.

The build reports `builtin`, `authored` or `library`. `result.library_items` gives kind, id and version
for used library definitions, and a library device row has `item` with that metadata. Library picks
store `catalog = "library:device/NS:NAME@VERSION"`; changing the item version causes a pick re-check even
if its electrical row is unchanged. Only `get` writes `[library.items]` pins: version, release, index
and tree digests. A missing pinned folder gives `FEN-6004` / `library.item-missing`; restore it with
`get --locked design.py --offline --dry-run`. Build does not rewrite item pins or verify release trees;
`get --status` reports local edits.

```sh
fenolite get device FenoliteDevices:Example --from release --dry-run --json
# Review result.licences and result.plan, then use the returned plan_id:
fenolite get device FenoliteDevices:Example --from release --confirm --plan PLAN --json
fenolite build design.py --out out --frozen --dry-run --json
```

The authored [library-devices example](../examples/library-devices/README.md) includes a small local
release, its vendored item closure and a lock. Its tests fetch from that release and build with network
access blocked, comparing the output bytes with the authored records directly. Its licence declarations and fixture review metadata
are authored test inputs, not copies or approvals of upstream legal text. Seed unit positives use a
test-only hash seam with an authored placeholder; production defaults reject that placeholder.

## Seeding an external data repository

```sh
fenolite library seed --from-librepcb ../LibrePCB_Base.lplib \
  --commit FULL_40_HEX_COMMIT --library "LibrePCB Base" \
  --into ../fenolite-library --namespace FenoliteDevices --dry-run --json
# Inspect every item, issue and planned file before confirming the returned plan:
fenolite library seed --from-librepcb ../LibrePCB_Base.lplib \
  --commit FULL_40_HEX_COMMIT --library "LibrePCB Base" \
  --into ../fenolite-library --namespace FenoliteDevices --confirm --plan PLAN --json
```

The full local CC0 1.0 legal text must match the pinned normalized SHA-256; a licence label alone is
refused with `FEN-3004`. If `.git` exists, `HEAD` must equal `--commit`. For an extracted directory the
commit is supplied by the caller, not independently attested by the converter. Source and output folders
must be separate. LibrePCB Base has a documented default public URL; another library must supply a
public HTTPS `url` in `library.lp` (an explicitly inferred metadata field).

A package becomes a footprint item for each footprint; the first takes the package name, later ones
append the footprint name. A component and its gate symbols become one pins item with a unit per gate;
the first component variant is used. A device joins those records and keeps its parts. Every item gets
`item.json`, the full `LICENSE`, a dated `NOTICE` and `PROVENANCE.json` (`origin: seeded`). Each record
keeps the source library, commit and original UUID in `origin`, version `1.0.0`, and `UNVERIFIED`.
The source is registered under a stable `D-` id. Review never erases seeded provenance.

Names replace characters outside `[A-Za-z0-9_.+-]` with `_`; reserved dot path segments and `..` runs
are sanitized too, following the item-id safety rules. A collision appends the first eight UUID
hex digits and reports `library.seed-renamed`. Repeating the same run with the same timestamp produces
the same bytes. A matching existing seeded UUID can be replaced only when it has no review entries.
A reviewed item is refused with `FEN-7001`, including with `--allow-lossy`. All planned files use the
shared transaction; a changed input or target requires a fresh plan (`FEN-4002`). Existing unrelated
files are not deleted; the external audit must still pass before a release.

## Current format limits and external review

The independent reader implements only the bounded `0.1` subset recorded in the
[format facts](formats/librepcb/library.md). Public documentation does not specify the complete
package/component/device field grammar, axis signs or role spellings. These interpretations are
explicitly inferred and tested only on original authored fixtures. Newer versions, unsupported/custom
pads, unrepresentable geometry, sub-nm lengths and missing dependencies report `library.seed-skipped`;
dependent devices are skipped too. Unknown signal roles become `unspecified`. A repeated signal across gates still produces symbol units,
but a device whose resulting map assigns one pad to multiple symbol numbers is skipped because the
record model cannot carry that map. No upstream parser,
generator or migration implementation was read or used. No live-library or external-tool compatibility
has been established by those tests.

CC0 does not establish that an upstream contributor had all necessary rights, or that its pin maps and
dimensions are correct. Keep the attribution and commit, review both the converted data and its history,
check sheets and source documents, and require current digest-bound human reviews before raising
evidence. The external `fenolite-library` repository still needs its `records`, `regenerate`, `versions`,
`origin` and `renders` jobs, CODEOWNERS approval, reviewed initial items and an audited release tag.
This implementation creates neither that release nor its CI result.

See [records](library-records.md), [library repository](library-repo.md),
[local import](library-import.md), [library checks and review](library-rules.md) and
[CLI contract](cli-contract.md#library).
