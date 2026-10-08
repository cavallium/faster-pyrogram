import unittest
from datetime import datetime
from unittest.mock import AsyncMock, call

import pyrogram
from pyrogram import enums, raw, types
from pyrogram.errors import MessageIdsEmpty


class SuggestedPostPaidTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = pyrogram.Client('offline-suggested-payment', api_id=1,
                                      api_hash='0' * 32, in_memory=True, fetch_replies=False)
        self.client.get_messages = AsyncMock()
        self.client.invoke = AsyncMock(side_effect=AssertionError('unexpected Telegram RPC'))
        self.channel = raw.types.Channel(id=42, title='offline', date=1, broadcast=True,
            photo=raw.types.ChatPhotoEmpty(), restriction_reason=[], usernames=[])

    def message(self, price):
        return raw.types.MessageService(id=99, peer_id=raw.types.PeerChannel(channel_id=42),
            date=1_790_000_000, action=raw.types.MessageActionSuggestedPostSuccess(price=price),
            reply_to=raw.types.MessageReplyHeader(reply_to_msg_id=77))

    async def parse(self, message, replies=1):
        return await types.Message._parse(self.client, message, {}, {42: self.channel}, replies=replies)

    def assert_service(self, message):
        self.assertEqual(99, message.id)
        self.assertEqual(datetime.fromtimestamp(1_790_000_000), message.date)
        self.assertEqual(-1000000000042, message.chat.id)
        self.assertEqual(enums.MessageServiceType.SUGGESTED_POST_PAID, message.service)
        self.assertEqual(77, message.suggested_post_paid.suggested_post_message_id)
        self.assertEqual(77, message.reply_to_message_id)

    async def test_ton_service_preserves_exact_amount_and_header_without_rpc(self):
        for amount in (1, 1_234_567_890, 9_223_372_036_854_775_807):
            with self.subTest(amount=amount):
                message = await self.parse(self.message(raw.types.StarsTonAmount(amount=amount)))
                self.assert_service(message)
                self.assertEqual(amount, message.suggested_post_paid.amount)
                self.assertIsNone(message.suggested_post_paid.star_amount)
                self.assertIsNone(message.suggested_post_paid.suggested_post_message)
        self.client.get_messages.assert_not_awaited()
        self.client.invoke.assert_not_awaited()

    async def test_stars_service_preserves_stars_and_nanostars_without_rpc(self):
        message = await self.parse(self.message(raw.types.StarsAmount(amount=123, nanos=987_654_321)))
        self.assert_service(message)
        self.assertIsNone(message.suggested_post_paid.amount)
        self.assertEqual(123, message.suggested_post_paid.star_amount.star_count)
        self.assertEqual(987_654_321, message.suggested_post_paid.star_amount.nanostar_count)
        self.client.get_messages.assert_not_awaited()
        self.client.invoke.assert_not_awaited()

    async def test_enabled_replies_preserve_both_existing_lookups(self):
        self.client.fetch_replies = True
        suggested = types.Message(id=77)
        self.client.get_messages.return_value = suggested
        message = await self.parse(self.message(raw.types.StarsTonAmount(amount=123)))
        self.assert_service(message)
        self.assertIs(suggested, message.suggested_post_paid.suggested_post_message)
        self.assertIs(suggested, message.reply_to_message)
        self.assertEqual([call(chat_id=-1000000000042, message_ids=77),
                          call(replies=0, chat_id=-1000000000042, message_ids=99, reply=True)],
                         self.client.get_messages.await_args_list)
        self.client.invoke.assert_not_awaited()

    async def test_zero_reply_depth_keeps_enabled_suggested_message_lookup(self):
        self.client.fetch_replies = True
        suggested = types.Message(id=77)
        self.client.get_messages.return_value = suggested
        message = await self.parse(self.message(raw.types.StarsTonAmount(amount=123)), replies=0)
        self.assert_service(message)
        self.assertIs(suggested, message.suggested_post_paid.suggested_post_message)
        self.client.get_messages.assert_awaited_once_with(chat_id=-1000000000042, message_ids=77)
        self.client.invoke.assert_not_awaited()

    async def test_unavailable_optional_reply_keeps_payment(self):
        self.client.fetch_replies = True
        self.client.get_messages.side_effect = MessageIdsEmpty()
        message = await self.parse(self.message(raw.types.StarsTonAmount(amount=123)), replies=0)
        self.assert_service(message)
        self.assertEqual(123, message.suggested_post_paid.amount)
        self.assertIsNone(message.suggested_post_paid.suggested_post_message)
        self.client.get_messages.assert_awaited_once_with(chat_id=-1000000000042, message_ids=77)
        self.client.invoke.assert_not_awaited()

    async def test_wrong_action_keeps_existing_none_result(self):
        message = self.message(raw.types.StarsTonAmount(amount=1))
        message.action = raw.types.MessageActionEmpty()
        self.assertIsNone(await types.SuggestedPostPaid._parse(self.client, message))
        self.client.get_messages.assert_not_awaited()
        self.client.invoke.assert_not_awaited()
