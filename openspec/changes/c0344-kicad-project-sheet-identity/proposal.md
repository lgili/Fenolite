# Why
A real KiCad10 GUI save of the populated sensor hierarchy reports AUTO-FIXED
brokenfile and rewrites child instance paths to the unrelated root UUID cached
in the project template. The root schematic UUID remains intact; R2/R3 and
PWR01/PWR02 context references collapse. Native netlists prove this is electrical
identity corruption, not harmless formatting. Do not promote the damaged fixture.

# What Changes
When build emits actual schematic bytes, bind only project sheet-identity caches
to those bytes: root filename/name/UUID and emitted sheet references. Preserve
unrelated project settings and schematic skip/no-emission behavior. Prove root/path
coherence before/after rebuild on9/10, native distinct repeat partition and actual
post-fix GUI save. Explicit GND shape is a separate authored fixture correction.
No model/CLI fields, relaxed comparisons, accepted differences or manual-only
project patch.
