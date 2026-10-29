## ADDED Requirements

### Requirement: Current browser navigation owns the view

Every document-open request SHALL have a new navigation generation. Only the current generation SHALL publish a loaded scene, a missing-scene card or a read failure. Selecting A, then B, then A again SHALL not allow the first request for A to replace the final request. Deferred selection actions SHALL verify their navigation is still current before changing selection or fitting the view. New-document loading SHALL identify the requested document while preserving the existing rendering layout.

#### Scenario: Late success, error or missing scene
- **GIVEN** a request for document A is waiting
- **WHEN** B is selected and rendered before A returns a scene, fails or returns no scene
- **THEN** B remains selected and displayed, and no card or error from A covers it

#### Scenario: Repeated selection
- **GIVEN** two requests for A separated by selection of B
- **WHEN** the newest A renders and the first A finishes later
- **THEN** the newest scene of A remains displayed

#### Scenario: Delayed cross-probe is superseded
- **GIVEN** a cross-probe is waiting for a candidate scene
- **WHEN** the user selects another document before it completes
- **THEN** the cross-probe does not change the selected document, its selection or the view

### Requirement: Current scene reads own their cache entry

Each document's asynchronous read or decode SHALL retain a read generation. An older completion SHALL not overwrite a newer cached scene or remove a newer raw source. Invalidation SHALL advance the generation before a refresh starts. A later selection SHALL use the newer cached scene.

#### Scenario: Cache responses arrive out of order
- **GIVEN** old and new scene requests for the same document
- **WHEN** the new request completes first and the old request completes later
- **THEN** the cache retains the new scene and a subsequent selection displays it

### Requirement: Version polling belongs to its navigation

Version polling SHALL capture the selected document and navigation before requesting. Only the current poll request for that document and current navigation SHALL change status or version or start a refresh. Refresh completion SHALL check navigation again. Stale failed requests SHALL not replace the status of the current document.

The first available version response SHALL revalidate the displayed scene before adopting that version, including when a cached document is selected again. A response reporting that the server is still building SHALL NOT adopt an unread version. Polling SHALL wait while the current scene is loading, so a slow read is not repeatedly superseded by automatic refreshes. A failed scene read SHALL NOT adopt the requested version.

#### Scenario: A poll completes after document selection changes
- **GIVEN** a version request for A is waiting
- **WHEN** B is selected before A's response or failure arrives
- **THEN** B's version, status and scene remain untouched by that response

#### Scenario: Poll replies arrive out of order
- **GIVEN** two version requests for the current document
- **WHEN** the newer request completes first
- **THEN** the older response does not roll back version or status or trigger another refresh

#### Scenario: Navigation changes during refresh
- **GIVEN** a current poll starts refreshing A
- **WHEN** B is selected before that scene read completes
- **THEN** the refresh does not change B's scene, status, selection or version

#### Scenario: Returning to an older cached scene
- **GIVEN** A's old scene is cached and its server version changes while B is selected
- **WHEN** A is selected again and its first version response arrives
- **THEN** the viewer reloads A before adopting the response version

#### Scenario: Refinement finishes before the first poll
- **GIVEN** the displayed scene was read before the server finished its refinement
- **WHEN** the first version response reports the refined scene's version
- **THEN** the viewer reloads and displays that scene

#### Scenario: A slow scene read spans polling intervals
- **GIVEN** the current navigation is loading a scene
- **WHEN** another poll is requested before the scene completes
- **THEN** it does not issue another version request or start a competing scene read
