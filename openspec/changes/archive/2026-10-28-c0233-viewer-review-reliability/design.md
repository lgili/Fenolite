## Decisions

1. Increment a per-document generation under the live server lock when a rebuild starts. Capture that generation before launching refinement. Serialize outside the lock, then compare and publish under the same lock; stale success/error/finally paths must not overwrite newer state.
2. Test both a refinement whose worker starts late and a refinement whose serialization overlaps a newer rebuild, with deterministic synchronization rather than timing sleeps.
3. Ignore keyboard events originating in inputs, selects, textareas or editable descendants, and events with Ctrl, Meta or Alt, composition or an already-prevented default. Preserve Shift+M/S/C and ordinary shortcuts.
4. At 760 CSS pixels and below, collapse the sidebar by default and expose a labelled Projects toggle. Use a bounded overlay for the opened sidebar, with an adaptable wrapping toolbar. Keep the original desktop geometry above the breakpoint and leave screenshot references untouched.
5. Use the actual browser harness for focus and viewport behavior, and inspect a narrow screenshot. No broad accessibility redesign or editing controls are included.
