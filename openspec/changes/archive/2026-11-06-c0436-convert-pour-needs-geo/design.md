# Design: c0436

`lower.write_design` keeps its contract: `pour=None` falls back to the outline with a warning (the build's
default, capability altium-build), an explicit mode raises `BackendUnavailable` without the extra. The
KiCad-to-Altium direction passes `options.pour or "computed"`, so a conversion always asks for a mode. This
leaves the build alone and keeps one place that decides the fallback.

The CLI's `BackendUnavailable` handler already maps to `FEN-6001`; its message now says whether the mode
was the default or explicit, and the hint gives both ways out. No issue code is added: the refusal is the
existing `FEN-6001`.

A board without polygons pours nothing, and the pour engine is not loaded, so it converts without the
extra as before.
