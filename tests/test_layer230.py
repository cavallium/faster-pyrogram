import io
import unittest
from unittest.mock import AsyncMock

from pyrogram import Client, enums, raw, types
from pyrogram.raw.core import TLObject


def round_trip(value):
    buffer = io.BytesIO(value.write())
    decoded = TLObject.read(buffer)
    assert not buffer.read()
    return decoded


class Layer230Tests(unittest.IsolatedAsyncioTestCase):
    async def test_inline_keyboard_types_round_trip(self):
        client = Client("offline", api_id=1, api_hash="0" * 32, in_memory=True)
        client.resolve_peer = AsyncMock(return_value=raw.types.InputUserSelf())
        cases = [
            ("callback_data", b"\xff"), ("url", "https://example.com"),
            ("switch_inline_query", ""), ("switch_inline_query_current_chat", "q"),
            ("callback_game", types.CallbackGame()), ("web_app", types.WebAppInfo(url="https://example.com")),
            ("pay", True), ("copy_text", "copy"),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                button = types.InlineKeyboardButton("Button", **{field: value},
                    style=enums.ButtonStyle.PRIMARY, icon_custom_emoji_id="123")
                markup = types.InlineKeyboardMarkup([[button]])
                parsed = types.InlineKeyboardMarkup.read(round_trip(await markup.write(client)))
                result = parsed.inline_keyboard[0][0]
                self.assertEqual(result.text, "Button")
                self.assertEqual(result.style, enums.ButtonStyle.PRIMARY)
                self.assertEqual(result.icon_custom_emoji_id, "123")
                actual = getattr(result, field)
                if field == "web_app":
                    self.assertEqual(actual.url, value.url)
                elif field == "callback_game":
                    self.assertIsInstance(actual, types.CallbackGame)
                else:
                    self.assertEqual(actual, value)

        login = types.InlineKeyboardButton("Login", login_url=types.LoginUrl(url="https://example.com"))
        login_wire = round_trip(await login.write(client))
        self.assertIsInstance(login_wire.type, raw.types.InputInlineButtonTypeUrlAuth)
        profile_wire = round_trip(await types.InlineKeyboardButton("User", user_id=123).write(client))
        self.assertIsInstance(profile_wire.type, raw.types.InputInlineButtonTypeUserProfile)
        received = raw.types.KeyboardInlineButton(text="Login",
            type=raw.types.InlineButtonTypeUrlAuth(url="https://example.com", button_id=7))
        self.assertEqual(types.InlineKeyboardButton.read(round_trip(received)).login_url.button_id, 7)

    async def test_reply_keyboard_types_round_trip(self):
        cases = [types.KeyboardButton("Plain"),
                 types.KeyboardButton("Phone", request_contact=True),
                 types.KeyboardButton("Location", request_location=True),
                 types.KeyboardButton("Poll", request_poll=types.KeyboardButtonPollType(is_quiz=True)),
                 types.KeyboardButton("App", web_app=types.WebAppInfo(url="https://example.com"))]
        for button in cases:
            parsed = types.KeyboardButton.read(round_trip(button.write()))
            self.assertEqual(parsed.text, button.text)
            self.assertEqual(parsed.request_contact, button.request_contact)
            self.assertEqual(parsed.request_location, button.request_location)
            if button.request_poll:
                self.assertTrue(parsed.request_poll.is_quiz)
        requested = types.KeyboardButton("Users", request_users=types.KeyboardButtonRequestUsers(button_id=1))
        self.assertIsInstance(round_trip(requested.write()).type, raw.types.InputButtonTypeRequestPeer)
        received = raw.types.KeyboardButton(text="Users", type=raw.types.ButtonTypeRequestPeer(
            button_id=1, peer_type=raw.types.RequestPeerTypeUser(), max_quantity=2))
        self.assertEqual(types.KeyboardButton.read(round_trip(received)).request_users.max_quantity, 2)

    async def test_current_message_and_community_fields_survive_parse(self):
        self.assertEqual(raw.all.layer, 230)
        client = Client("offline", api_id=1, api_hash="0" * 32, in_memory=True,
                        fetch_replies=False, fetch_topics=False, fetch_stories=False)
        channel = raw.types.Channel(id=42, title="Fixture", date=1,
            photo=raw.types.ChatPhotoEmpty(), megagroup=True, linked_community_id=123)
        rich = raw.types.RichMessage(blocks=[raw.types.PageBlockParagraph(text=raw.types.TextPlain(text="Body"))],
                                     photos=[], documents=[])
        message = round_trip(raw.types.Message(id=1, peer_id=raw.types.PeerChannel(channel_id=42),
            date=1, message="", rich_message=rich))
        parsed = await types.Message._parse(client, message, {}, {42: round_trip(channel)}, replies=0)
        self.assertEqual(parsed.rich_message.blocks[0].text.text, "Body")
        self.assertEqual(parsed.chat.community, {"id": 123, "name": ""})
