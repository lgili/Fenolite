# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The one folder in which Fenolite keeps external tools the user asked it to fetch (capability routing,
"Tools folder"; change c0078).

The folder is a cache: what is in it can be fetched again. This module names it and creates nothing;
``fenolite fetch NAME --confirm`` is the only writer. The environment is read at each call.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TOOLS_ENV = "FENOLITE_TOOLS_DIR"
"""The variable that names the tools folder; its value is an absolute path."""


def tools_dir() -> Path:
    """The tools folder: ``FENOLITE_TOOLS_DIR``, else ``$XDG_CACHE_HOME/fenolite/tools``, else the user
    cache folder of the platform. A relative ``FENOLITE_TOOLS_DIR`` raises ``ValueError``."""
    explicit = os.environ.get(TOOLS_ENV, "")
    if explicit:
        folder = Path(explicit).expanduser()
        if not folder.is_absolute():
            raise ValueError(f"{TOOLS_ENV} must be an absolute path, not {explicit!r}")
        return folder
    cache = os.environ.get("XDG_CACHE_HOME", "")
    if cache:
        return Path(cache) / "fenolite" / "tools"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "fenolite" / "tools"
    local = os.environ.get("LOCALAPPDATA", "")
    if sys.platform == "win32" and local:
        return Path(local) / "fenolite" / "tools"
    return Path.home() / ".cache" / "fenolite" / "tools"


def tool_path(name: str, file: str) -> Path:
    """Where the file ``file`` of the tool ``name`` is kept: ``tools_dir() / name / file``."""
    return tools_dir() / name / file


__all__ = ["TOOLS_ENV", "tool_path", "tools_dir"]
