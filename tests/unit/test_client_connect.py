"""Connection setup cleans up the real session and storage when transport startup fails."""

from __future__ import annotations as _annotations

import base64
import struct

import pytest

from pyrogram import Client
from pyrogram.storage import Storage


async def test_failed_connect_releases_storage_and_can_be_retried():
    session_string = (
        base64.urlsafe_b64encode(
            struct.pack(Storage.SESSION_STRING_FORMAT, 2, 1, False, bytes(256), 123, False)
        )
        .decode()
        .rstrip("=")
    )
    connections = []

    class RefusedConnection:
        def __init__(self, **kwargs):
            self.closed = False
            connections.append(self)

        async def connect(self):
            raise OSError("connection refused")

        async def close(self):
            self.closed = True

    client = Client(
        "connect_failure", session_string=session_string, connection_factory=RefusedConnection
    )
    try:
        for _ in range(2):
            with pytest.raises(OSError, match="connection refused"):
                await client.connect()
            assert not client.is_connected
            assert client.session is None
            assert connections[-1].closed
            assert client.storage.executor is None
            assert client.storage._conn is None
        assert len(connections) == 2
    finally:
        if client.storage.executor is not None:
            await client.storage.close()
        client.executor.shutdown(wait=False)
