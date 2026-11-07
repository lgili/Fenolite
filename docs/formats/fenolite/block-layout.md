# Block layout v0

Evidence: `INFERRED`. This is Fenolite's own authored format (c0271), not an imported CAD format.
`reuse.blocklayout` reads TOML with `tomllib` (S-0273) and decimal tokens without creating floats.

The required header, in write order, is `schema = "fenolite.block-layout.v0"`, `block` (record id),
`block_version` (MAJOR.MINOR.PATCH), `parts_digest`, `nets_digest`, `licence`, and `evidence`.
Optional `captured_from` is informative and relative. Unknown keys fail as `FEN-3004`; an unsupported
schema fails as `FEN-3002`. Lengths and angles are strings with units, exact whole nanometres and
microdegrees. The writer uses exact millimetres and degrees, LF and UTF-8.

`[parts."local/path"]` has `at = ["0mm", "2.5mm"]`, `rotation = "90deg"`, `side = "top"`
(or `bottom`) and `footprint` (library id). Paths are relative to the block instance, including nested
parts. The frame has Y down. A bottom block pose mirrors X, then turns and translates the frame.

`[[tracks]]` has `net`, `layer`, `width`, `start`, `end`; `[[arcs]]` adds `mid`.
`[[vias]]` has `net`, `at`, `size`, `drill`, `layers`, optionally `via_type`.
`[[zones]]` has `net`, `layers`, `outline`, optionally `name`, `priority`, and `settings`.
Zone settings and hatch settings use the model field names; lengths, angles and areas have units,
ratios are decimal text, counts are integers, enums are strings. Fills are never stored.
Nondefault via protection is not represented by v0 and capture refuses it as
`blocks.capture-check-failed`, so a round trip never silently removes that manufacturing setting.
All copper tables may carry `pads`, the local `part.pad` contacts their ends occupy. These contacts
validate geometry; they never move it. Local nets are `port:NAME`, `port:NAME.member`, `net:NAME`
(including nested `net:sub/NAME`); `global:NAME` records an escaped script net, `nc` an unconnected pad.
Parts write in local path order and copper in layer, net and geometry order.

Digests use `sha256:` plus 64 lower-case hexadecimal digits over `model.canonical.dumps` UTF-8 bytes.
`parts_digest` hashes the path-sorted list `[local_path, footprint_id, sorted_pad_numbers]`.
`nets_digest` hashes the sorted triples `[local_path, pad_number, local_net]`. They are computed after
selection and footprint resolution: values do not count, the selected case does, and port mappings
use the block port's local name rather than the parent's net name. Pad geometry does not count.

An id or major version mismatch refuses application. A parts mismatch stages the parts; a net mismatch
keeps placement and omits copper. Equal digests allow an older minor/patch version with a notice.
Capture uses the recorded pose's inverse, or an anchor translation, and checks a 1 µm pad-fit round trip.
A shipped `Fenolite:` layout uses Apache-2.0; a project may name its own licence. Evidence remains
`INFERRED` until actual oracle results support a higher claim.


## Persistent copy observations

`fenolite-layout-base.json` is an optional protected output (`fenolite.block-layout-base.v0`), separate
from the reusable asset and from caches. It stores `design`, copper `layers`, resolved `frames`, asset
SHA-256s and owned UUID rows under `copies.<instance>`. A row has local `code` and `out` geometry (or
null for deletion), `source`, local `net` and local `pads`. Geometry has the model's integer fields and
`kind`; identity, net ids, locks and derived fills are excluded. The body SHA-256 covers canonical JSON
without its `sha256` field. The build record also hashes the file. It is not created for designs without
layout copies, and a clone can rebuild from it with no cache. Evidence remains `INFERRED`.

## Declared port boundaries

A block's declared port nets are boundaries of its reusable copper. A group attached to
one block pad on such a net may remain: the containing board completes the connection.
A ground pad, short track and via into a local return area is one case. Ordinary reuse
retains its two-pad island guard. Free ends, insufficient via-layer connections and new
clearance or short findings are still refused. The starter layout proofs exercise both
that positive and an ordinary free-end negative (`tests/unit/blocks/test_starter_layouts.py`).
