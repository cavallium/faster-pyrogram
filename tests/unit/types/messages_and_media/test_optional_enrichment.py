from __future__ import annotations as _annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pyrogram import Client, raw, types


GIFT_CASES = [
    (
        types.PremiumGiftCode,
        raw.types.MessageActionGiftCode(days=90, slug="gift", unclaimed=True),
        ({}, {}),
        "code",
        "gift",
        raw.types.InputStickerSetPremiumGifts,
    ),
    (
        types.GiftedPremium,
        raw.types.MessageActionGiftPremium(currency="EUR", amount=900, days=90),
        (None, None, {}),
        "day_count",
        90,
        raw.types.InputStickerSetPremiumGifts,
    ),
    (
        types.GiftedStars,
        raw.types.MessageActionGiftStars(currency="EUR", amount=900, stars=100),
        (),
        "star_count",
        100,
        raw.types.InputStickerSetPremiumGifts,
    ),
    (
        types.GiftedGrams,
        raw.types.MessageActionGiftTon(
            currency="EUR", amount=900, crypto_currency="TON", crypto_amount=123
        ),
        (),
        "gram_amount",
        123,
        raw.types.InputStickerSetTonGifts,
    ),
    (
        types.GiveawayPrizeStars,
        raw.types.MessageActionPrizeStars(
            stars=100,
            transaction_id="tx",
            boost_peer=raw.types.PeerChannel(channel_id=42),
            giveaway_msg_id=123,
            unclaimed=True,
        ),
        ({},),
        "giveaway_message_id",
        123,
        raw.types.InputStickerSetPremiumGifts,
    ),
]


