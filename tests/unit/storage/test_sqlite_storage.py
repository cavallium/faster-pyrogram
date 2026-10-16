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
import sqlite3
import struct
import threading
from pathlib import Path

import pytest

from pyrogram.storage import UpdateState
from pyrogram.storage.sqlite_storage import PROD, SCHEMA, TEST, SQLiteStorage


@pytest.mark.asyncio
async def test_conn_property_round_trips_the_connection() -> None:
    # self.conn moved from a plain attribute (declared non-Optional via a
    #  `# type:` comment but assigned None in __init__) to a property backed by
    #  self._conn, so open()/close() and every query still have to see the same
    #  connection object through the ordinary self.conn read/write syntax.
    storage = SQLiteStorage("test", Path(), in_memory=True)

    await storage.open()
    assert await storage.is_bot() is None

    await storage.date(0)
    assert await storage.date() == 0

    await storage.close()


def test_conn_raises_before_open() -> None:
    storage = SQLiteStorage("test", Path(), in_memory=True)

    with pytest.raises(RuntimeError):
        _ = storage.conn


@pytest.mark.parametrize("use_wal", [False, True])
async def test_file_storage_persists_peers_and_partial_update_states(tmp_path, use_wal):

    storage = SQLiteStorage("persistent", tmp_path, use_wal=use_wal)
    await storage.open()
    try:
        await storage.update_peers(iter([(123, 456, "user", "12345")]))
        await storage.update_usernames(iter([(123, [None, "first"])]))
        await storage.update_usernames([(123, [None, "second"])])
        await storage.set_update_state(UpdateState(0, 10, 20, 30, 40))
        await storage.set_update_state([UpdateState(0, 11, None, None, None)])
        await storage.set_update_state([UpdateState(1, 1, 2, 3, 4)])
        assert await storage.get_update_states([]) == []
        await storage.delete_update_state([])
        await storage.delete_update_state(iter([1]))
        await storage.save()
        journal_mode = await storage._run(
            lambda: storage.conn.execute("PRAGMA journal_mode").fetchone()[0]
        )
        assert journal_mode == ("wal" if use_wal else "delete")
    finally:
        await storage.close()

    await storage.open()
    try:
        assert (await storage.get_peer_by_username("second")).user_id == 123
        assert (await storage.get_peer_by_phone_number("12345")).user_id == 123
        with pytest.raises(KeyError):
            await storage.get_peer_by_username("first")
        assert await storage.get_update_states(0) == [UpdateState(0, 11, 20, 30, 40)]
        assert await storage.get_update_states(iter([1])) == []
        await storage.delete_update_state(0)
        assert await storage.get_update_states() == []
    finally:
        await storage.close()
    await storage.delete()
    assert not (tmp_path / "persistent.session").exists()


async def test_sqlite_calls_run_on_one_worker_off_the_event_loop(monkeypatch):

    main_thread = threading.get_ident()
    threads = []
    connect = sqlite3.connect

    class TracedConnection(sqlite3.Connection):
        def execute(self, *args, **kwargs):
            threads.append(threading.get_ident())
            return super().execute(*args, **kwargs)

        def executemany(self, *args, **kwargs):
            threads.append(threading.get_ident())
            return super().executemany(*args, **kwargs)

    def traced_connect(*args, **kwargs):
        threads.append(threading.get_ident())
        return connect(*args, **kwargs, factory=TracedConnection)

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    storage = SQLiteStorage("worker", Path(), in_memory=True)
    await storage.open()
    try:
        await asyncio.gather(*(storage.user_id(i) for i in range(20)))
        assert await storage.user_id() == 19
        await storage.update_peers([(1, 2, "user", None)])
        assert (await storage.get_peer_by_id(1)).user_id == 1
        await storage.save()
    finally:
        await storage.close()
    assert len(set(threads)) == 1
    assert main_thread not in threads
    assert storage.executor is None


@pytest.mark.parametrize("test_mode", [False, True])
@pytest.mark.parametrize(
    "format_",
    [
        SQLiteStorage.OLD_SESSION_STRING_FORMAT,
        SQLiteStorage.OLD_SESSION_STRING_FORMAT_64,
        SQLiteStorage.SESSION_STRING_FORMAT,
    ],
)
async def test_session_string_import_sets_connection_endpoint(test_mode, format_):

    fields = [3, test_mode, b"x" * 256, 123, False]
    if format_ == SQLiteStorage.SESSION_STRING_FORMAT:
        fields.insert(1, 12345)
    session_string = base64.urlsafe_b64encode(struct.pack(format_, *fields)).decode().rstrip("=")
    storage = SQLiteStorage("import", Path(), in_memory=True, session_string=session_string)
    await storage.open()
    try:
        assert await storage.dc_id() == 3
        assert await storage.server_address() == (TEST if test_mode else PROD)[3]
        assert await storage.port() == (80 if test_mode else 443)
        assert await storage.auth_key() == b"x" * 256
        assert await storage.user_id() == 123
    finally:
        await storage.close()


