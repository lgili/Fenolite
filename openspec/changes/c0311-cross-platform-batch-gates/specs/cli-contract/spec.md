## ADDED Requirements

### Requirement: Library output folders are relative on the native platform

Library generation SHALL reject an output folder with a native path anchor, including a rooted path without a drive on Windows, using the existing usage error before planning writes.

#### Scenario: A rooted folder on Windows
- **WHEN** library generation receives a rooted output folder without a drive
- **THEN** it returns exit 2 with FEN-2001 and plans no write

### Requirement: Library Git checkouts have portable newline settings

Git checkouts used by library get and replay SHALL use explicit autocrlf-disabled and LF-default settings so global user Git settings do not alter the fetched payload. Upstream attributes remain effective.

#### Scenario: The caller enables automatic newline conversion
- **WHEN** a pinned authored library or upstream is fetched with global autocrlf enabled
- **THEN** its payload and replay outputs retain the expected byte digests
