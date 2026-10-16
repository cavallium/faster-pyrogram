from __future__ import annotations as _annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from pyrogram import Client, raw


@pytest.mark.parametrize("wrapped", [False, True])
async def test_invoke_populates_peer_cache_from_join_results(wrapped):
    users = [raw.types.User(id=1, first_name="Test")]
    chats = [raw.types.ChatForbidden(id=2, title="Test")]
    updates = raw.types.Updates(updates=[], users=users, chats=chats, date=1, seq=1)
    result = raw.types.messages.ChatInviteJoinResultOk(updates=updates) if wrapped else updates
    client = SimpleNamespace(
        is_connected=True,
        session=SimpleNamespace(invoke=AsyncMock(return_value=result)),
        no_updates=False,
        takeout_id=None,
        sleep_threshold=10,
        fetch_peers=AsyncMock(),
    )
    assert (
        await Client.invoke(client, raw.functions.messages.ImportChatInvite(hash="test")) is result
    )
    assert client.fetch_peers.await_args_list == [call(users), call(chats)]
