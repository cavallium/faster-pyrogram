from __future__ import annotations as _annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pyrogram import Client, raw
from pyrogram.storage import MemoryStorage, UpdateState


@pytest.mark.parametrize("channel", [False, True])
async def test_empty_recovery_keeps_the_returned_cursor(channel):
    state_id = -1000000000042 if channel else 0
    storage = MemoryStorage("recover-empty")
    await storage.open()
    await storage.set_update_state(UpdateState(state_id, 42, 2, 123, 9))
    diff = (
        raw.types.updates.ChannelDifferenceEmpty(pts=99, final=True)
        if channel
        else raw.types.updates.DifferenceEmpty(date=200, seq=10)
    )
    client = SimpleNamespace(
        storage=storage,
        invoke=AsyncMock(return_value=diff),
        resolve_peer=AsyncMock(return_value=raw.types.InputChannel(channel_id=42, access_hash=7)),
    )
    try:
        assert await Client.recover_gaps(client, state_id) == (0, 0)
        expected = (
            UpdateState(state_id, 99, 2, 123, 9) if channel else UpdateState(0, 42, 2, 200, 10)
        )
        assert await storage.get_update_states(state_id) == [expected]
        client.invoke.assert_awaited_once()
    finally:
        await storage.close()
