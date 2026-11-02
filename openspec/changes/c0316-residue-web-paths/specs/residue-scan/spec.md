## ADDED Requirements

### Requirement: HTTP path distinction
The scanner MUST distinguish a parsed HTTP(S) URL path from an absolute user path.
Only an `abs-user-path` match wholly inside that URL path SHALL be exempt. File
URIs, query/fragment values and paths outside URLs MUST retain their checks.

#### Scenario: Public reference and local path
- **GIVEN** an HTTP(S) reference whose path resembles a user directory
- **WHEN** the reference and a separate local path are scanned
- **THEN** the URL path alone is exempt and the local path is reported

#### Scenario: Other URI components retain checks
- **WHEN** a file URI or an HTTP query/fragment contains a user path
- **THEN** the existing absolute-user-path finding is reported

### Requirement: URL checks remain scoped
The scanner MUST continue private-token, known-blob and other structural checks
on URL bytes. Its URL-path distinction SHALL apply across supported decodings,
archive members and historical blob labels without broadening file waivers.

#### Scenario: Token in an HTTPS path
- **GIVEN** a configured invented private token in a URL path
- **WHEN** that content is scanned
- **THEN** the private-token finding is retained

#### Scenario: Encoded archive member
- **WHEN** an archive member contains an encoded reference and a local path
- **THEN** only the local path produces the absolute-user-path finding
