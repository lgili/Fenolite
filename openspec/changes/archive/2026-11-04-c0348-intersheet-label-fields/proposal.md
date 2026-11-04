# Typed global-label inter-sheet reference fields

Three declared native9 corpus inputs refuse extraction because eight global labels
carry the fixed Intersheetrefs/${INTERSHEET_REFS} property with visible poses. The
owning flat_hierarchy project explicitly enables reference display. Dropping the
field or rendering its placeholder literally would change the drawing.

Append one optional typed field pose to DrawnLabel and carry it through the drawn
codec/extract/lower/native write paths. Resolve effective viewer text from the
owning project's settings and complete sheet instances, with explicit instance
scenes where repeated sheets have different references. Keep default scenes and
native output bytes unchanged when this field/context is absent. Preserve strict
refusals for unrelated/duplicate properties and unsupported context.

Native9.0.9/10.0.6 authored SVG measurements already establish all five requested
project settings, repeated-instance behavior and project-show overriding stored
field hide. No runtime code is authorized until coordinator design review.
