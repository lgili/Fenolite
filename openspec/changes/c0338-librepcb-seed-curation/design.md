# Design
Use the byte-attested public subset and c0335 normalization output as immutable
raw input. A deterministic external recipe copies only two footprints, resistor
symbol and resistor device. Assert exactly two pin lengths2,000,000nm, then
replace those lengths with2,032,000nm (8×254,000nm), preserving every other record
field. Update the existing dated modification_notice and NOTICE, plus conversion
outputs_tree for changed record bytes. Record source/output file hashes and the
explicit semantic delta externally. No extra provenance keys are invented.

Run library check on all four resulting records without skips/waivers; confirm
review sheets only after exit0 and zero ERROR, preserving all four WARN about
the preferred100mil grid. The maintainer explicitly retained80mil artwork rather
than enlarging it merely to suppress warnings; do not claim zero findings. Build the same two-resistor circuit and
export native KiCad netlists before and after; partitions must equal the three
expected nets and each other. Repeat recipe must reproduce all payload hashes.
No human review is inferred. The raw source/output/findings remain available.
