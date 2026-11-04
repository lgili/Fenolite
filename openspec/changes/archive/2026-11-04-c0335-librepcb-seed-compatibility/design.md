# Design

Use a metadata-only default-name reader: exactly one unlocalized name and
well-formed unique locale alternatives; all other duplicate field guards stay.
Accept scalar drill only when exactly zero and no hole representation coexists.
An absent package_pad uses the footprint pad UUID only if it names a declared
package pad. An explicit reference remains authoritative. Preserve the existing
hole path; do not invent nonzero legacy drill support or round sub-nm data.

Record observed spellings from the immutable public CC0 component/package as
INFERRED format facts (S-1200/S-1201). Unit inputs are authored modifications of
Fenolite's existing authored fixture, never copied from upstream. A separate
five-element public dependency view, with every blob attested against Git,
produces the review packet outside core through dry-run/review/exact plan confirm.
All seeded records stay UNVERIFIED; generating a packet is not human approval.

Preserve a valid declared component reference prefix in both records; U is only
an absent-field default. Keep DevicePin.function strict. Normalize only ASCII
digit-only internal function names to Pin_<original>; symbol pin names/numbers,
source UUIDs and signal-to-pin-to-pad associations remain unchanged. Check all
candidate function identifiers for collisions, including already valid Pin_1,
before generating a device. Other invalid names stay refused. Emit a localized
warning library.seed-function-normalized with a deterministic JSON mapping of
signal UUID/original/normalized. Preserve that mapping in existing validated
modification_notice text and NOTICE, alongside immutable upstream commit and
provenance output hashes; add no arbitrary schema key or model field.

Author controls cover numeric R functions, legal-name collision, byte-stable
replay, and pin/pad partition equivalence. The public resistor symbol's 2 mm pin
length stays untouched and its off-10mil finding remains visible; this change
must not make failed geometry clean or claim the complete Base is supported.

Only exact cardinal symbol pin rotations are representable. Canonicalize signed
or full-turn cardinal angles modulo360 in integer microdegrees, preserving
orientation exactly; refuse 45deg and -90.0001deg without rounding. Emit
library.seed-angle-normalized with source symbol UUID/SHA, pin UUID, original
and normalized integer angle, and preserve that warning in the existing symbol
provenance modification_notice and NOTICE. No model fields change.
