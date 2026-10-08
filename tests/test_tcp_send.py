import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pyrogram import raw
from pyrogram.connection import Connection
from pyrogram.connection.transport.tcp.tcp import TCP
from pyrogram.connection.transport.tcp.tcp_abridged import TCPAbridged
from pyrogram.raw.core import Message, MsgContainer
from pyrogram.session import session as session_module
from pyrogram.session.internals import MsgFactory


class TCPSendTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.transports = []

    def tearDown(self):
        for transport in self.transports:
            transport.crypto_executor.shutdown(wait=True, cancel_futures=True)

    def writer(self, closing=False):
        return SimpleNamespace(is_closing=Mock(return_value=closing), write=Mock(), drain=AsyncMock())

    def transport(self, writer=None, marker=True, cls=TCP):
        transport = cls(loop=asyncio.get_running_loop())
        transport.writer = writer
        if marker:
            transport.marker_event.set()
        self.transports.append(transport)
        return transport

    def session(self, transport):
        session = session_module.Session.__new__(session_module.Session)
        session.client = SimpleNamespace(loop=asyncio.get_running_loop(), server_time=1790000000)
        session.msg_factory = MsgFactory(session.client)
        session.results = {}
        session.salt = 7
        session.session_id = 8
        session.auth_key = b'0' * 256
        session.auth_key_id = 9
        session.pending_acks = set()
        session.connection = Connection(2, '127.0.0.1', 1, True, loop=session.client.loop)
        session.connection.protocol = transport
        return session

    async def wait_until(self, predicate):
        async def wait():
            while not predicate():
                await asyncio.sleep(0)
        await asyncio.wait_for(wait(), 1)

    def respond(self, session, value='success'):
        pending = session.results[session.msg_factory._last_msg_id]
        pending.value = value
        pending.event.set()

    async def test_missing_and_closing_writer_raise_plain_oserror_without_writes(self):
        for writer in (None, self.writer(closing=True)):
            with self.subTest(writer=writer):
                transport = self.transport(writer)
                with self.assertRaisesRegex(OSError, '^TCP transport is not connected$') as error:
                    await transport.send(b'data')
                self.assertIs(type(error.exception), OSError)
                if writer is not None:
                    writer.write.assert_not_called()
                    writer.drain.assert_not_awaited()
                self.assertFalse(transport.lock.locked())

    async def test_connection_send_propagates_disconnected_error(self):
        transport = self.transport()
        session = self.session(transport)
        with self.assertRaisesRegex(OSError, '^TCP transport is not connected$') as error:
            await session.connection.send(b'data')
        self.assertIs(type(error.exception), OSError)
        self.assertEqual({}, session.results)

    async def test_healthy_writer_writes_and_drains_once(self):
        writer = self.writer()
        transport = self.transport(writer)
        await transport.send(b'data')
        writer.write.assert_called_once_with(b'data')
        writer.drain.assert_awaited_once()
        self.assertFalse(transport.lock.locked())

    async def test_session_send_failure_cleans_only_its_response_registration(self):
        for writer in (None, self.writer(closing=True)):
            with self.subTest(writer=writer):
                session = self.session(self.transport(writer))
                other = session.results[123] = session_module.Result()
                with patch.object(session_module.mtproto, 'pack', return_value=b'data') as pack:
                    with self.assertRaisesRegex(OSError, '^TCP transport is not connected$') as error:
                        await session.send(raw.functions.Ping(ping_id=1), timeout=0.01)
                self.assertIs(type(error.exception), OSError)
                self.assertEqual({123: other}, session.results)
                pack.assert_called_once()

    async def test_failed_ack_transmission_retains_ids_until_healthy_send(self):
        transport = self.transport()
        session = self.session(transport)
        ack_ids = set(range(10))
        session.pending_acks.update(ack_ids)
        packet = Message(MsgContainer([]), 1, 0, 0)
        with patch.object(session_module.mtproto, 'unpack', return_value=packet), \
             patch.object(session_module.mtproto, 'pack', return_value=b'data') as pack:
            await session.handle_packet(b'fixture')
            self.assertEqual(ack_ids, session.pending_acks)
            self.assertEqual({}, session.results)
            writer = transport.writer = self.writer()
            await session.handle_packet(b'fixture')
        self.assertEqual(set(), session.pending_acks)
        self.assertEqual({}, session.results)
        self.assertEqual(2, pack.call_count)
        for args in pack.call_args_list:
            self.assertIsInstance(args.args[0].body, raw.types.MsgsAck)
            self.assertEqual(ack_ids, set(args.args[0].body.msg_ids))
        writer.write.assert_called_once_with(b'data')
        writer.drain.assert_awaited_once()

    async def test_cancellation_at_lock_marker_and_drain_cleans_registration(self):
        for stage in ('lock', 'marker', 'drain'):
            with self.subTest(stage=stage):
                writer = self.writer()
                transport = self.transport(writer, marker=stage != 'marker')
                session = self.session(transport)
                entered = asyncio.Event()
                if stage == 'lock':
                    await transport.lock.acquire()
                if stage == 'drain':
                    async def drain():
                        entered.set()
                        await asyncio.Future()
                    writer.drain.side_effect = drain
                try:
                    with patch.object(session_module.mtproto, 'pack', return_value=b'data'):
                        task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
                        if stage == 'lock':
                            await self.wait_until(lambda: transport.lock._waiters)
                        elif stage == 'marker':
                            await self.wait_until(lambda: transport.marker_event._waiters)
                        else:
                            await asyncio.wait_for(entered.wait(), 1)
                        pending = session.results[session.msg_factory._last_msg_id]
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await asyncio.wait_for(task, 1)
                    self.assertEqual({}, session.results)
                    self.assertFalse(pending.event._waiters)
                    self.assertEqual(int(stage == 'drain'), writer.write.call_count)
                    self.assertEqual(int(stage == 'drain'), writer.drain.await_count)
                finally:
                    if stage == 'lock':
                        transport.lock.release()
                self.assertFalse(transport.lock.locked())

    async def test_cancelled_send_preserves_replacement_registration(self):
        transport = self.transport(self.writer())
        session = self.session(transport)
        await transport.lock.acquire()
        try:
            with patch.object(session_module.mtproto, 'pack', return_value=b'data'):
                task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
                await self.wait_until(lambda: transport.lock._waiters)
                msg_id = session.msg_factory._last_msg_id
                replacement = session.results[msg_id] = session_module.Result()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 1)
            self.assertEqual({msg_id: replacement}, session.results)
            transport.writer.write.assert_not_called()
        finally:
            transport.lock.release()

    async def test_cancellation_during_packing_cleans_registration_without_write(self):
        transport = self.transport(self.writer())
        session = self.session(transport)
        entered = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        def pack(*args):
            loop.call_soon_threadsafe(entered.set)
            release.wait(2)
            return b'data'
        try:
            with patch.object(session_module.mtproto, 'pack', side_effect=pack):
                task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
                await asyncio.wait_for(entered.wait(), 1)
                self.assertEqual(1, len(session.results))
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 1)
            self.assertEqual({}, session.results)
            transport.writer.write.assert_not_called()
            transport.writer.drain.assert_not_awaited()
        finally:
            release.set()

    async def test_writer_is_checked_after_lock_acquisition(self):
        old = self.writer()
        transport = self.transport(old)
        await transport.lock.acquire()
        task = asyncio.create_task(transport.send(b'data'))
        await self.wait_until(lambda: transport.lock._waiters)
        replacement = transport.writer = self.writer()
        transport.lock.release()
        await asyncio.wait_for(task, 1)
        old.write.assert_not_called()
        replacement.write.assert_called_once_with(b'data')
        replacement.drain.assert_awaited_once()

    async def test_explicit_connection_reconnect_resumes_new_requests_without_replay(self):
        old = self.transport(cls=TCPAbridged)
        session = self.session(old)
        packed = []
        def pack(message, *args):
            packed.append(message.body.ping_id)
            return b'data'
        def factory(**kwargs):
            transport = TCPAbridged(**kwargs)
            self.transports.append(transport)
            return transport
        session.connection.protocol_factory = factory
        writer = self.writer()
        async def connect(transport, address):
            self.assertEqual(('127.0.0.1', 1), address)
            transport.writer = writer
        with patch.object(session_module.mtproto, 'pack', side_effect=pack), \
             patch.object(TCP, '_connect', new=connect):
            with self.assertRaisesRegex(OSError, 'TCP transport is not connected'):
                await session.send(raw.functions.Ping(ping_id=1), timeout=0.01)
            self.assertEqual({}, session.results)
            self.assertEqual([old], self.transports)  # No hidden reconnect on send failure.
            await session.connection.connect()
            self.assertIsNot(old, session.connection.protocol)
            self.assertTrue(session.connection.protocol.marker_event.is_set())
            writer.drain.side_effect = lambda: self.respond(session)
            self.assertEqual('success', await session.send(raw.functions.Ping(ping_id=2)))
        self.assertEqual([1, 2], packed)  # Failed request was not replayed.
        self.assertEqual([b'\xef', b'\x01data'], [args.args[0] for args in writer.write.call_args_list])
        self.assertEqual(2, writer.drain.await_count)
        self.assertEqual({}, session.results)