@pytest.fixture
def client():
    return SimpleNamespace(
        fetch_stickers=False,
        fetch_replies=False,
        invoke=AsyncMock(),
        get_messages=AsyncMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("parser,action,args,field,value,sticker_set", GIFT_CASES)
async def test_gift_metadata_without_optional_requests(
    client, parser, action, args, field, value, sticker_set
):
    result = await parser._parse(client, action, *args)

    assert getattr(result, field) == value
    assert result.sticker is None
    client.invoke.assert_not_awaited()
    client.get_messages.assert_not_awaited()
    if parser is types.GiveawayPrizeStars:
        assert result.is_unclaimed is True
        assert result.giveaway_message is None
        assert result.star_count == 100
        assert result.transaction_id == "tx"


@pytest.mark.asyncio
@pytest.mark.parametrize("parser,action,args,field,value,sticker_set", GIFT_CASES)
@pytest.mark.parametrize("documents", [[], [SimpleNamespace(attributes=[])]])
async def test_gift_stickers_enabled(
    client, monkeypatch, parser, action, args, field, value, sticker_set, documents
):
    client.fetch_stickers = True
    client.invoke.return_value = SimpleNamespace(documents=documents)
    sticker = object()
    parse_sticker = AsyncMock(return_value=sticker)
    monkeypatch.setattr(types.Sticker, "_parse", parse_sticker)

    result = await parser._parse(client, action, *args)

    assert getattr(result, field) == value
    assert result.sticker is (sticker if documents else None)
    request = client.invoke.await_args.args[0]
    assert isinstance(request, raw.functions.messages.GetStickerSet)
    assert isinstance(request.stickerset, sticker_set)
    assert request.hash == 0
    client.get_messages.assert_not_awaited()
    if documents:
        parse_sticker.assert_awaited_once_with(client, documents[0], {})
    else:
        parse_sticker.assert_not_awaited()


GIVEAWAY_CASES = [
    (types.GiveawayPrizeStars, GIFT_CASES[-1][1], ({},)),
    (
        types.GiveawayWinners,
        raw.types.MessageMediaGiveawayResults(
            channel_id=42,
            launch_msg_id=123,
            winners_count=2,
            unclaimed_count=1,
            winners=[],
            until_date=1,
            stars=100,
        ),
        ({}, {}),
    ),
    (
        types.GiveawayCompleted,
        raw.types.MessageActionGiveawayResults(winners_count=2, unclaimed_count=1),
        (SimpleNamespace(id=-1000000000042), 123),
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("parser,action,args", GIVEAWAY_CASES)
@pytest.mark.parametrize("enabled", [False, True])
async def test_giveaway_reference_fetch_is_optional(client, parser, action, args, enabled):
    client.fetch_replies = enabled
    message = object()
    client.get_messages.return_value = message

    result = await parser._parse(client, action, *args)

    assert result.giveaway_message_id == 123
    assert result.giveaway_message is (message if enabled else None)
    client.invoke.assert_not_awaited()
    if enabled:
        client.get_messages.assert_awaited_once_with(
            chat_id=-1000000000042, message_ids=123, replies=0
        )
    else:
        client.get_messages.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("parser,action,args,field,value,sticker_set", GIFT_CASES)
@pytest.mark.parametrize("failure", [RuntimeError("fetch failed"), asyncio.CancelledError()])
async def test_enabled_sticker_fetch_propagates_failures(
    client, parser, action, args, field, value, sticker_set, failure
):
    client.fetch_stickers = True
    client.invoke.side_effect = failure

    with pytest.raises(type(failure)):
        await parser._parse(client, action, *args)


@pytest.mark.asyncio
@pytest.mark.parametrize("parser,action,args", GIVEAWAY_CASES)
@pytest.mark.parametrize("failure", [RuntimeError("fetch failed"), asyncio.CancelledError()])
async def test_enabled_reference_fetch_propagates_failures(client, parser, action, args, failure):
    client.fetch_replies = True
    client.get_messages.side_effect = failure

    with pytest.raises(type(failure)):
        await parser._parse(client, action, *args)


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("missing_chat", [False, True])
async def test_media_area_channel_post(client, enabled, missing_chat):
    client.fetch_replies = enabled
    area = raw.types.MediaAreaChannelPost(
        coordinates=raw.types.MediaAreaCoordinates(x=1, y=2, w=3, h=4, rotation=0),
        channel_id=42,
        msg_id=123,
    )
    channel = raw.types.ChannelForbidden(id=42, access_hash=1, title="channel")
    result = await types.MediaArea._parse(client, area, {} if missing_chat else {42: channel})

    assert result.message_id == 123
    assert (result.sender_chat is None) == missing_chat
    if not missing_chat:
        assert result.sender_chat.id == -1000000000042
    if enabled:
        client.get_messages.assert_awaited_once_with(chat_id=-1000000000042, message_ids=123)
        assert result.message is client.get_messages.return_value
    else:
        client.get_messages.assert_not_awaited()
        assert result.message is None
    client.invoke.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_media_area_gift(client, enabled):
    client.fetch_stories = enabled
    client.get_upgraded_gift = AsyncMock()
    area = raw.types.MediaAreaStarGift(
        coordinates=raw.types.MediaAreaCoordinates(x=1, y=2, w=3, h=4, rotation=0), slug="gift-123"
    )

    result = await types.MediaArea._parse(client, area, {})

    assert result.gift_slug == "gift-123"
    if enabled:
        client.get_upgraded_gift.assert_awaited_once_with("gift-123")
        assert result.gift is client.get_upgraded_gift.return_value
    else:
        client.get_upgraded_gift.assert_not_awaited()
        assert result.gift is None
    client.invoke.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("returned_thumbs", [[], [raw.types.DocumentEmpty(id=99)]])
async def test_sticker_set_missing_thumbnail_fetch(client, enabled, returned_thumbs):
    client.fetch_stickers = enabled
    client.sticker_set_name_cache = SimpleNamespace(set=AsyncMock())
    client.invoke.return_value = returned_thumbs
    sticker_set = raw.types.messages.StickerSet(
        set=raw.types.StickerSet(
            id=42,
            access_hash=1,
            title="set",
            short_name="set",
            count=0,
            hash=0,
            thumb_document_id=99,
        ),
        documents=[],
        packs=[],
        keywords=[],
    )

    result = await types.StickerSet._parse(client, sticker_set)

    assert result.id == 42
    assert result.raw is sticker_set
    assert not result.stickers
    assert result.thumbs is None
    if enabled:
        request = client.invoke.await_args.args[0]
        assert isinstance(request, raw.functions.messages.GetCustomEmojiDocuments)
        assert request.document_id == [99]
    else:
        client.invoke.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_sticker_set_without_thumbnail(client):
    client.sticker_set_name_cache = SimpleNamespace(set=AsyncMock())
    sticker_set = raw.types.messages.StickerSet(
        set=raw.types.StickerSet(
            id=42, access_hash=1, title="set", short_name="set", count=0, hash=0
        ),
        documents=[],
        packs=[],
        keywords=[],
    )

    result = await types.StickerSet._parse(client, sticker_set)

    assert result.thumbs is None
    client.invoke.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("parser", [types.User._parse_full, types.Chat._parse_full_user])
async def test_full_user_optional_message_bodies(client, parser, enabled):
    client.fetch_replies = enabled
    user = raw.types.User(id=7, access_hash=1, first_name="user")
    full_user = raw.types.UserFull(
        id=7,
        settings=raw.types.PeerSettings(),
        notify_settings=raw.types.PeerNotifySettings(),
        common_chats_count=0,
        pinned_msg_id=123,
        personal_channel_id=42,
        personal_channel_message=321,
    )
    channel = raw.types.ChannelForbidden(id=42, access_hash=1, title="channel")

    result = await parser(client, full_user, {7: user}, {42: channel})

    assert result.id == 7
    assert result.raw is full_user
    assert result.raw.pinned_msg_id == 123
    assert result.raw.personal_channel_message == 321
    assert result.personal_channel.id == -1000000000042
    if enabled:
        assert client.get_messages.await_count == 2
        assert result.pinned_message is client.get_messages.return_value
        assert result.personal_channel_message is client.get_messages.return_value
    else:
        client.get_messages.assert_not_awaited()
        assert result.pinned_message is None
        assert result.personal_channel_message is None
    client.invoke.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("is_channel", [False, True])
async def test_full_chat_optional_pinned_message(client, enabled, is_channel):
    client.fetch_replies = enabled
    if is_channel:
        peer = raw.types.Channel(
            id=42,
            access_hash=1,
            title="channel",
            photo=raw.types.ChatPhotoEmpty(),
            date=1,
            usernames=[],
            restriction_reason=[],
        )
        full_chat = raw.types.ChannelFull(
            id=42,
            about="description",
            read_inbox_max_id=0,
            read_outbox_max_id=0,
            unread_count=0,
            chat_photo=raw.types.PhotoEmpty(id=1),
            notify_settings=raw.types.PeerNotifySettings(),
            bot_info=[],
            pts=0,
            pinned_msg_id=123,
        )
        parser = types.Chat._parse_full_channel
    else:
        peer = raw.types.ChatForbidden(id=42, title="chat")
        full_chat = raw.types.ChatFull(
            id=42,
            about="description",
            participants=raw.types.ChatParticipantsForbidden(chat_id=42),
            notify_settings=raw.types.PeerNotifySettings(),
            pinned_msg_id=123,
        )
        parser = types.Chat._parse_full_chat

    result = await parser(client, full_chat, {}, {42: peer})

    assert result.raw is full_chat
    assert result.raw.pinned_msg_id == 123
    assert result.description == "description"
    if enabled:
        client.get_messages.assert_awaited_once_with(chat_id=result.id, pinned=True)
        assert result.pinned_message is client.get_messages.return_value
    else:
        client.get_messages.assert_not_awaited()
        assert result.pinned_message is None
    client.invoke.assert_not_awaited()


@pytest.mark.parametrize("parser,action,args,field,value,sticker_set", GIFT_CASES)
async def test_full_service_message_parse_with_enrichment_disabled(
    parser, action, args, field, value, sticker_set
):
    client = Client(
        "no-enrichment",
        in_memory=True,
        fetch_replies=False,
        fetch_topics=False,
        fetch_stories=False,
        fetch_stickers=False,
    )
    client.invoke = AsyncMock(side_effect=AssertionError("unexpected Telegram RPC"))
    client.get_messages = AsyncMock(side_effect=AssertionError("unexpected message lookup"))
    channel = raw.types.Channel(
        id=42,
        title="Test",
        photo=raw.types.ChatPhotoEmpty(),
        date=1,
        broadcast=True,
        usernames=[],
        restriction_reason=[],
    )
    message = raw.types.MessageService(
        id=5,
        peer_id=raw.types.PeerChannel(channel_id=42),
        date=1,
        action=action,
        reply_to=raw.types.MessageReplyHeader(reply_to_msg_id=123),
    )
    try:
        parsed = await types.Message._parse(client, message, {}, {42: channel})
        service = getattr(parsed, parsed.service.value)
        assert isinstance(service, parser)
        assert service.sticker is None
        assert getattr(service, field) == value
        assert parsed.chat.id == -1000000000042
        assert parsed.reply_to_message_id == 123
        client.invoke.assert_not_awaited()
        client.get_messages.assert_not_awaited()
    finally:
        client.executor.shutdown(wait=False)
