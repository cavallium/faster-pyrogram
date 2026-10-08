import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pyrogram import raw
from pyrogram.session import session as session_module


class MessageFactory:
    def __init__(self):
        self.count = 0

    async def create(self, data):
        self.count += 1
        return SimpleNamespace(msg_id=self.count)


class Connection:
    def __init__(self, session, mode, responses):
        self.session = session
        self.mode = mode
        self.responses = list(responses)
        self.protocol = SimpleNamespace(crypto_executor=None)
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.send_count = 0

    async def send(self, payload):
        self.send_count += 1
        self.entered.set()
        if self.mode == "block":
            await self.release.wait()
        if self.mode == "oserror":
            raise OSError("local send failure")
        if self.responses:
            result = self.session.results[self.session.msg_factory.count]
            result.value = self.responses.pop(0)
            result.event.set()


class SessionSendTests(unittest.IsolatedAsyncioTestCase):
    def make_session(self, mode="idle", responses=()):
        session = session_module.Session.__new__(session_module.Session)
        session.client = SimpleNamespace(loop=asyncio.get_running_loop())
        session.msg_factory = MessageFactory()
        session.results = {}
        session._state = session_module.SessionState.STARTED
        session.is_started = asyncio.Event()
        session.is_started.set()
        session.transport_send_failures = 0
        session.restart_requests_ignored = 0
        session.salt = 7
        session.session_id = 8
        session.auth_key = b"local-key"
        session.auth_key_id = 9
        session.connection = Connection(session, mode, responses)
        return session

    async def wait_for_response_waiter(self, session):
        async def ready():
            while True:
                result = session.results.get(session.msg_factory.count)
                if result is not None and result.event._waiters:
                    return result
                await asyncio.sleep(0)

        return await asyncio.wait_for(ready(), 1)

    def assert_clean(self, session, sends, result=None):
        self.assertEqual(session.results, {})
        self.assertEqual(session.connection.send_count, sends)
        self.assertEqual(len(session.connection.release._waiters), 0)
        if result is not None:
            self.assertEqual(len(result.event._waiters), 0)

    def bad_salt(self):
        return raw.types.BadServerSalt(
            bad_msg_id=1, bad_msg_seqno=1, error_code=48, new_server_salt=99
        )

    async def test_cancel_blocked_connection_send(self):
        session = self.make_session(mode="block")
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            task = asyncio.create_task(session.send(object()))
            await asyncio.wait_for(session.connection.entered.wait(), 1)
            result = session.results[1]
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        self.assert_clean(session, 1, result)

    async def test_cancel_response_wait(self):
        session = self.make_session()
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            task = asyncio.create_task(session.send(object()))
            result = await self.wait_for_response_waiter(session)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        self.assert_clean(session, 1, result)

    async def test_connection_send_oserror(self):
        session = self.make_session(mode="oserror")
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            with self.assertRaisesRegex(OSError, "local send failure"):
                await asyncio.wait_for(session.send(object()), 1)
        self.assert_clean(session, 1)

    async def test_packing_exception(self):
        session = self.make_session()
        with patch.object(session_module.mtproto, "pack", side_effect=ValueError("local pack failure")):
            with self.assertRaisesRegex(ValueError, "local pack failure"):
                await asyncio.wait_for(session.send(object()), 1)
        self.assert_clean(session, 0)

    async def test_normal_response(self):
        session = self.make_session(responses=("success",))
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            self.assertEqual(await asyncio.wait_for(session.send(object()), 1), "success")
        self.assert_clean(session, 1)

    async def test_normal_timeout(self):
        session = self.make_session()
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            with self.assertRaisesRegex(TimeoutError, "Request timed out"):
                await asyncio.wait_for(session.send(object(), timeout=0.01), 1)
        self.assert_clean(session, 1)

    async def test_bad_salt_then_normal_response(self):
        session = self.make_session(responses=(self.bad_salt(), "retry-success"))
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            self.assertEqual(await asyncio.wait_for(session.send(object()), 1), "retry-success")
        self.assert_clean(session, 2)
        self.assertEqual(session.salt, 99)

    async def test_bad_salt_then_cancel_response_wait(self):
        session = self.make_session(responses=(self.bad_salt(),))
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            task = asyncio.create_task(session.send(object()))
            result = await self.wait_for_response_waiter(session)
            self.assertEqual(list(session.results), [2])
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        self.assert_clean(session, 2, result)
        self.assertEqual(session.salt, 99)

    async def test_repeated_cancellation_does_not_grow_results(self):
        session = self.make_session()
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            for count in range(1, 21):
                task = asyncio.create_task(session.send(object()))
                result = await self.wait_for_response_waiter(session)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 1)
                self.assert_clean(session, count, result)

    async def test_cancel_preserves_replacement_registration(self):
        session = self.make_session()
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            task = asyncio.create_task(session.send(object()))
            result = await self.wait_for_response_waiter(session)
            replacement = session_module.Result()
            session.results[1] = replacement
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        self.assertIs(session.results[1], replacement)
        self.assertEqual(len(result.event._waiters), 0)
        self.assertEqual(session.connection.send_count, 1)

    async def test_send_without_response(self):
        session = self.make_session()
        with patch.object(session_module.mtproto, "pack", return_value=b"local"):
            self.assertIsNone(await asyncio.wait_for(session.send(object(), wait_response=False), 1))
        self.assert_clean(session, 1)
