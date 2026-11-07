# Design

c0363 retains a TAB in a KiCad footprint property through the native field of its footprint, after it
checks that field's measured pose and font profile. Another backend holds no such native field, so the
emitter cannot keep the value, and `Part.properties` stays printable (c0363). Until a backend proves a
native carrier, the emitter counts each such property under the unexpressed kind `property-tab`
(example `REF:Name`) and goes on; the property is not written, and the rest of the import proceeds. The
KiCad path, its pose checks and its refusals of other controls are unchanged.
