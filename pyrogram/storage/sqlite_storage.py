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

import base64
import logging
import sqlite3
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pyrogram import raw

from .. import utils
from .storage import Storage

log = logging.getLogger(__name__)


# language=SQLite
SCHEMA = """
CREATE TABLE sessions
(
    dc_id          INTEGER PRIMARY KEY,
    server_address TEXT,
    port           INTEGER,
    api_id         INTEGER,
    test_mode      INTEGER,
    auth_key       BLOB,
    date           INTEGER NOT NULL,
    user_id        INTEGER,
    is_bot         INTEGER
);

CREATE TABLE peers
(
    id             INTEGER PRIMARY KEY,
    access_hash    INTEGER,
    type           INTEGER NOT NULL,
    phone_number   TEXT,
    last_update_on INTEGER NOT NULL DEFAULT (CAST(STRFTIME('%s', 'now') AS INTEGER))
);

CREATE TABLE usernames
(
    id       INTEGER,
    username TEXT,
    FOREIGN KEY (id) REFERENCES peers(id)
);

CREATE TABLE update_state
(
    id   INTEGER PRIMARY KEY,
    pts  INTEGER,
    qts  INTEGER,
    date INTEGER,
    seq  INTEGER
);

CREATE TABLE version
(
    number INTEGER PRIMARY KEY
);

CREATE INDEX idx_peers_id ON peers (id);
CREATE INDEX idx_peers_phone_number ON peers (phone_number);
CREATE INDEX idx_usernames_id ON usernames (id);
CREATE INDEX idx_usernames_username ON usernames (username);

CREATE TRIGGER trg_peers_last_update_on
    AFTER UPDATE
    ON peers
BEGIN
    UPDATE peers
    SET last_update_on = CAST(STRFTIME('%s', 'now') AS INTEGER)
    WHERE id = NEW.id;
END;
"""

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

TEST = {
    1: "149.154.175.10",
    2: "149.154.167.40",
    3: "149.154.175.117"
}

PROD = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
    203: "91.105.192.100"
}

def get_input_peer(peer_id: int, access_hash: int, peer_type: str):
    if peer_type in ["user", "bot"]:
        return raw.types.InputPeerUser(
            user_id=peer_id,
            access_hash=access_hash
        )

    if peer_type == "group":
        return raw.types.InputPeerChat(
            chat_id=-peer_id
        )

    if peer_type in ["direct", "channel", "forum", "supergroup"]:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id),
            access_hash=access_hash
        )

    raise ValueError(f"Invalid peer type: {peer_type}")


