# LibrePCB library elements

This page records the public facts used by the independent library reader (c0266). No LibrePCB
parser, grammar implementation, generator or migration code was read. The sources were read on
2026-11-01. The reader is a conservative subset, not a claim to implement every LibrePCB version.

| fact | source | label | hypothesis |
|---|---|---|---|
| Libraries use human-readable S-expressions. Each element is identified by a UUID, which is also its directory name. | S-1090, S-1091 | INFERRED | H-G-LIBREPCB-SEED |
| A library root has `.librepcb-lib` and `library.lp`; optional folders are `sym`, `pkg`, `cmp`, `dev` (and categories). Element files are `symbol.lp`, `package.lp`, `component.lp`, `device.lp`; their markers are `.librepcb-sym`, `.librepcb-pkg`, `.librepcb-cmp`, `.librepcb-dev`. | S-1091 | INFERRED | H-G-LIBREPCB-SEED |
| A marker contains a format version, separate from the element's own version. A newer format must not silently be treated as an older one. The documented example is `0.1`. | S-1092 | INFERRED | H-G-LIBREPCB-SEED |
| Components describe signals and symbol gates; devices connect components to packages; packages may have several footprint variants, with the first the default. UUID references can cross library boundaries. | S-1091, S-1093 | INFERRED | H-G-LIBREPCB-SEED |
| The default name is the English name; localized names are optional. | S-1091 | INFERRED | H-G-LIBREPCB-SEED |
| A symbol has `pin` UUIDs, `name`, `position`, `rotation`, `length`; polygon `vertex` nodes have `position` and `angle`. Standard texts have `layer`, `value`, `align`, `height`, `position`, `rotation`. These field names are observable in the symbol example explicitly linked by the official format page. | S-1090, S-1094 | INFERRED | H-G-LIBREPCB-SEED |
| Library drawing dimensions are expressed in mm; symbol grids and recommended lengths are specified in mm. Package drawings use top view, centred on the body unless the datasheet specifies otherwise. | S-1093, S-1095 | INFERRED | H-G-LIBREPCB-SEED |
| Official libraries are offered under CC0-1.0. The pinned library's full legal code normalizes (lowercase, whitespace collapsed) to SHA-256 `0dd25be0803b1e2764b0323560013cdd5ad9ca92ba4780bd7db0cbe6ce821dd8`. A licence label alone is not this proof. | S-1096, S-1097 | INFERRED | H-G-LIBREPCB-SEED |

The optional library metadata `url` used for source registration is also an explicitly INFERRED
interpretation, not a schema guarantee.

The public pages above do not publish a complete grammar for package, component and device fields,
string escapes, axis signs or rotation direction. Those are **UNKNOWN** as independently verified
format facts. The following explicitly **INFERRED** reader interpretations are isolated and tested
with authored inputs; all resulting records remain `UNVERIFIED`. A successful parse is not evidence
that a live upstream library converts correctly. An external library review and oracle remain needed.

| fact | source | label | hypothesis |
|---|---|---|---|
| Lists have a head atom and positional atoms/child lists. Whitespace separates tokens; double quoted strings support `\\`, `\"`, `\n`, `\r`, `\t`; other escapes and comments are refused. Nesting, bytes and token counts are bounded. | S-1090, S-1094; conservative Fenolite subset | INFERRED | H-G-LIBREPCB-SEED |
| Length tokens are decimal mm, converted exactly to nm. Angle tokens are decimal degrees, converted exactly to microdegrees. Positive X/Y and counterclockwise angles are kept in model coordinates. Nonintegral nm/microdegrees are refused, never rounded. | S-1093, S-1095; unit and axis interpretation pending upstream oracle | INFERRED | H-G-LIBREPCB-SEED |
| Package `pad` maps UUID to name. Each `footprint` has `pad` nodes with `package_pad`, `side`, `shape`, `position`, `rotation`, `size` and optional round `hole` with `diameter`. Only top-side rectangular or round pads, straight polygons and circles are supported. | S-1091, S-1093; relationship interpretation, field spellings not independently documented | INFERRED | H-G-LIBREPCB-SEED |
| Component `signal` nodes have names and roles. A `variant` contains `gate` nodes with `symbol` references and `pin` nodes mapping symbol pin UUIDs to `signal` UUIDs. The first variant is used, one model unit per gate. | S-1091; relationship interpretation, field spellings not independently documented | INFERRED | H-G-LIBREPCB-SEED |
| A device's `component`, `package` and `pad`/`signal` references join those elements; `part` carries an MPN and `manufacturer`. Missing/unsupported dependencies skip the dependent element. | S-1091; relationship interpretation, field spellings not independently documented | INFERRED | H-G-LIBREPCB-SEED |

The role interpretation maps `input` → `input`, `output` → `output`, `inout` → `bidirectional`,
`passive` → `passive`, `power` → `power_in`, `opendrain` → `open_collector`; every unknown role →
`unspecified`. These spellings and mappings are **INFERRED**, not an electrical guarantee.

Only marker format `0.1`, the version explicitly illustrated by the public documentation, is currently
accepted. Other versions, custom pad polygons, curved polygon segments, unsupported drawing/pad
features and missing cross-library dependencies produce `library.seed-skipped` with the UUID and
reason. No board or schematic is read. Nothing is copied from the public symbol example into the
fixtures. The seed command carries the full local licence text into the external data repository; the
Fenolite repository keeps only authored fixtures. Positive unit tests inject the hash of an original
licence placeholder, and an explicit negative test proves the unchanged production gate rejects that
placeholder. S-1097 records the public full-text hash; no copy of that legal text is vendored.
