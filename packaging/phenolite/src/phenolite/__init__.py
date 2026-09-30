# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Alias of Fenolite. ``pip install phenolite`` installs ``fenolite``; import ``fenolite`` directly."""

from fenolite import *  # noqa: F403  (re-export the public namespace)
from fenolite import __version__

__all__ = ["__version__"]
