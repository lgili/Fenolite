## ADDED Requirements

### Requirement: Generation-safe scene refinement

A live document SHALL assign a new generation when rebuilding starts. A background refinement SHALL retain the generation of its originating rebuild. Publishing a scene SHALL compare the expected generation and replace scene bytes/version under the same lock; a stale worker SHALL NOT change scene, error or building state.

#### Scenario: A refinement starts after a new rebuild

- **GIVEN** an old scene whose refinement worker is delayed before running
- **WHEN** a new rebuild is published and the old worker runs
- **THEN** the new scene remains published

#### Scenario: A refinement pauses before publication

- **GIVEN** a refinement paused during serialization
- **WHEN** a newer rebuild publishes and the old refinement resumes
- **THEN** generation comparison and publication are atomic and the newer bytes remain

### Requirement: Context-aware viewer shortcuts

Viewer shortcuts SHALL NOT run while an input, select, textarea or editable descendant has focus, during composition, after default prevention, or with Ctrl, Meta or Alt pressed. Existing plain and Shift shortcuts SHALL continue to work outside those contexts.

#### Scenario: Selecting a highlight mode

- **WHEN** M is pressed with the highlight select focused
- **THEN** the viewer does not enter Measure, and an ordinary M outside form controls still toggles Measure

### Requirement: Review in narrow windows

At viewport widths of 760 CSS pixels or below the viewer SHALL offer a labelled, keyboard-operable sidebar toggle, collapse the sidebar initially, and adapt the toolbar so the canvas retains the viewport width. The open sidebar SHALL fit the viewport and remain dismissible. Above the breakpoint the existing desktop layout SHALL remain.

#### Scenario: A 390-pixel window

- **WHEN** the viewer opens at 390 CSS pixels and the sidebar is toggled open and closed
- **THEN** the canvas uses the full available width, controls remain reachable, and the toggle exposes its expanded state

#### Scenario: Desktop remains unchanged

- **WHEN** the viewer opens at 1100 CSS pixels
- **THEN** the sidebar is 260 pixels wide and the narrow-screen toggle is hidden

#### Scenario: Sidebar dismissal does not require a CAD scene

- **GIVEN** a narrow window with the sidebar open and focus outside a form field
- **WHEN** Escape is pressed while a table document is open or no scene is loaded
- **THEN** the sidebar closes and focus returns to its toggle
