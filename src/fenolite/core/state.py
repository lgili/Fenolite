# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The state folder: where Fenolite keeps what one call leaves for the next, outside the user's tree.

It holds the staged plans of dry runs (``plans/<id>/``) and the records of unfinished routes
(``jobs/<key>/``); see capability cli-contract, "Staged plans" and "Resumable route jobs". Everything in
it can be deleted at any time.
"""

from __future__ import annotations

import os
from pathlib import Path

STATE_ENV = "FENOLITE_STATE_DIR"
"""An absolute path names the folder; ``off`` turns the state folder off."""
OFF = "off"


def state_dir() -> Path | None:
    """``FENOLITE_STATE_DIR`` when it is an absolute path, ``None`` when it is ``off``, and
    ``~/.cache/fenolite/state`` otherwise (beside the library cache). The folder is not created here."""
    value = os.environ.get(STATE_ENV, "").strip()
    if value.lower() == OFF:
        return None
    if value and Path(value).is_absolute():
        return Path(value)
    return Path.home() / ".cache" / "fenolite" / "state"


__all__ = ["OFF", "STATE_ENV", "state_dir"]
