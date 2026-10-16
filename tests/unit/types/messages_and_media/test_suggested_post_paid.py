from __future__ import annotations as _annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyrogram import raw, types


async def test_ton_payment_keeps_nanoton_amount_without_reply_fetch():
    client = SimpleNamespace(fetch_replies=False, get_messages=AsyncMock())
    message = raw.types.MessageService(
        id=1,
        peer_id=raw.types.PeerChannel(channel_id=42),
        date=1,
        action=raw.types.MessageActionSuggestedPostSuccess(
            price=raw.types.StarsTonAmount(amount=123456789)
        ),
        reply_to=raw.types.MessageReplyHeader(reply_to_msg_id=77),
    )
    parsed = await types.SuggestedPostPaid._parse(client, message)
    assert parsed.amount == 123456789
    assert parsed.star_amount is None
    assert parsed.suggested_post_message_id == 77
    assert parsed.suggested_post_message is None
    client.get_messages.assert_not_awaited()
