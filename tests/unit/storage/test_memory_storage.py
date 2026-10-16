"""The public in-memory storage uses the same worker and API as SQLite sessions."""

from __future__ import annotations as _annotations

import pytest

from pyrogram import Client
from pyrogram.storage import MemoryStorage, UpdateState


async def test_memory_storage_round_trips_session_strings_without_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    storage = MemoryStorage("memory")
    await storage.open()
    try:
        await storage.dc_id(4)
        await storage.api_id(123)
        await storage.test_mode(False)
        await storage.auth_key(bytes(range(256)))
        await storage.user_id(456)
        await storage.is_bot(False)
        await storage.set_update_state(UpdateState(0, 10, 20, 30, 40))
        await storage.update_peers([(456, 789, "user", None)])
        await storage.update_usernames([(456, ["example"])])
        assert (await storage.get_peer_by_username("example")).access_hash == 789
        exported = await storage.export_session_string()
    finally:
        await storage.close()

    restored = MemoryStorage("restored", session_string=exported)
    await restored.open()
    try:
        assert await restored.dc_id() == 4
        assert await restored.auth_key() == bytes(range(256))
        assert await restored.user_id() == 456
        assert await restored.server_address() == "149.154.167.91"
        assert await restored.port() == 443
        assert await restored.get_update_states() == []
    finally:
        await restored.close()

    await storage.open()
    try:
        assert await storage.get_update_states() == []
        with pytest.raises(KeyError):
            await storage.get_peer_by_id(456)
    finally:
        await storage.close()
    await storage.delete()
    assert list(tmp_path.iterdir()) == []


def test_client_uses_public_memory_storage():
    client = Client("memory", in_memory=True)
    try:
        assert isinstance(client.storage, MemoryStorage)
        assert client.storage.in_memory
    finally:
        client.executor.shutdown(wait=False)
