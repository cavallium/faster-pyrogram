import asyncio
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pyrogram import raw
from pyrogram.connection import Connection
from pyrogram.connection.transport.tcp.tcp import TCP
from pyrogram.connection.transport.tcp.tcp_abridged import TCPAbridged
from pyrogram.errors import InternalServerError, HistoryGetFailed
from pyrogram.raw.core import Message, MsgContainer
from pyrogram.session import session as sdk


class TaskLoop:
    def __init__(self):
        self.loop = asyncio.get_running_loop()
        self.tasks = []
        self.executors = []

    def create_task(self, coroutine):
        task = self.loop.create_task(coroutine)
        self.tasks.append(task)
        return task

    def run_in_executor(self, executor, function, *args):
        self.executors.append(executor)
        return self.loop.run_in_executor(executor, function, *args)


class SessionRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.loop = TaskLoop()
        self.transports = []
        self.releases = []

    async def asyncTearDown(self):
        for release in self.releases:
            release.set()
        for task in self.loop.tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.loop.tasks, return_exceptions=True)
        for transport in self.transports:
            transport.crypto_executor.shutdown(wait=True, cancel_futures=True)

    def writer(self, closing=False):
        return SimpleNamespace(is_closing=Mock(return_value=closing), write=Mock(), drain=AsyncMock(),
            transport=SimpleNamespace(abort=Mock()), close=Mock(), wait_closed=AsyncMock())

    def connection(self, writer=None, cls=TCP):
        transport = cls(loop=self.loop.loop)
        transport.writer = writer
        transport.marker_event.set()
        self.transports.append(transport)
        connection = Connection(2, '127.0.0.1', 1, True, loop=self.loop.loop)
        connection.protocol = transport
        return connection

    def session(self, connection=None):
        client = SimpleNamespace(loop=self.loop, server_time=1790000000, name='offline',
            disconnect_handler=None, connect_handler=None, _set_server_time=Mock(), handle_updates=AsyncMock(),
            proxy=None, protocol_factory=TCP)
        session = sdk.Session(client, 2, '127.0.0.1', 1, b'0' * 256, True)
        session.connection = connection or self.connection()
        session._state = sdk.SessionState.STARTED
        session.is_started.set()
        return session

    async def wait_until(self, predicate):
        async def wait():
            while not predicate():
                await asyncio.sleep(0)
        await asyncio.wait_for(wait(), 1)

    def blocked_crypto(self, result=None, error=None):
        entered = asyncio.Event()
        release = threading.Event()
        self.releases.append(release)
        def function(*args):
            self.loop.loop.call_soon_threadsafe(entered.set)
            release.wait(2)
            if error is not None:
                raise error
            return result
        return function, entered, release

    async def settle_tasks(self):
        await asyncio.gather(*list(self.loop.tasks))

    async def test_closing_writer_is_aborted_closed_and_forgotten(self):
        writer = self.writer(closing=True)
        connection = self.connection(writer)
        await connection.close()
        writer.transport.abort.assert_called_once()
        writer.close.assert_called_once()
        writer.wait_closed.assert_awaited_once()
        self.assertIsNone(connection.protocol.writer)

    async def test_close_cancellation_at_lock_and_wait_propagates(self):
        for stage in ('lock', 'wait'):
            with self.subTest(stage=stage):
                writer = self.writer(closing=True)
                transport = self.connection(writer).protocol
                entered = asyncio.Event()
                if stage == 'lock':
                    await transport.lock.acquire()
                else:
                    async def wait_closed():
                        entered.set()
                        await asyncio.Future()
                    writer.wait_closed.side_effect = wait_closed
                task = asyncio.create_task(transport.close())
                try:
                    if stage == 'lock':
                        await self.wait_until(lambda: transport.lock._waiters)
                    else:
                        await asyncio.wait_for(entered.wait(), 1)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertIs(writer if stage == 'lock' else None, transport.writer)
                finally:
                    if stage == 'lock':
                        transport.lock.release()
                self.assertFalse(transport.lock.locked())

    async def test_send_clears_readiness_before_close_wait_and_cancel_still_cleans_result(self):
        writer = self.writer(closing=True)
        session = self.session(self.connection(writer))
        entered = asyncio.Event()
        async def wait_closed():
            self.assertFalse(session.is_started.is_set())
            self.assertEqual(sdk.SessionState.STARTED, session.state)
            entered.set()
            await asyncio.Future()
        writer.wait_closed.side_effect = wait_closed
        with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
            task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertEqual({}, session.results)
        self.assertEqual(1, session.transport_send_failures)
        self.assertIsNone(session.connection.protocol.writer)
        writer.write.assert_not_called()

    async def test_send_cancelled_waiting_for_close_lock_preserves_readiness_fence(self):
        writer = self.writer(closing=True)
        session = self.session(self.connection(writer))
        transport = session.connection.protocol
        await transport.lock.acquire()
        entered, release = asyncio.Event(), asyncio.Event()
        async def blocker():
            async with transport.lock:
                entered.set()
                await release.wait()
        with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
            task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
            await self.wait_until(lambda: transport.lock._waiters)
            blocked = asyncio.create_task(blocker())
            await self.wait_until(lambda: len(transport.lock._waiters) == 2)
            transport.lock.release()
            try:
                await asyncio.wait_for(entered.wait(), 1)
                await self.wait_until(lambda: transport.lock._waiters)
                self.assertFalse(session.is_started.is_set())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            finally:
                release.set()
                await blocked
        self.assertEqual({}, session.results)
        self.assertEqual(1, session.transport_send_failures)

    async def test_ordinary_close_error_does_not_mask_send_error_or_delete_replacement_result(self):
        connection = self.connection(self.writer(closing=True))
        session = self.session(connection)
        transport = connection.protocol
        connection.close = AsyncMock(side_effect=ValueError('close failure'))
        await transport.lock.acquire()
        try:
            with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
                task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
                await self.wait_until(lambda: transport.lock._waiters)
                msg_id = session.msg_factory._last_msg_id
                replacement = session.results[msg_id] = sdk.Result()
                transport.lock.release()
                with self.assertRaisesRegex(OSError, '^TCP transport is not connected$'):
                    await task
            self.assertEqual({msg_id: replacement}, session.results)
            self.assertFalse(session.is_started.is_set())
            self.assertEqual(1, session.transport_send_failures)
        finally:
            if transport.lock.locked():
                transport.lock.release()

    async def test_capture_precedes_message_factory_and_crypto_awaits(self):
        for stage in ('factory', 'pack'):
            with self.subTest(stage=stage):
                old_writer = self.writer(closing=True)
                old = self.connection(old_writer)
                session = self.session(old)
                replacement_writer = self.writer()
                replacement = self.connection(replacement_writer)
                if stage == 'factory':
                    entered, release = asyncio.Event(), asyncio.Event()
                    original = session.msg_factory.create
                    async def create(data):
                        entered.set()
                        await release.wait()
                        return await original(data)
                    session.msg_factory.create = create
                    pack = lambda *args: b'data'
                else:
                    pack, entered, release = self.blocked_crypto(b'data')
                with patch.object(sdk.mtproto, 'pack', side_effect=pack):
                    task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=1)))
                    await asyncio.wait_for(entered.wait(), 1)
                    session.connection = replacement
                    session.pending_acks = {999}
                    release.set()
                    with self.assertRaisesRegex(OSError, 'TCP transport is not connected'):
                        await task
                self.assertTrue(session.is_started.is_set())
                self.assertEqual({999}, session.pending_acks)
                self.assertEqual({}, session.results)
                self.assertIs(old.protocol.crypto_executor, self.loop.executors[-1])
                old_writer.transport.abort.assert_called_once()
                replacement_writer.transport.abort.assert_not_called()
                replacement_writer.write.assert_not_called()

    async def test_delayed_recv_and_ping_restart_only_one_generation_after_readiness_clear(self):
        writer = self.writer(closing=True)
        old = self.connection(writer, TCPAbridged)
        session = self.session(old)
        recv_entered, eof = asyncio.Event(), asyncio.Event()
        async def read(length):
            recv_entered.set()
            await eof.wait()
            return b''
        old.protocol.reader = SimpleNamespace(read=AsyncMock(side_effect=read))
        session.recv_task = asyncio.create_task(session.recv_worker())
        await asyncio.wait_for(recv_entered.wait(), 1)
        replacement = self.connection(self.writer())
        async def start():
            session.connection = replacement
            session._state = sdk.SessionState.STARTED
            session.is_started.set()
        session.start = AsyncMock(side_effect=start)
        await session.restart_lock.acquire()
        try:
            with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
                with self.assertRaisesRegex(OSError, 'TCP transport is not connected'):
                    await session.send(raw.functions.Ping(ping_id=1))
                self.assertFalse(session.is_started.is_set())
                self.assertEqual(sdk.SessionState.STARTED, session.state)
                self.assertFalse(session.recv_task.done())
                session.PING_INTERVAL = 0.001
                session.ping_task = asyncio.create_task(session.ping_worker())
                await asyncio.wait_for(session.ping_task, 1)
                eof.set()
                await asyncio.wait_for(session.recv_task, 1)
                self.assertEqual(2, len(self.loop.tasks))
        finally:
            session.restart_lock.release()
        await self.settle_tasks()
        session.start.assert_awaited_once()
        self.assertIs(replacement, session.connection)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual(1, session.restart_requests_ignored)
        self.assertEqual(2, session.transport_send_failures)

    async def test_restart_guard_counts_only_expected_generation_or_state_rejections(self):
        session = self.session()
        old = session.connection
        session.connection = self.connection()
        session.stop, session.start = AsyncMock(), AsyncMock()
        self.assertEqual((0, 0), (session.transport_send_failures, session.restart_requests_ignored))
        await session.restart(old)
        session._state = sdk.SessionState.STARTING
        await session.restart(session.connection)
        self.assertEqual(2, session.restart_requests_ignored)
        session.stop.assert_not_awaited()
        session.start.assert_not_awaited()
        await session.restart()  # Existing public/startup recovery stays unconditional.
        session.stop.assert_awaited_once()
        session.start.assert_awaited_once()
        self.assertEqual(2, session.restart_requests_ignored)

    async def test_stale_packet_is_discarded_before_and_after_unpack(self):
        for phase in ('before', 'after', 'error'):
            with self.subTest(phase=phase):
                old = self.connection()
                session = self.session(old)
                replacement = self.connection(self.writer())
                session.restart = AsyncMock()
                response = session.results[123] = sdk.Result()
                packet = Message(raw.types.Pong(msg_id=123, ping_id=1), 10, 1, 0)
                if phase == 'before':
                    session.connection = replacement
                    with patch.object(sdk.mtproto, 'unpack') as unpack:
                        await session.handle_packet(b'fixture', old)
                    unpack.assert_not_called()
                else:
                    unpack, entered, release = self.blocked_crypto(packet,
                        ValueError('old packet') if phase == 'error' else None)
                    with patch.object(sdk.mtproto, 'unpack', side_effect=unpack):
                        task = asyncio.create_task(session.handle_packet(b'fixture', old))
                        await asyncio.wait_for(entered.wait(), 1)
                        session.connection = replacement
                        session.pending_acks = {999}
                        session.stored_msg_ids = [888]
                        release.set()
                        await task
                    self.assertEqual({999}, session.pending_acks)
                    self.assertEqual([888], session.stored_msg_ids)
                self.assertIsNone(response.value)
                self.assertFalse(response.event.is_set())
                session.restart.assert_not_awaited()
                self.assertTrue(session.is_started.is_set())

    async def test_stale_packet_after_identity_allocation_cannot_mutate_replacement(self):
        old = self.connection()
        session = self.session(old)
        session.stored_msg_ids = [1]
        response = session.results[123] = sdk.Result()
        entered, release = asyncio.Event(), asyncio.Event()
        async def allocate():
            entered.set()
            await release.wait()
            return 10
        session.msg_factory.allocate_message_identity = allocate
        packet = Message(raw.types.Pong(msg_id=123, ping_id=1), 10, 2, 0)
        with patch.object(sdk.mtproto, 'unpack', return_value=packet):
            task = asyncio.create_task(session.handle_packet(b'fixture', old))
            await asyncio.wait_for(entered.wait(), 1)
            session.connection = self.connection()
            session.stored_msg_ids = [888]
            session.ignore_count = 9
            release.set()
            await task
        self.assertEqual([888], session.stored_msg_ids)
        self.assertEqual(9, session.ignore_count)
        self.assertIsNone(response.value)

    async def test_old_ack_completion_cannot_clear_replacement_acks(self):
        old = self.connection()
        session = self.session(old)
        session.pending_acks = set(range(10))
        entered, release = asyncio.Event(), asyncio.Event()
        async def send(*args):
            entered.set()
            await release.wait()
        session.send = AsyncMock(side_effect=send)
        with patch.object(sdk.mtproto, 'unpack', return_value=Message(MsgContainer([]), 1, 0, 0)):
            task = asyncio.create_task(session.handle_packet(b'fixture', old))
            await asyncio.wait_for(entered.wait(), 1)
            session.connection = self.connection()
            session.pending_acks = {999}
            release.set()
            await task
        self.assertEqual({999}, session.pending_acks)

    async def test_packet_failures_and_ping_capture_restart_generation(self):
        for kind in ('unpack', 'security', 'ping'):
            with self.subTest(kind=kind):
                session = self.session()
                expected = session.connection
                session.restart = AsyncMock()
                if kind == 'unpack':
                    with patch.object(sdk.mtproto, 'unpack', side_effect=ValueError('invalid packet')):
                        await session.handle_packet(b'fixture', expected)
                elif kind == 'security':
                    session.stored_msg_ids = [2]
                    session.ignore_count = session.MAX_CONSECUTIVE_IGNORED - 1
                    packet = Message(raw.types.Pong(msg_id=123, ping_id=1), 1, 2, 0)
                    with patch.object(sdk.mtproto, 'unpack', return_value=packet):
                        await session.handle_packet(b'fixture', expected)
                else:
                    replacement = self.connection()
                    async def allocate():
                        session.connection = replacement
                        return 10
                    session.msg_factory.allocate_message_identity = allocate
                    session.send = AsyncMock(side_effect=OSError('send'))
                    session.PING_INTERVAL = 0.001
                    expected = replacement
                    await session.ping_worker()
                await self.settle_tasks()
                session.restart.assert_awaited_once_with(expected)

    async def test_healthy_and_rpc500_send_do_not_close_or_clear_readiness(self):
        for error in (False, True):
            with self.subTest(error=error):
                writer = self.writer()
                session = self.session(self.connection(writer))
                async def drain():
                    pending = session.results[session.msg_factory._last_msg_id]
                    pending.value = raw.types.RpcError(error_code=500, error_message='RPC_CALL_FAIL') if error else 'success'
                    pending.event.set()
                writer.drain.side_effect = drain
                with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
                    if error:
                        with self.assertRaises(InternalServerError):
                            await session.send(raw.functions.Ping(ping_id=1))
                    else:
                        self.assertEqual('success', await session.send(raw.functions.Ping(ping_id=1)))
                self.assertTrue(session.is_started.is_set())
                self.assertEqual(0, session.transport_send_failures)
                writer.close.assert_not_called()
                self.assertEqual({}, session.results)

    async def test_invoke_rpc500_keeps_retry_and_generation_scoped_restart(self):
        session = self.session()
        expected = session.connection
        session.send = AsyncMock(side_effect=[InternalServerError('fixture'), 'success'])
        session.restart = AsyncMock()
        self.assertEqual('success', await session.invoke(raw.functions.Ping(ping_id=1), retries=2, retry_delay=0))
        await self.settle_tasks()
        session.restart.assert_awaited_once_with(expected)
        self.assertEqual(2, session.send.await_count)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual(0, session.transport_send_failures)

    async def test_starting_send_failure_uses_existing_unqualified_start_recovery(self):
        connection = self.connection()
        session = self.session(connection)
        session._state = sdk.SessionState.STOPPED
        session.is_started.clear()
        connection.connect = AsyncMock()
        connection.recv = AsyncMock(side_effect=lambda: asyncio.Future())
        async def recv():
            await asyncio.Future()
        connection.recv.side_effect = recv
        session.client.connection_factory = Mock(return_value=connection)
        session.restart = AsyncMock()
        with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
            await session.start()
        await self.wait_until(lambda: session.restart.await_count == 1)
        session.restart.assert_awaited_once_with()
        self.assertEqual(sdk.SessionState.STARTING, session.state)
        self.assertFalse(session.is_started.is_set())
        self.assertEqual(1, session.transport_send_failures)
        self.assertEqual(0, session.restart_requests_ignored)
        session.recv_task.cancel()
        await asyncio.gather(session.recv_task, return_exceptions=True)

    async def test_pack_oserror_is_not_counted_as_transport_send_failure(self):
        writer = self.writer()
        session = self.session(self.connection(writer))
        with patch.object(sdk.mtproto, 'pack', side_effect=OSError('packing failure')):
            with self.assertRaisesRegex(OSError, 'packing failure'):
                await session.send(raw.functions.Ping(ping_id=1))
        self.assertEqual(0, session.transport_send_failures)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual({}, session.results)
        writer.write.assert_not_called()
        writer.close.assert_not_called()

    async def test_recv_forwards_generation_and_discards_stale_recv_completion(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                connection = self.connection()
                session = self.session(connection)
                session.handle_packet = AsyncMock()
                session.restart = AsyncMock()
                if stale:
                    async def recv():
                        session.connection = self.connection()
                        return b'packet'
                    connection.recv = recv
                else:
                    connection.recv = AsyncMock(side_effect=[b'packet', None])
                await session.recv_worker()
                await self.settle_tasks()
                if stale:
                    session.handle_packet.assert_not_awaited()
                    session.restart.assert_not_awaited()
                else:
                    session.handle_packet.assert_awaited_once_with(b'packet', connection)
                    session.restart.assert_awaited_once_with(connection)

    async def test_old_invoke_failure_cannot_restart_replacement(self):
        old = self.connection()
        session = self.session(old)
        replacement = self.connection(self.writer())
        calls = []
        async def send(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                session.connection = replacement
                raise OSError('old failure')
            return 'success'
        session.send = send
        session.start, session.stop = AsyncMock(), AsyncMock()
        self.assertEqual('success', await session.invoke(raw.functions.Ping(ping_id=1), retries=2, retry_delay=0))
        await self.settle_tasks()
        self.assertEqual(1, session.restart_requests_ignored)
        session.start.assert_not_awaited()
        session.stop.assert_not_awaited()
        self.assertTrue(session.is_started.is_set())
        replacement.protocol.writer.close.assert_not_called()

    async def test_actual_rpc500_keeps_existing_retry_and_restart_policy(self):
        writer = self.writer()
        session = self.session(self.connection(writer))
        expected = session.connection
        session.restart = AsyncMock()
        responses = [raw.types.RpcError(error_code=500, error_message='RPC_CALL_FAIL'), 'success']
        async def drain():
            pending = session.results[session.msg_factory._last_msg_id]
            pending.value = responses.pop(0)
            pending.event.set()
        writer.drain.side_effect = drain
        with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
            self.assertEqual('success', await session.invoke(raw.functions.Ping(ping_id=1), retries=2, retry_delay=0))
        await self.settle_tasks()
        session.restart.assert_awaited_once_with(expected)
        self.assertEqual(2, writer.write.call_count)
        self.assertEqual(0, session.transport_send_failures)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual({}, session.results)

    async def test_actual_history_get_failed_is_returned_without_retry_or_restart(self):
        writer = self.writer()
        session = self.session(self.connection(writer))
        session.restart = AsyncMock()
        async def drain():
            pending = session.results[session.msg_factory._last_msg_id]
            pending.value = raw.types.RpcError(error_code=500, error_message='HISTORY_GET_FAILED')
            pending.event.set()
        writer.drain.side_effect = drain
        with patch.object(sdk.mtproto, 'pack', return_value=b'data'):
            with self.assertRaises(HistoryGetFailed) as error:
                await session.invoke(raw.functions.Ping(ping_id=1), retries=3, retry_delay=0)
        self.assertEqual(500, error.exception.CODE)
        session.restart.assert_not_awaited()
        self.assertEqual(1, writer.write.call_count)
        self.assertEqual(0, session.transport_send_failures)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual({}, session.results)

    async def test_successful_ack_send_removes_only_its_snapshot_within_same_generation(self):
        writer = self.writer()
        session = self.session(self.connection(writer))
        original = set(range(10))
        session.pending_acks.update(original)
        entered, release = asyncio.Event(), asyncio.Event()
        sent = []
        async def drain():
            entered.set()
            await release.wait()
        def pack(message, *args):
            self.assertIsInstance(message.body, raw.types.MsgsAck)
            sent.append(set(message.body.msg_ids))
            return b'data'
        writer.drain.side_effect = drain
        packet = Message(MsgContainer([]), 1, 0, 0)
        with patch.object(sdk.mtproto, 'unpack', return_value=packet), \
             patch.object(sdk.mtproto, 'pack', side_effect=pack):
            task = asyncio.create_task(session.handle_packet(b'fixture', session.connection))
            await asyncio.wait_for(entered.wait(), 1)
            new_ids = {999, 1000}
            session.pending_acks.update(new_ids)
            release.set()
            await task
        self.assertEqual([original], sent)
        self.assertEqual(new_ids, session.pending_acks)
        writer.write.assert_called_once_with(b'data')
        writer.drain.assert_awaited_once()
        self.assertTrue(session.is_started.is_set())
        self.assertEqual(0, session.transport_send_failures)
