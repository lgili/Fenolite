# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Negative tests on text: "this value is not in that output".

A path of Windows holds backslashes, and JSON text and ``repr`` write each as two. So ``str(path) not in
json.dumps(reply)`` is true on Windows whatever the reply holds, and the test proves nothing there.
``absent`` looks for every spelling the value can have in the text.
"""

from __future__ import annotations

import json


def spellings(needle: str) -> tuple[str, ...]:
    """``needle`` as it stands, as JSON text writes it and as ``repr`` writes it, without repeats."""
    forms = (
        needle,
        json.dumps(needle)[1:-1],
        json.dumps(needle, ensure_ascii=False)[1:-1],
        repr(needle)[1:-1],
    )
    return tuple(dict.fromkeys(forms))


def absent(needle: str, *texts: str) -> bool:
    """Whether no spelling of ``needle`` occurs in any of ``texts``."""
    return not any(form in text for form in spellings(needle) for text in texts)


__all__ = ["absent", "spellings"]
