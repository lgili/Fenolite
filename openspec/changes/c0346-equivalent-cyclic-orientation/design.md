# Design
field_differences gains an optional keyword-only orientation_paths collection,
default empty. Only callers comparing L7 Text and FootprintField pass rotation.
Use existing norm.angles_equal only when both leaves have exact type int;
boolean/None/missing presence goes through the existing exact leaf comparison.
Other integer leaves retain existing length semantics. No model/codec/JSON value
or presence changes. In particular do not normalize sweeps, angle ranges,
geometry keys, pad symmetries or S without a separate concrete requirement.

Before runtime code, authored L7 controls must fail for0/360 and-90/270 on
board/footprint text and footprint fields. Negative90/0,180/0,1microdegree/0,
length tolerance not affecting angles, and positive angular-only tolerance
establish the boundary. Generic sweep0/360 and None/false/zero stay distinct.
Canonical serialization/input values are untouched even when physical orientation
compares equal. Then replay exact Tiny inputs to prove the29 false differences
vanish while unrelated graphics/pixel failures remain visible.
