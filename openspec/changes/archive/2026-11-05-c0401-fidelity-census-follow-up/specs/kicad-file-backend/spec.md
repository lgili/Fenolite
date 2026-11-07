## MODIFIED Requirements

### Requirement: Explicit physical root edges with a logical outline

The writer SHALL accept Board.outline with explicit root edge lines, arcs or unfilled rectangles only when complete deterministic reconstruction from those root edges and the existing footprint edges exactly matches the logical outline's complete edge-text multiset. It SHALL then emit only the explicit root graphics and existing footprint graphics, preserving their geometry and multiplicity without emitting synthetic outline copies. An incomplete, ambiguous, branching or inconsistent reconstruction SHALL be refused. The importer SHALL keep a root Edge.Cuts `gr_rect` that owns the outline as an explicit rectangle, so the board keeps one `gr_rect` instead of four `gr_line`s.

#### Scenario: Nanometre joins in a footprint notch

- GIVEN explicit authored root lines/arcs closed by footprint edges whose adjacent endpoints differ by nanometres
- WHEN their complete reconstructed outline exactly matches the logical outline and the board is written for target 9 or 10
- THEN all original root and footprint graphics retain their exact geometry and there are no synthetic root duplicates

#### Scenario: Nearby edges do not prove ownership

- GIVEN an explicit root line one nanometre from an intentionally distinct footprint line
- WHEN the writer considers the complete physical geometry
- THEN it preserves the root line or refuses inconsistent geometry and never erases it through cluster coincidence

#### Scenario: A rectangle outline stays a rectangle

- GIVEN a board whose only Edge.Cuts item is one unfilled `gr_rect`
- WHEN it is imported to Python and built for target 9 or 10
- THEN the built board holds that one `gr_rect` with its corners and width, and no `gr_line` on Edge.Cuts
