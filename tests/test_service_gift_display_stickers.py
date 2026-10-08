import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pyrogram
from pyrogram import raw, types
from pyrogram.errors import ChannelPrivate, MessageIdsEmpty


FAMILIES = ('premium_gift_code', 'gifted_premium', 'gifted_stars', 'gifted_ton', 'giveaway_prize_stars')


class ServiceGiftDisplayStickerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.users = {user_id: raw.types.User(id=user_id, first_name=f'User{user_id}',
            usernames=[], restriction_reason=[]) for user_id in (11, 12)}
        self.chats = {42: raw.types.Channel(id=42, title='Boosted', date=1, broadcast=True,
            photo=raw.types.ChatPhotoEmpty(), restriction_reason=[], usernames=[])}
        self.documents = [raw.types.Document(id=document_id, access_hash=123, file_reference=b'fixture',
            date=1, mime_type='image/webp', size=1234, dc_id=2, thumbs=[], video_thumbs=[], attributes=[
                raw.types.DocumentAttributeSticker(alt='gift', stickerset=raw.types.InputStickerSetShortName(short_name='fixture')),
                raw.types.DocumentAttributeImageSize(w=512, h=512),
                raw.types.DocumentAttributeFilename(file_name='gift.webp')]) for document_id in (101, 102)]
        self.reference = types.Message(id=77)

    def action(self, family):
        text = raw.types.TextWithEntities(text='Gift caption', entities=[raw.types.MessageEntityBold(offset=0, length=4)])
        if family == 'premium_gift_code':
            return raw.types.MessageActionGiftCode(days=93, slug='fixture-code', via_giveaway=True,
                unclaimed=True, boost_peer=raw.types.PeerChannel(channel_id=42), currency='EUR',
                amount=1234, crypto_currency='TON', crypto_amount=987654321, message=text)
        if family == 'gifted_premium':
            return raw.types.MessageActionGiftPremium(currency='EUR', amount=1234, days=93,
                crypto_currency='TON', crypto_amount=987654321, message=text)
        if family == 'gifted_stars':
            return raw.types.MessageActionGiftStars(currency='EUR', amount=1234, stars=456,
                crypto_currency='TON', crypto_amount=987654321, transaction_id='stars-transaction')
        if family == 'gifted_ton':
            return raw.types.MessageActionGiftTon(currency='EUR', amount=1234, crypto_currency='TON',
                crypto_amount=987654321, transaction_id='ton-transaction')
        return raw.types.MessageActionPrizeStars(stars=456, transaction_id='prize-transaction',
            boost_peer=raw.types.PeerChannel(channel_id=42), giveaway_msg_id=77, unclaimed=True)

    async def parse(self, family, fetch_stickers, reference_error=None, flip_stickers=None):
        options = {} if fetch_stickers is None else {'fetch_stickers': fetch_stickers}
        client = pyrogram.Client('offline-gift-display', api_id=1, api_hash='0' * 32,
            in_memory=True, fetch_replies=False, **options)
        events = []
        async def invoke(query):
            self.assertIsInstance(query, raw.functions.messages.GetStickerSet)
            expected = raw.types.InputStickerSetTonGifts if family == 'gifted_ton' else raw.types.InputStickerSetPremiumGifts
            self.assertIsInstance(query.stickerset, expected)
            self.assertEqual(0, query.hash)
            events.append('sticker_set')
            return SimpleNamespace(documents=self.documents)
        async def reference(**kwargs):
            events.append('reference')
            if flip_stickers is not None:
                client.fetch_stickers = flip_stickers
            if reference_error is not None:
                raise reference_error
            return self.reference
        def choose(stickers):
            events.append('choice')
            self.assertEqual(2, len(stickers))
            self.assertTrue(all(isinstance(s, types.Sticker) for s in stickers))
            return stickers[-1]
        client.invoke = AsyncMock(side_effect=invoke)
        client.get_messages = AsyncMock(side_effect=reference)
        message = raw.types.MessageService(id=99, date=1790000000,
            peer_id=raw.types.PeerUser(user_id=12), from_id=raw.types.PeerUser(user_id=11),
            action=self.action(family))
        with patch(f'pyrogram.types.messages_and_media.{family}.random.choice', side_effect=choose) as choice:
            parsed = await types.Message._parse(client, message, self.users, self.chats)
        self.assertEqual(99, parsed.id)
        self.assertEqual(datetime.fromtimestamp(1790000000), parsed.date)
        result = getattr(parsed, family)
        self.assertIsNotNone(result)
        if family == 'giveaway_prize_stars':
            client.get_messages.assert_awaited_once_with(chat_id=-1000000000042, message_ids=77, replies=0)
        else:
            client.get_messages.assert_not_awaited()
        return result, client, choice, events

    def assert_business_fields(self, family, result):
        if family == 'premium_gift_code':
            self.assertEqual(-1000000000042, result.creator.id)
            self.assertEqual('Gift caption', result.text.text)
            self.assertEqual(4, result.text.entities[0].length)
            self.assertTrue(result.is_from_giveaway)
            self.assertTrue(result.is_unclaimed)
            self.assertEqual('fixture-code', result.code)
            self.assertEqual('https://t.me/giftcode/fixture-code', result.link)
        elif family != 'giveaway_prize_stars':
            self.assertEqual(11, result.gifter.id)
            self.assertEqual(12, result.receiver.id)
        if family in ('premium_gift_code', 'gifted_premium', 'gifted_stars'):
            self.assertEqual(('EUR',1234,'TON',987654321),
                (result.currency,result.amount,result.cryptocurrency,result.cryptocurrency_amount))
        if family in ('premium_gift_code', 'gifted_premium'):
            self.assertEqual((93,3), (result.day_count,result.month_count))
        if family == 'gifted_premium':
            self.assertEqual('Gift caption', result.caption)
            self.assertEqual(4, result.caption_entities[0].length)
        if family == 'gifted_stars':
            self.assertEqual((456,'stars-transaction'), (result.star_count,result.transaction_id))
        if family == 'gifted_ton':
            self.assertEqual((987654321,'ton-transaction'), (result.ton_amount,result.transaction_id))
        if family == 'giveaway_prize_stars':
            self.assertEqual((456,'prize-transaction',77),
                (result.star_count,result.transaction_id,result.giveaway_message_id))
            self.assertEqual(-1000000000042, result.boosted_chat.id)
            self.assertIs(self.reference, result.giveaway_message)

    async def test_disabled_skips_display_rpc_parse_and_random_choice_for_all_families(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                result, client, choice, events = await self.parse(family, False)
                self.assertIsNone(result.sticker)
                client.invoke.assert_not_awaited()
                choice.assert_not_called()
                self.assertEqual(['reference'] if family == 'giveaway_prize_stars' else [], events)
                self.assert_business_fields(family, result)

    async def test_enabled_and_default_keep_original_sticker_rpc_and_selection(self):
        for family in FAMILIES:
            for enabled in (True, None):
                with self.subTest(family=family, enabled=enabled):
                    result, client, choice, events = await self.parse(family, enabled)
                    self.assertTrue(client.fetch_stickers)
                    client.invoke.assert_awaited_once()
                    choice.assert_called_once()
                    self.assertEqual('gift.webp', result.sticker.file_name)
                    self.assertEqual('gift', result.sticker.emoji)
                    self.assertIs(self.documents[-1], result.sticker.raw)
                    self.assertEqual(['sticker_set', 'reference', 'choice'] if family == 'giveaway_prize_stars'
                        else ['sticker_set', 'choice'], events)
                    self.assert_business_fields(family, result)

    async def test_enabled_and_disabled_outputs_differ_only_in_display_sticker(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                disabled, *_ = await self.parse(family, False)
                enabled, *_ = await self.parse(family, True)
                self.assertIsNotNone(enabled.sticker)
                enabled.sticker = None
                self.assertEqual(enabled, disabled)

    async def test_prize_reference_failure_remains_optional_for_both_sticker_modes(self):
        for enabled in (False, True):
            for error in (MessageIdsEmpty(), ChannelPrivate()):
                with self.subTest(enabled=enabled, error=type(error).__name__):
                    result, client, choice, events = await self.parse('giveaway_prize_stars', enabled, error)
                    self.assertIsNone(result.giveaway_message)
                    self.assertEqual(77, result.giveaway_message_id)
                    self.assertEqual(456, result.star_count)
                    self.assertEqual('prize-transaction', result.transaction_id)
                    self.assertEqual(int(enabled), client.invoke.await_count)
                    self.assertEqual(int(enabled), choice.call_count)

    async def test_enabled_sticker_request_propagates_owner_task_cancellation(self):
        for family in FAMILIES:
            with self.subTest(family=family):
                client = pyrogram.Client('offline-gift-cancel', api_id=1, api_hash='0' * 32,
                    in_memory=True, fetch_replies=False, fetch_stickers=True)
                entered = asyncio.Event()
                async def invoke(query):
                    self.assertIsInstance(query, raw.functions.messages.GetStickerSet)
                    entered.set()
                    await asyncio.Future()
                client.invoke = AsyncMock(side_effect=invoke)
                client.get_messages = AsyncMock(side_effect=AssertionError('unexpected reference lookup after cancellation'))
                message = raw.types.MessageService(id=99, date=1790000000,
                    peer_id=raw.types.PeerUser(user_id=12), from_id=raw.types.PeerUser(user_id=11),
                    action=self.action(family))
                with patch(f'pyrogram.types.messages_and_media.{family}.random.choice') as choice:
                    task = asyncio.create_task(types.Message._parse(client, message, self.users, self.chats))
                    await asyncio.wait_for(entered.wait(), 1)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertTrue(task.cancelled())
                client.invoke.assert_awaited_once()
                client.get_messages.assert_not_awaited()
                choice.assert_not_called()

    async def test_prize_sticker_decision_uses_entry_flag_during_reference_lookup(self):
        for initial in (False, True):
            with self.subTest(initial=initial):
                result, client, choice, events = await self.parse('giveaway_prize_stars', initial,
                    flip_stickers=not initial)
                self.assertEqual(not initial, client.fetch_stickers)
                self.assertEqual(initial, result.sticker is not None)
                self.assertEqual(int(initial), client.invoke.await_count)
                self.assertEqual(int(initial), choice.call_count)
                self.assertEqual(['sticker_set', 'reference', 'choice'] if initial else ['reference'], events)
                self.assert_business_fields('giveaway_prize_stars', result)
