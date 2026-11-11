# Proposal: c0475-altium-carried-body-owners

## Problem
When carried component body graphics (`comp_gfx`) replace a different number of template graphics,
the generated footprint links can refer to the wrong records. Altium reported missing footprints
on a converted project; this ownership defect is a plausible cause, but a native recompile is pending.

The component writer patches the template's owner indexes with one fixed offset
(`drawn.component`: `OWNERINDEX = int(value) + offset`). The template's footprint chain owners
(45 → 44, 46/48 → 45, 47 → 46) are **positions inside the template**, which holds the symbol's own
body records. When the carried body replaces them with more (or fewer) records, every owner after the
body names the record where it would have sat without the carried body.

## Change
`drawn.component` records the live index of every template record it writes (template position →
written index) and resolves each template `OWNERINDEX` through that map instead of adding the fixed
offset; a template owner that was not written raises a `FormatError` instead of silently naming the
wrong record. The carried gfx loop keeps using the component's own index for `@0`.

## Proof
- `tests/unit/backends/altium/test_drawn_altium.py::test_carried_body_owners_shift_the_footprint_chain`
- A local rebuild of the reported project: read back the owner chain of each reported component.
- Compile the regenerated project in Altium and compare its warnings with the original project.
