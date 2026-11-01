# Library rules: Fenolite conventions

Change c0262. All constants and checks on this page are Fenolite-authored, `INFERRED`.
They do not assert compliance with an industry library standard.

| rule | convention and reason |
|---|---|
| Land tolerance | `T = 50_000 nm` (0.05 mm). Imported pads differing by more than T in position or size warn; generated manufacturer lands must agree exactly. |
| Pin 1 | In the zero-orientation footprint frame (X right, Y down), pad 1 or A1 is above-left of the numbered-pad centroid: both inequalities non-strict, at least one strict. Non-polarized two-terminal parts are exempt. |
| Marker | A silk/fab graphic's bounding-box centre is strictly closer to pad 1 than every other pad. This is a heuristic; unusual connectors may waive it with a reason. |
| Grid | Symbol connection points and lengths use 254_000 nm (10 mil); 2_540_000 nm (100 mil) is the preferred grid. Off the first is an error; off only the second is a warning. |
| Clearance | Copper pads with different numbers must have a positive gap on every common copper layer. Geometry uses integer nanometres. |
| Body/span | Leads outside a body require its maximum width below the minimum span. Lead length uses `2Lmin < span.max − width.min + 2T`. |
| Grid arrays | Rows use `ABCDEFGHJKLMNPRTUVWY`, then AA, AB, etc.; columns start at 1. Depopulated locations are unique grid positions and have no copper pad. |

Public source S-0988 (TI ZXH0080A outline) supports A–J omitting I. As already recorded in
[naming.md](naming.md), the other omitted letters and the multi-letter continuation are Fenolite
conventions (`INFERRED`); this change makes no unsupported JEDEC claim. The checked rules are stated
here from first principles rather than copied from another library's rules.

Review digests exclude top-level evidence and review metadata, normalize generated evidence-only
descriptions, and include referenced records and generated definitions. The accepted HTML contains an
immutable review-content section; live reviewer/date/state is reported by the command. This prevents
accepting the sheet from immediately making that same sheet stale.