class SQLiteStorage(Storage):
    VERSION = 7
    USERNAME_TTL = 8 * 60 * 60
    FILE_EXTENSION = ".session"

    def __init__(
        self,
        name: str,
        workdir: Path,
        session_string: Optional[str] = None,
        in_memory: Optional[bool] = False,
        use_wal: Optional[bool] = True,
    ):
        super().__init__(name)

        self.executor = ThreadPoolExecutor(1)
        self.loop = utils.get_event_loop()
        self.conn = None # type: sqlite3.Connection

        self.session_string = session_string
        self.in_memory = in_memory
        self.use_wal = use_wal

        if self.in_memory:
            self.database = ":memory:"
        else:
            self.database = workdir / (self.name + self.FILE_EXTENSION)

    async def _run(self, func, *args):
        return await self.loop.run_in_executor(self.executor, func, *args)

    def _connect_impl(self, path):
        self.conn = sqlite3.connect(str(path), timeout=1, check_same_thread=False)

        with self.conn:
            if self.use_wal and path != ":memory:":
                self.conn.execute("PRAGMA journal_mode=WAL").close()
                self.conn.execute("PRAGMA synchronous=NORMAL").close()
                self.conn.execute("PRAGMA temp_store=1").close()
            else:
                self.conn.execute("PRAGMA journal_mode=DELETE").close()

    def _vacuum_impl(self):
        with self.conn:
            self.conn.execute("VACUUM")

    def _update_impl(self):
        version = self._get_impl("version", "number")

        if version == 1:
            with self.conn:
                self.conn.execute("DELETE FROM peers;")

            version += 1

        if version == 2:
            with self.conn:
                self.conn.execute("ALTER TABLE sessions ADD api_id INTEGER;")

            version += 1

        if version == 3:
            with self.conn:
                self.conn.executescript(USERNAMES_SCHEMA)

            version += 1

        if version == 4:
            with self.conn:
                self.conn.executescript(UPDATE_STATE_SCHEMA)

            version += 1

        if version == 5:
            with self.conn:
                self.conn.execute("CREATE INDEX idx_usernames_id ON usernames (id);")

            version += 1

        if version == 6:
            dc_id = self._get_impl("sessions", "dc_id")

            if self._get_impl("sessions", "test_mode"):
                address = TEST[dc_id]
                port = 80
            else:
                address = PROD[dc_id]
                port = 443

            with self.conn:
                self.conn.execute("ALTER TABLE sessions ADD server_address TEXT;")
                self.conn.execute("ALTER TABLE sessions ADD port INTEGER;")

                self.conn.execute("UPDATE sessions SET server_address = ?;", (address,))
                self.conn.execute("UPDATE sessions SET port = ?;", (port,))

            version += 1

        self._set_impl("version", "number", version)

    async def update(self):
        return await self._run(self._update_impl)

    def _create_impl(self):
        with self.conn:
            self.conn.executescript(SCHEMA)

            self.conn.execute("INSERT INTO version VALUES (?)", (self.VERSION,))

            self.conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (2, "149.154.167.51", 443, None, None, None, 0, None, None),
            )

    async def create(self):
        return await self._run(self._create_impl)

    async def open(self):
        if self.in_memory:
            await self._run(self._connect_impl, ":memory:")
            await self.create()

            if self.session_string:
                # Old format
                if len(self.session_string) in [
                    self.SESSION_STRING_SIZE,
                    self.SESSION_STRING_SIZE_64,
                ]:
                    dc_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                        (
                            self.OLD_SESSION_STRING_FORMAT
                            if len(self.session_string) == self.SESSION_STRING_SIZE
                            else self.OLD_SESSION_STRING_FORMAT_64
                        ),
                        base64.urlsafe_b64decode(
                            self.session_string + "=" * (-len(self.session_string) % 4)
                        ),
                    )

                    await self.dc_id(dc_id)
                    await self.test_mode(test_mode)
                    await self.auth_key(auth_key)
                    await self.user_id(user_id)
                    await self.is_bot(is_bot)
                    await self.date(0)

                    log.warning(
                        "You are using an old session string format. Use export_session_string to update"
                    )
                    return

                dc_id, api_id, test_mode, auth_key, user_id, is_bot = struct.unpack(
                    self.SESSION_STRING_FORMAT,
                    base64.urlsafe_b64decode(
                        self.session_string + "=" * (-len(self.session_string) % 4)
                    ),
                )

                await self.dc_id(dc_id)

                if test_mode:
                    await self.server_address(TEST[dc_id])
                    await self.port(80)
                else:
                    await self.server_address(PROD[dc_id])
                    await self.port(443)

                await self.api_id(api_id)
                await self.test_mode(test_mode)
                await self.auth_key(auth_key)
                await self.user_id(user_id)
                await self.is_bot(is_bot)
                await self.date(0)

            return

        path = self.database
        file_exists = isinstance(path, Path) and path.is_file()

        await self._run(self._connect_impl, path)

        if file_exists:
            await self.update()
        else:
            await self.create()

        await self._run(self._vacuum_impl)

    async def save(self):
        await self.date(int(time.time()))
        await self._run(self.conn.commit)

    async def close(self):
        await self._run(self.conn.close)
        self.executor.shutdown()

    async def delete(self):
        if not self.in_memory:
            Path(self.database).unlink()

    def _update_peers_impl(self, peers: List[Tuple[int, int, str, str]]):
        with self.conn:
            self.conn.executemany(
                "REPLACE INTO peers (id, access_hash, type, phone_number) VALUES (?, ?, ?, ?)",
                list(peers)
            )

    async def update_peers(self, peers: List[Tuple[int, int, str, str]]):
        return await self._run(self._update_peers_impl, peers)

    def _update_usernames_impl(self, usernames: List[Tuple[int, List[str]]]):
        with self.conn:
            self.conn.executemany("DELETE FROM usernames WHERE id = ?", [(id,) for id, _ in usernames])

            self.conn.executemany(
                "REPLACE INTO usernames (id, username) VALUES (?, ?)",
                [(id, username) for id, usernames in usernames for username in usernames],
            )

    async def update_usernames(self, usernames: List[Tuple[int, List[str]]]):
        return await self._run(self._update_usernames_impl, usernames)

    def _update_state_impl(self, value: Tuple[int, int, int, int, int] = object):
        if value is object:
            return self.conn.execute(
                "SELECT id, pts, qts, date, seq FROM update_state ORDER BY date ASC"
            ).fetchall()
        else:
            with self.conn:
                if isinstance(value, int):
                    self.conn.execute("DELETE FROM update_state WHERE id = ?", (value,))
                else:
                    self.conn.execute(
                        "REPLACE INTO update_state (id, pts, qts, date, seq) VALUES (?, ?, ?, ?, ?)",
                        value,
                    )

    async def update_state(self, value: Tuple[int, int, int, int, int] = object):
        return await self._run(self._update_state_impl, value)

    def _get_peer_by_id_impl(self, peer_id: int):
        return self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE id = ?", (peer_id,)
        ).fetchone()

    async def get_peer_by_id(self, peer_id: int):
        r = await self._run(self._get_peer_by_id_impl, peer_id)

        if r is None:
            raise KeyError(f"ID not found: {peer_id}")

        return get_input_peer(*r)

    def _get_peer_by_username_impl(self, username: str):
        return self.conn.execute(
            "SELECT p.id, p.access_hash, p.type, p.last_update_on FROM peers p "
            "JOIN usernames u ON p.id = u.id "
            "WHERE u.username = ? "
            "ORDER BY p.last_update_on DESC",
            (username,),
        ).fetchone()

    async def get_peer_by_username(self, username: str):
        r = await self._run(self._get_peer_by_username_impl, username)

        if r is None:
            raise KeyError(f"Username not found: {username}")

        if abs(time.time() - r[3]) > self.USERNAME_TTL:
            raise KeyError(f"Username expired: {username}")

        return get_input_peer(*r[:3])

    def _get_peer_by_phone_number_impl(self, phone_number: str):
        return self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE phone_number = ?", (phone_number,)
        ).fetchone()

    async def get_peer_by_phone_number(self, phone_number: str):
        r = await self._run(self._get_peer_by_phone_number_impl, phone_number)

        if r is None:
            raise KeyError(f"Phone number not found: {phone_number}")

        return get_input_peer(*r)

    def _get_impl(self, table: str, attr: str):
        return self.conn.execute(f"SELECT {attr} FROM {table}").fetchone()[0]

    def _set_impl(self, table: str, attr: str, value: Any):
        with self.conn:
            self.conn.execute(f"UPDATE {table} SET {attr} = ?", (value,))

    async def _get(self, table: str, attr: str):
        return await self._run(self._get_impl, table, attr)

    async def _set(self, table: str, attr: str, value: Any):
        return await self._run(self._set_impl, table, attr, value)

    async def _accessor(self, table: str, attr: str, value: Any = object):
        return await self._get(table, attr) if value is object else await self._set(table, attr, value)

    async def dc_id(self, value: int = object):
        return await self._accessor("sessions", "dc_id", value)

    async def server_address(self, value: str = object):
        return await self._accessor("sessions", "server_address", value)

    async def port(self, value: int = object):
        return await self._accessor("sessions", "port", value)

    async def api_id(self, value: int = object):
        return await self._accessor("sessions", "api_id", value)

    async def test_mode(self, value: bool = object):
        return await self._accessor("sessions", "test_mode", value)

    async def auth_key(self, value: bytes = object):
        return await self._accessor("sessions", "auth_key", value)

    async def date(self, value: int = object):
        return await self._accessor("sessions", "date", value)

    async def user_id(self, value: int = object):
        return await self._accessor("sessions", "user_id", value)

    async def is_bot(self, value: bool = object):
        return await self._accessor("sessions", "is_bot", value)

    async def version(self, value: int = object):
        return await self._accessor("version", "number", value)
