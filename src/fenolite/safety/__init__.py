# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""File safety around the user's own project files (capability file-safety; user guide
``docs/file-safety.md``): the files of a project, a copy that no save interrupted, the lock files that a CAD
tool leaves beside an open file, the files a sync client keeps only online, and the paths a project's
documents hold."""

from fenolite.safety.files import project_files, read_stable
from fenolite.safety.placeholders import is_online_only, online_only
from fenolite.safety.sessions import lock_files, open_sessions

__all__ = ["is_online_only", "lock_files", "online_only", "open_sessions", "project_files", "read_stable"]
