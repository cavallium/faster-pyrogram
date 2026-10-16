#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram, licensed under the LGPL v3 or later.

from __future__ import annotations as _annotations

from pathlib import Path

from .sqlite_storage import SQLiteStorage


class MemoryStorage(SQLiteStorage):
    """A session kept in memory, optionally initialized from a session string."""

    def __init__(self, name: str, session_string: str | None = None):
        super().__init__(name, workdir=Path(), session_string=session_string, in_memory=True)
