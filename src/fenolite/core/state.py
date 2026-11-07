# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The state folder: where Fenolite keeps what one call leaves for the next, outside the user's tree.

It holds the staged plans of dry runs (``plans/<id>/``) and the records of unfinished routes
(``jobs/<key>/``); see capability cli-contract, "Staged plans" and "Resumable route jobs". Everything in
it can be deleted at any time.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

STATE_ENV = "FENOLITE_STATE_DIR"
"""An absolute path names the folder; ``off`` turns the state folder off."""
OFF = "off"


_OVERRIDE: ContextVar[Path | None] = ContextVar("fenolite_private_state", default=None)


@contextmanager
def using_state(path: Path) -> Generator[None, None, None]:
    """Isolate in-process test plans without changing process-wide environment variables."""
    token = _OVERRIDE.set(path)
    try:
        yield
    finally:
        _OVERRIDE.reset(token)


def state_dir() -> Path | None:
    """``FENOLITE_STATE_DIR`` when it is an absolute path, ``None`` when it is ``off``, and
    ``~/.cache/fenolite/state`` otherwise (beside the library cache). The folder is not created here."""
    override = _OVERRIDE.get()
    if override is not None:
        return override
    value = os.environ.get(STATE_ENV, "").strip()
    if value.lower() == OFF:
        return None
    if value and Path(value).is_absolute():
        return Path(value)
    return Path.home() / ".cache" / "fenolite" / "state"


__all__ = ["OFF", "STATE_ENV", "state_dir"]
