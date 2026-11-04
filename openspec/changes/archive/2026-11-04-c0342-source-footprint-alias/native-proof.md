# Source-bound footprint alias proof

Public native controls remain external; no third-party CAD payload is retained
in core. Their immutable declared source is the official KiCad demo tree at
revision97acc80c223d75520c03fc44cab63cd9a3202c42 (existing corpus inputs),
verified against every input-verification SHA before each fresh import.
The source locations are:

- https://gitlab.com/kicad/code/kicad/-/tree/97acc80c223d75520c03fc44cab63cd9a3202c42/demos/interf_u
- https://gitlab.com/kicad/code/kicad/-/tree/97acc80c223d75520c03fc44cab63cd9a3202c42/demos/complex_hierarchy

Original source aliases are bound by exact native sheet/symbol/use/ref identity.
Local geometry copies retain the exact derived instance variants, including
field poses, source ordering and edits. Logical aliases may share a name when
explicit footprint_definition selects distinct physical variants; a conflict on
one exact lookup still refuses. No L3 comparator/namespace policy changed.

| Actual control | Native10.0.6 result | Fresh strict proof |
|---|---|---|
| interf_u |24components/173nets, no netlist differences including Footprint metadata and pin types | levels1–8+S all equal; no differences/acceptances |
| complex_hierarchy |68components/52nets, no netlist differences including Footprint metadata and pin types | levels1–6/S/8 equal; the existing L7 opaque teardrop165→0 remains visible under c0340/regeneration |

No source or proof was made passing with a filter, accepted difference, altered
mask, arbitrary Footprint text override or pose normalization. Native exports
run on private copies; the public input hashes remain unchanged. Authored Mini
fixtures exercise the same logic on9/10, preserve physical UUID/pad identities,
prove edited variants and reject real lookup/context/basename conflicts before
staging. Default import preserves its confirmation/plan/no-write contract.

The independent c0326 planted Other versus Mini_R physical contradiction now
fails earlier with located FEN-3004 and zero plans/targets; the maintainer
explicitly chose refusal over inventing an inconsistent text/physical binding.
Nonalias import/build byte maps on9/10 are identical to clean bffa03fd code when
using the same c0344-refreshed authored project fixture. Old aggregate pins were
reanchored separately with that causal file-by-file proof, not silently relaxed.

Proof commands: the importer package, library derive controls, import CLI,
agent-page budgets and native alias oracle run together:366 passed137.06s.
Root75plans, serialized fast and exact-source CI remain independent open gates.