async def test_v6_session_migration_preserves_auth_and_adds_endpoint(tmp_path):

    legacy_schema = SCHEMA.replace("    server_address TEXT,\n", "").replace(
        "    port           INTEGER,\n", ""
    )
    with sqlite3.connect(tmp_path / "migration.session") as conn:
        conn.executescript(legacy_schema)
        conn.execute("INSERT INTO version VALUES (6)")
        conn.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?)", (4, 12345, 0, b"key", 0, 123, 0)
        )

    storage = SQLiteStorage("migration", tmp_path)
    await storage.open()
    try:
        assert await storage.version() == 7
        assert await storage.dc_id() == 4
        assert await storage.server_address() == PROD[4]
        assert await storage.port() == 443
        assert await storage.auth_key() == b"key"
        assert await storage.user_id() == 123
    finally:
        await storage.close()

    await storage.open()
    try:
        assert await storage.version() == 7
        assert await storage.auth_key() == b"key"
    finally:
        await storage.close()


async def test_failed_open_releases_worker_and_allows_retry():
    storage = SQLiteStorage("invalid", Path(), in_memory=True, session_string="invalid")
    with pytest.raises(struct.error):
        await storage.open()
    assert storage.executor is None
    assert storage._conn is None
    storage.session_string = None
    await storage.open()
    await storage.close()


async def test_cancelled_queued_close_drains_before_reopen():
    storage = SQLiteStorage("cancelled-close", Path(), in_memory=True)
    await storage.open()
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()

    def block_worker():
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)

    blocker = storage.executor.submit(block_worker)
    await asyncio.wait_for(started.wait(), 5)
    closing = asyncio.create_task(storage.close())
    try:
        await asyncio.sleep(0)  # close has submitted its callback behind the blocked worker.
        for _ in range(2):
            closing.cancel()
            await asyncio.sleep(0)
            assert not closing.done()
            assert storage.executor is not None
            assert storage._conn is not None
            with pytest.raises(RuntimeError, match="already open"):
                await storage.open()
    finally:
        release.set()
        await asyncio.wrap_future(blocker)
        with pytest.raises(asyncio.CancelledError):
            await closing

    assert storage.executor is None
    assert storage._conn is None
    await storage.open()
    await storage.close()


@pytest.mark.parametrize("cancel_open", [False, True])
async def test_open_cleanup_drains_through_repeated_cancellation(monkeypatch, cancel_open):
    storage = SQLiteStorage("cancelled-open", Path(), in_memory=True)
    loop = asyncio.get_running_loop()
    open_started = asyncio.Event()
    cleanup_started = asyncio.Event()
    release_open = threading.Event()
    release_cleanup = threading.Event()
    original_open = storage._open_impl
    original_cleanup = storage._close_failed_open

    def blocked_open():
        original_open()
        loop.call_soon_threadsafe(open_started.set)
        assert release_open.wait(5)
        if not cancel_open:
            raise ValueError("failed open")

    def blocked_cleanup():
        loop.call_soon_threadsafe(cleanup_started.set)
        assert release_cleanup.wait(5)
        original_cleanup()

    monkeypatch.setattr(storage, "_open_impl", blocked_open)
    monkeypatch.setattr(storage, "_close_failed_open", blocked_cleanup)
    opening = asyncio.create_task(storage.open())
    try:
        await asyncio.wait_for(open_started.wait(), 5)
        if cancel_open:
            opening.cancel()
        release_open.set()
        await asyncio.wait_for(cleanup_started.wait(), 5)
        for _ in range(2):
            opening.cancel()
            await asyncio.sleep(0)
            assert not opening.done()
            assert storage.executor is not None
            assert storage._conn is not None
            with pytest.raises(RuntimeError, match="already open"):
                await storage.open()
    finally:
        release_open.set()
        release_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await opening

    assert storage.executor is None
    assert storage._conn is None
    monkeypatch.setattr(storage, "_open_impl", original_open)
    await storage.open()
    await storage.close()
