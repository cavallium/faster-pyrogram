#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

import logging
import os
import sqlite3
from pathlib import Path

from .sqlite_storage import SQLiteStorage

log = logging.getLogger(__name__)

USERNAMES_SCHEMA = """
CREATE TABLE usernames
(
    id       INTEGER,
    username TEXT,
    FOREIGN KEY (id) REFERENCES peers(id)
);

CREATE INDEX idx_usernames_username ON usernames (username);
"""

UPDATE_STATE_SCHEMA = """
CREATE TABLE update_state
(
    id   INTEGER PRIMARY KEY,
    pts  INTEGER,
    qts  INTEGER,
    date INTEGER,
    seq  INTEGER
);
"""


class FileStorage(SQLiteStorage):
    FILE_EXTENSION = ".session"

    def __init__(self, name: str, workdir: Path):
        super().__init__(name)

        self.database = workdir / (self.name + self.FILE_EXTENSION)

    def _update_from_one_impl(self):
        with self.conn:
            self.conn.execute("DELETE FROM peers")

    def _connect_impl(self, path):
        self.conn = sqlite3.connect(str(path), timeout=1, check_same_thread=False)

        with self.conn:
            self.conn.execute("PRAGMA journal_mode=OFF").close()
            self.conn.execute("PRAGMA synchronous=NORMAL").close()
            self.conn.execute("PRAGMA temp_store=0").close()

    async def update(self):
        version = await self.version()

        if version == 1:
            with self.conn:
                await self.conn.execute("DELETE FROM peers")

            version += 1

        if version == 2:
            with self.conn:
                await self.conn.execute("ALTER TABLE sessions ADD api_id INTEGER")

            version += 1

        if version == 3:
            with self.conn:
                await self.conn.executescript(USERNAMES_SCHEMA)

            version += 1

        if version == 4:
            with self.conn:
                await self.conn.executescript(UPDATE_STATE_SCHEMA)

            version += 1

        if version == 5:
            with self.conn:
                await self.conn.execute("CREATE INDEX idx_usernames_id ON usernames (id);")

            version += 1

        await self.version(version)

    async def open(self):
        path = self.database
        file_exists = path.is_file()

        self.executor.submit(self._connect_impl, path).result()

        if not file_exists:
            await self.create()
        else:
            await self.update()

        with self.conn:
            await self.conn.execute("VACUUM")

    async def delete(self):
        os.remove(self.database)
