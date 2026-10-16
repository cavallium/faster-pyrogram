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

from __future__ import annotations as _annotations

import asyncio
import base64
import logging
import sqlite3
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pyrogram import raw

from .. import utils
from .storage import Storage, UpdateState

if TYPE_CHECKING:
    from collections.abc import Iterable

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

TEST = {1: "149.154.175.10", 2: "149.154.167.40", 3: "149.154.175.117"}

PROD = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
    203: "91.105.192.100",
}


def get_input_peer(peer_id: int, access_hash: int, peer_type: str):
    if peer_type in {"user", "bot"}:
        return raw.types.InputPeerUser(user_id=peer_id, access_hash=access_hash)

    if peer_type == "group":
        return raw.types.InputPeerChat(chat_id=-peer_id)

    if peer_type in {"direct", "channel", "forum", "supergroup", "community"}:
        return raw.types.InputPeerChannel(
            channel_id=utils.get_channel_id(peer_id), access_hash=access_hash
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
        session_string: str | None = None,
        in_memory: bool = False,
        use_wal: bool = True,
    ):
        self.name = name
        self.executor: ThreadPoolExecutor | None = None
        self._conn: sqlite3.Connection | None = None

        self.session_string = session_string
        self.in_memory = in_memory
        self.use_wal = use_wal

        if self.in_memory:
            self.database = ":memory:"
        else:
            self.database = workdir / (self.name + self.FILE_EXTENSION)

    @property
    def conn(self) -> sqlite3.Connection:
        # Every method below this point runs only after open() has set a real
        #  connection; raising here narrows the type once for all of them
        #  instead of repeating the same guard at every call site.
        if self._conn is None:
            msg = "`SQLiteStorage.conn` accessed before `open()`"
            raise RuntimeError(msg)

        return self._conn

    @conn.setter
    def conn(self, value: sqlite3.Connection | None) -> None:
        self._conn = value

    def _update_impl(self):
        version = self._version_impl()

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
            if self._test_mode_impl():
                address = TEST[self._dc_id_impl()]
                port = 80
            else:
                address = PROD[self._dc_id_impl()]
                port = 443

            with self.conn:
                self.conn.execute("ALTER TABLE sessions ADD server_address TEXT;")
                self.conn.execute("ALTER TABLE sessions ADD port INTEGER;")

                self.conn.execute("UPDATE sessions SET server_address = ?;", (address,))
                self.conn.execute("UPDATE sessions SET port = ?;", (port,))

            version += 1

        self._version_impl(version)

    def _create_impl(self):
        with self.conn:
            self.conn.executescript(SCHEMA)

            self.conn.execute("INSERT INTO version VALUES (?)", (self.VERSION,))

            self.conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (2, "149.154.167.51", 443, None, None, None, 0, None, None),
            )

    def _open_impl(self):
        if self.in_memory:
            self.conn = sqlite3.connect(":memory:", timeout=1, check_same_thread=False)
            self._create_impl()

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

                    self._dc_id_impl(dc_id)
                    self._server_address_impl((TEST if test_mode else PROD)[dc_id])
                    self._port_impl(80 if test_mode else 443)
                    self._test_mode_impl(test_mode)
                    self._auth_key_impl(auth_key)
                    self._user_id_impl(user_id)
                    self._is_bot_impl(is_bot)
                    self._date_impl(0)

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

                self._dc_id_impl(dc_id)

                if test_mode:
                    self._server_address_impl(TEST[dc_id])
                    self._port_impl(80)
                else:
                    self._server_address_impl(PROD[dc_id])
                    self._port_impl(443)

                self._api_id_impl(api_id)
                self._test_mode_impl(test_mode)
                self._auth_key_impl(auth_key)
                self._user_id_impl(user_id)
                self._is_bot_impl(is_bot)
                self._date_impl(0)

            return

        path = self.database
        file_exists = isinstance(path, Path) and path.is_file()

        self.conn = sqlite3.connect(str(path), timeout=1, check_same_thread=False)

        if self.use_wal:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA temp_store=1")
        else:
            self.conn.execute("PRAGMA journal_mode=DELETE")

        if file_exists:
            self._update_impl()
        else:
            self._create_impl()

        with self.conn:
            self.conn.execute("VACUUM")

    def _save_impl(self):
        self._date_impl(int(time.time()))
        self.conn.commit()

    def _close_impl(self):
        self.conn.close()
        self.conn = None

    def _delete_impl(self):
        if not self.in_memory:
            Path(self.database).unlink()

    def _update_peers_impl(self, peers: Iterable[tuple[int, int, str, str | None]]):
        with self.conn:
            self.conn.executemany(
                "REPLACE INTO peers (id, access_hash, type, phone_number) VALUES (?, ?, ?, ?)",
                peers,
            )

    def _update_usernames_impl(self, usernames: Iterable[tuple[int, list[str | None]]]):
        with self.conn:
            usernames = list(usernames)

            if not usernames:
                return

            ids = [id_ for id_, _ in usernames]
            placeholders = ", ".join("?" for _ in ids)

            self.conn.execute(
                f"DELETE FROM usernames WHERE id IN ({placeholders})",
                ids,
            )

            self.conn.executemany(
                "REPLACE INTO usernames (id, username) VALUES (?, ?)",
                [
                    (id_, username)
                    for id_, names in usernames
                    for username in names
                    if username is not None
                ],
            )

    def _get_update_states_impl(self, ids: int | Iterable[int] | None = None):
        query = "SELECT id, pts, qts, date, seq FROM update_state"

        if ids is not None:
            state_ids = (ids,) if isinstance(ids, int) else tuple(ids)

            if not state_ids:
                return []

            placeholders = ", ".join("?" for _ in state_ids)
            query += f" WHERE id IN ({placeholders})"
        else:
            state_ids = ()

        rows = self.conn.execute(query + " ORDER BY date ASC", state_ids).fetchall()
        return [UpdateState(*row) for row in rows]

    def _set_update_state_impl(self, update_state: UpdateState | Iterable[UpdateState]):
        with self.conn:
            states = [update_state] if isinstance(update_state, UpdateState) else update_state

            self.conn.executemany(
                "INSERT INTO update_state (id, pts, qts, date, seq) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "pts = COALESCE(excluded.pts, update_state.pts), "
                "qts = COALESCE(excluded.qts, update_state.qts), "
                "date = COALESCE(excluded.date, update_state.date), "
                "seq = COALESCE(excluded.seq, update_state.seq)",
                [(state.id, state.pts, state.qts, state.date, state.seq) for state in states],
            )

    def _delete_update_state_impl(self, state_id):
        with self.conn:
            if isinstance(state_id, int):
                self.conn.execute(
                    "DELETE FROM update_state WHERE id = ?",
                    (state_id,),
                )
                return

            state_ids = tuple(state_id)

            if not state_ids:
                return

            placeholders = ", ".join("?" for _ in state_ids)

            self.conn.execute(
                f"DELETE FROM update_state WHERE id IN ({placeholders})",
                state_ids,
            )

    def _get_peer_by_id_impl(self, peer_id: int):
        r = self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE id = ?", (peer_id,)
        ).fetchone()

        if r is None:
            raise KeyError(f"ID not found: {peer_id}")

        return get_input_peer(*r)

    def _get_peer_by_username_impl(self, username: str):
        r = self.conn.execute(
            "SELECT p.id, p.access_hash, p.type, p.last_update_on FROM peers p "
            "JOIN usernames u ON p.id = u.id "
            "WHERE u.username = ? "
            "ORDER BY p.last_update_on DESC",
            (username,),
        ).fetchone()

        if r is None:
            raise KeyError(f"Username not found: {username}")

        if abs(time.time() - r[3]) > self.USERNAME_TTL:
            raise KeyError(f"Username expired: {username}")

        return get_input_peer(*r[:3])

    def _get_peer_by_phone_number_impl(self, phone_number: str):
        r = self.conn.execute(
            "SELECT id, access_hash, type FROM peers WHERE phone_number = ?", (phone_number,)
        ).fetchone()

        if r is None:
            raise KeyError(f"Phone number not found: {phone_number}")

        return get_input_peer(*r)

    def _get(self, table: str, attr: str):
        return self.conn.execute(f"SELECT {attr} FROM {table}").fetchone()[0]

    def _set(self, table: str, attr: str, value: Any):
        with self.conn:
            self.conn.execute(f"UPDATE {table} SET {attr} = ?", (value,))

    def _accessor(self, table: str, attr: str, value: Any = object):
        return self._get(table, attr) if value is object else self._set(table, attr, value)

    # `object` (the class, not an instance) is the sentinel for "no value passed"
    #  (read the column instead of writing to it), so every accessor's parameter type
    #  has to include it alongside the column's real type.
    def _dc_id_impl(self, value: int | None | type[object] = object) -> int | None:
        return self._accessor("sessions", "dc_id", value)

    def _server_address_impl(self, value: str | None | type[object] = object) -> str | None:
        return self._accessor("sessions", "server_address", value)

    def _port_impl(self, value: int | None | type[object] = object) -> int | None:
        return self._accessor("sessions", "port", value)

    def _api_id_impl(self, value: int | None | type[object] = object) -> int | None:
        return self._accessor("sessions", "api_id", value)

    def _test_mode_impl(self, value: bool | None | type[object] = object) -> bool | None:
        return self._accessor("sessions", "test_mode", value)

    def _auth_key_impl(self, value: bytes | None | type[object] = object) -> bytes | None:
        return self._accessor("sessions", "auth_key", value)

    def _date_impl(self, value: int | None | type[object] = object) -> int | None:
        return self._accessor("sessions", "date", value)

    def _user_id_impl(self, value: int | None | type[object] = object) -> int | None:
        return self._accessor("sessions", "user_id", value)

    def _is_bot_impl(self, value: bool | None | type[object] = object) -> bool | None:
        return self._accessor("sessions", "is_bot", value)

    def _version_impl(self, value: int | None | type[object] = object) -> int | None:
        return self._accessor("version", "number", value)

    def _submit(self, function, *args):
        if self.executor is None:
            raise RuntimeError("SQLiteStorage accessed before open() or after close()")

        return asyncio.get_running_loop().run_in_executor(self.executor, function, *args)

    async def _run(self, function, *args):
        return await self._submit(function, *args)

    async def _run_to_completion(self, function, *args):
        future = self._submit(function, *args)
        cancelled = False
        while True:
            try:
                result = await asyncio.shield(future)
                break
            except asyncio.CancelledError:
                if future.cancelled():
                    raise
                # Keep ownership until the worker finishes, even if cancellation is repeated.
                cancelled = True

        if cancelled:
            raise asyncio.CancelledError

        return result

    async def open(self):
        if self.executor is not None:
            raise RuntimeError("SQLiteStorage is already open")

        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pyrogram-storage")
        try:
            await self._run(self._open_impl)
        except BaseException:
            # A failed migration or session import must not leave a worker or connection behind.
            try:
                await self._run_to_completion(self._close_failed_open)
            finally:
                self.executor.shutdown(wait=False)
                self.executor = None
            raise

    def _close_failed_open(self):
        if self._conn is not None:
            self._close_impl()

    async def close(self):
        try:
            await self._run_to_completion(self._close_impl)
        finally:
            if self.executor is not None:
                self.executor.shutdown(wait=False)
                self.executor = None

    async def update(self):
        return await self._run(self._update_impl)

    async def create(self):
        return await self._run(self._create_impl)

    async def save(self):
        return await self._run(self._save_impl)

    async def delete(self):
        await asyncio.to_thread(self._delete_impl)

    async def update_peers(self, peers: Iterable[tuple[int, int, str, str | None]]):
        return await self._run(self._update_peers_impl, peers)

    async def update_usernames(self, usernames: Iterable[tuple[int, list[str | None]]]):
        return await self._run(self._update_usernames_impl, usernames)

    async def get_update_states(self, ids: int | Iterable[int] | None = None):
        return await self._run(self._get_update_states_impl, ids)

    async def set_update_state(self, update_state: UpdateState | Iterable[UpdateState]):
        return await self._run(self._set_update_state_impl, update_state)

    async def delete_update_state(self, state_id):
        return await self._run(self._delete_update_state_impl, state_id)

    async def get_peer_by_id(self, peer_id: int):
        return await self._run(self._get_peer_by_id_impl, peer_id)

    async def get_peer_by_username(self, username: str):
        return await self._run(self._get_peer_by_username_impl, username)

    async def get_peer_by_phone_number(self, phone_number: str):
        return await self._run(self._get_peer_by_phone_number_impl, phone_number)

    async def dc_id(self, value: int | None | type[object] = object) -> int | None:
        return await self._run(self._dc_id_impl, value)

    async def server_address(self, value: str | None | type[object] = object) -> str | None:
        return await self._run(self._server_address_impl, value)

    async def port(self, value: int | None | type[object] = object) -> int | None:
        return await self._run(self._port_impl, value)

    async def api_id(self, value: int | None | type[object] = object) -> int | None:
        return await self._run(self._api_id_impl, value)

    async def test_mode(self, value: bool | None | type[object] = object) -> bool | None:
        return await self._run(self._test_mode_impl, value)

    async def auth_key(self, value: bytes | None | type[object] = object) -> bytes | None:
        return await self._run(self._auth_key_impl, value)

    async def date(self, value: int | None | type[object] = object) -> int | None:
        return await self._run(self._date_impl, value)

    async def user_id(self, value: int | None | type[object] = object) -> int | None:
        return await self._run(self._user_id_impl, value)

    async def is_bot(self, value: bool | None | type[object] = object) -> bool | None:
        return await self._run(self._is_bot_impl, value)

    async def version(self, value: int | None | type[object] = object) -> int | None:
        return await self._run(self._version_impl, value)
