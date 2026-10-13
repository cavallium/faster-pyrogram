import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyrogram import Client, enums, raw, types
from pyrogram.types.object import Object


class ApiReviewTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = Client("offline", api_id=1, api_hash="0" * 32, in_memory=True)
        await self.client.storage.open()
        self.client.is_connected = True
        self.client.session = SimpleNamespace(invoke=AsyncMock())
        self.user = raw.types.User(id=7, access_hash=70, first_name="Verifier", bot=True)
        self.channel = raw.types.Channel(id=42, access_hash=420, title="Joined",
            date=1, photo=raw.types.ChatPhotoEmpty(), megagroup=True, username="joined")

    async def asyncTearDown(self):
        await self.client.storage.close()

    def result(self, chat):
        return raw.types.messages.ChatInviteJoinResultOk(updates=raw.types.Updates(
            updates=[], users=[self.user], chats=[chat], date=1, seq=1))

    async def test_raw_join_result_retained_and_nested_peers_cached(self):
        result = self.result(self.channel)
        self.client.session.invoke.return_value = result
        self.assertIs(await self.client.invoke(raw.functions.messages.ImportChatInvite(hash="abc")), result)
        peer = await self.client.resolve_peer(-1000000000042)
        self.assertEqual((peer.channel_id, peer.access_hash), (42, 420))
        self.assertEqual((await self.client.resolve_peer(7)).access_hash, 70)
        self.assertEqual((await self.client.resolve_peer("joined")).channel_id, 42)
        self.client.session.invoke.assert_awaited_once()

    async def test_invite_join_parses_group_and_channel_after_peer_caching(self):
        group = raw.types.Chat(id=43, title="Group", photo=raw.types.ChatPhotoEmpty(),
            participants_count=1, date=1, version=1)
        for chat in (group, self.channel):
            with self.subTest(chat=type(chat).__name__):
                self.client.session.invoke.return_value = self.result(chat)
                parsed = await self.client.join_chat("https://t.me/+abc")
                self.assertEqual(parsed.title, chat.title)
                self.assertIsInstance(self.client.session.invoke.call_args.kwargs["query"],
                                      raw.functions.messages.ImportChatInvite)
                self.assertEqual((await self.client.resolve_peer(parsed.id)).chat_id if chat is group
                                 else (await self.client.resolve_peer(parsed.id)).channel_id, chat.id)

    async def test_public_join_caches_response_before_high_level_parse(self):
        await self.client.fetch_peers([self.channel])
        self.client.session.invoke.return_value = self.result(self.channel)
        original = types.Chat._parse_channel_chat
        def parse(client, channel):
            self.assertIsNotNone(client.storage.conn.execute(
                "SELECT id FROM peers WHERE id = ?", (7,)).fetchone())
            return original(client, channel)
        with patch.object(types.Chat, "_parse_channel_chat", side_effect=parse):
            parsed = await self.client.join_chat("joined")
        self.assertEqual(parsed.id, -1000000000042)
        self.assertIsInstance(self.client.session.invoke.call_args.kwargs["query"],
                              raw.functions.channels.JoinChannel)

    async def test_webview_challenge_is_not_reported_as_joined(self):
        challenge = raw.types.messages.ChatInviteJoinResultWebView(bot_id=7, query_id=99, users=[self.user])
        self.client.session.invoke.return_value = challenge
        self.assertIs(await self.client.invoke(raw.functions.messages.ImportChatInvite(hash="abc")), challenge)
        await self.client.fetch_peers([self.channel])
        for chat_id in ("https://t.me/+abc", "joined"):
            with self.subTest(chat_id=chat_id):
                with self.assertRaisesRegex(ValueError, r"WebView.*bot_id=7, query_id=99"):
                    await self.client.join_chat(chat_id)
        self.assertEqual((await self.client.resolve_peer(7)).access_hash, 70)

    async def test_rich_message_str_and_json_keep_nested_raw_data(self):
        rich = raw.types.RichMessage(blocks=[raw.types.PageBlockParagraph(
            text=raw.types.TextPlain(text="Body"))], photos=[], documents=[])
        message = types.Message(id=1, rich_message=rich)
        message.raw = raw.types.PeerUser(user_id=7)
        for encoded in (str(message), json.dumps(message, default=Object.default)):
            data = json.loads(encoded)
            self.assertNotIn("raw", data)
            self.assertEqual(data["rich_message"]["_"], "types.RichMessage")
            self.assertEqual(data["rich_message"]["blocks"][0]["text"]["text"], "Body")
        self.assertEqual(Object.default(b"abc"), "b'abc'")
        self.assertEqual(Object.default(raw.types.PeerUser(user_id=7))["user_id"], 7)

    async def test_verification_description_is_text_with_resolved_entities(self):
        description = raw.types.TextWithEntities(text="Verified by bot", entities=[
            raw.types.MessageEntityBold(offset=0, length=8),
            raw.types.MessageEntityMentionName(offset=12, length=3, user_id=7)])
        verification = raw.types.BotVerification(bot_id=7, icon=123, description=description)
        parsed = types.BotVerification._parse(self.client, verification, {7: self.user})
        self.assertEqual(parsed.description, description.text)
        self.assertIsInstance(parsed.description, str)
        self.assertEqual(parsed.description_entities[0].type, enums.MessageEntityType.BOLD)
        self.assertEqual(parsed.description_entities[1].user.id, 7)
        self.assertEqual(json.loads(str(parsed))["description"], description.text)
        empty = raw.types.BotVerification(bot_id=7, icon=123,
            description=raw.types.TextWithEntities(text="", entities=[]))
        self.assertIsNone(types.BotVerification._parse(self.client, empty, {}).description_entities)
        self.assertIsNone(types.BotVerification._parse(self.client, None, {}))
