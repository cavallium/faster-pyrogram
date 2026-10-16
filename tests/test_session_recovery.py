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
        session.stop, session.start = AsyncMock(wraps=session.stop), AsyncMock()
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

    def bootstrap_session(self):
        session = self.session()
        session._state = sdk.SessionState.STOPPED
        session.is_started.clear()
        connection = SimpleNamespace(connect=AsyncMock(), close=AsyncMock())
        session.client.connection_factory = Mock(return_value=connection)
        session.client.init_connection_params = None
        session.client.storage = SimpleNamespace(api_id=AsyncMock(return_value=123))
        for key in ('app_version', 'device_model', 'system_version', 'system_lang_code', 'lang_pack', 'lang_code'):
            setattr(session.client, key, 'fixture')
        async def worker():
            await asyncio.Future()
        session.recv_worker = worker
        session.ping_worker = worker
        session.send = AsyncMock(return_value='success')
        return session, connection

    async def test_actual_bootstrap429_keeps_deadline_and_adds_owned_backoff(self):
        session, _ = self.bootstrap_session()
        del session.send
        del session.recv_worker
        virtual = 0
        connects, delays, connections = [], [], []
        original_wait_for, original_sleep = asyncio.wait_for, asyncio.sleep
        received = asyncio.Event()
        def factory(**kwargs):
            queue = asyncio.Queue()
            transport = self.connection().protocol
            async def connect():
                connects.append(virtual)
                if len(connects) == 4:
                    raise ValueError('end controlled attempts')
            async def send(payload):
                self.assertIsInstance(payload, bytes)  # Actual mtproto.pack and executor.
                queue.put_nowait((-429).to_bytes(4, 'little', signed=True))
            async def recv():
                value = await queue.get()
                received.set()
                return value
            async def close():
                queue.put_nowait(None)
            connection = SimpleNamespace(connect=connect, send=send, recv=recv,
                close=AsyncMock(side_effect=close), protocol=transport)
            connections.append(connection)
            return connection
        session.client.connection_factory = factory
        async def wait_for(operation, timeout):
            nonlocal virtual
            self.assertEqual(2, timeout)
            waiter = asyncio.create_task(operation)
            try:
                await original_wait_for(received.wait(), 1)
                received.clear()
                self.assertTrue(session.recv_task.done())
                self.assertEqual(1, len(session.results))
                self.assertFalse(next(iter(session.results.values())).event.is_set())
                virtual += timeout
                raise asyncio.TimeoutError
            finally:
                waiter.cancel()
                await asyncio.gather(waiter, return_exceptions=True)
        async def sleep(delay):
            nonlocal virtual
            self.assertIsNone(session.recv_task)
            self.assertEqual({}, session.results)
            connections[-1].close.assert_awaited_once()
            delays.append(delay)
            virtual += delay
            await original_sleep(0)
        with patch.object(sdk.asyncio, 'wait_for', side_effect=wait_for), patch.object(sdk.asyncio, 'sleep', side_effect=sleep):
            with self.assertRaisesRegex(ValueError, 'end controlled attempts'):
                await session.start()
        self.assertEqual([0, 3, 7, 13], connects)
        self.assertEqual([1, 2, 4], delays)
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertEqual(3, len(self.loop.tasks))  # Receive owners only; no queued restart.
        self.assertEqual({}, session.results)

    async def test_bootstrap_owned_backoff_recovers_and_resets(self):
        session, connection = self.bootstrap_session()
        delays = []
        async def sleep(delay):
            self.assertEqual(sdk.SessionState.STOPPED, session.state)
            self.assertTrue(session.recv_task is None)
            self.assertGreater(connection.close.await_count, 0)
            delays.append(delay)
        session.send.side_effect = [OSError('failed')] * 6 + ['ping', 'init']
        with patch.object(sdk.asyncio, 'sleep', side_effect=sleep):
            await session.start()
        self.assertEqual([1, 2, 4, 8, 15, 15], delays)
        self.assertEqual(7, connection.connect.await_count)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual(sdk.SessionState.STARTED, session.state)
        self.assertTrue(all(call.kwargs['timeout'] == 2 for call in session.send.await_args_list))
        await session.stop()
        delays.clear()
        session.send.side_effect = [OSError('again'), 'ping', 'init']
        with patch.object(sdk.asyncio, 'sleep', side_effect=sleep):
            await session.start()
        self.assertEqual([1], delays)
        await session.stop()

    async def test_bootstrap_flood_wait_is_minimum(self):
        for error in (sdk.FloodWait(12), sdk.FloodPremiumWait(20)):
            session, connection = self.bootstrap_session()
            session.send.side_effect = [error, 'ping', 'init']
            with patch.object(sdk.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
                await session.start()
            sleep.assert_awaited_once_with(error.value)
            await session.stop()

    async def test_cancel_connect_ping_init_and_backoff_cleans_and_can_restart(self):
        for phase in ('connect', 'ping', 'init', 'backoff'):
            with self.subTest(phase=phase):
                session, connection = self.bootstrap_session()
                entered = asyncio.Event()
                async def block(*args, **kwargs):
                    entered.set()
                    await asyncio.Future()
                if phase == 'connect':
                    connection.connect.side_effect = block
                elif phase in ('ping', 'init'):
                    async def send(query, **kwargs):
                        if phase == 'ping' or isinstance(query, raw.functions.InvokeWithLayer):
                            await block()
                    session.send.side_effect = send
                else:
                    session.send.side_effect = OSError('failed')
                with patch.object(sdk.asyncio, 'sleep', side_effect=block) if phase == 'backoff' else patch.object(session, 'RETRY_DELAY', 1):
                    task = asyncio.create_task(session.start())
                    await asyncio.wait_for(entered.wait(), 1)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                self.assertEqual(sdk.SessionState.STOPPED, session.state)
                self.assertFalse(session.is_started.is_set())
                self.assertIsNone(session.recv_task)
                self.assertIsNone(session.ping_task)
                connection.close.assert_awaited()
                connection.connect.side_effect = None
                session.send.side_effect = None
                await session.start()
                self.assertTrue(session.is_started.is_set())
                await session.stop()

    async def test_stop_during_backoff_does_not_resurrect(self):
        session, connection = self.bootstrap_session()
        entered = asyncio.Event()
        async def sleep(delay):
            entered.set()
            await asyncio.Future()
        session.send.side_effect = OSError('failed')
        with patch.object(sdk.asyncio, 'sleep', side_effect=sleep):
            task = asyncio.create_task(session.start())
            await asyncio.wait_for(entered.wait(), 1)
            await session.stop()
        self.assertTrue(task.cancelled())
        self.assertEqual(1, connection.connect.await_count)
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        session.send.side_effect = None
        await session.restart()  # A new explicit intent may reconnect after stop.
        self.assertTrue(session.is_started.is_set())
        await session.stop()

    async def test_stop_invalidates_qualified_restart_while_close_blocked(self):
        session, connection = self.bootstrap_session()
        await session.start()
        entered, release = asyncio.Event(), asyncio.Event()
        async def close():
            entered.set()
            await release.wait()
        connection.close.side_effect = close
        task = asyncio.create_task(session.restart(connection))
        await asyncio.wait_for(entered.wait(), 1)
        stop = asyncio.create_task(session.stop())
        await self.wait_until(lambda: session._run_generation == 2)
        release.set()
        await asyncio.gather(task, stop)
        self.assertEqual(1, connection.connect.await_count)
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertFalse(session.is_started.is_set())

    async def test_fatal_bootstrap_auth_and_transport404_cleanup(self):
        for error in (sdk.AuthKeyDuplicated('fixture'), sdk.Unauthorized('fixture')):
            session, connection = self.bootstrap_session()
            session.send.side_effect = error
            with self.assertRaises(type(error)):
                await session.start()
            self.assertEqual(sdk.SessionState.STOPPED, session.state)
            connection.close.assert_awaited_once()
        session, connection = self.bootstrap_session()
        async def recv():
            raise sdk.AuthKeyNotFound('404')
        session.recv_worker = recv
        async def send(*args, **kwargs):
            await asyncio.sleep(0)
            raise TimeoutError('bootstrap')
        session.send.side_effect = send
        with self.assertRaises(sdk.AuthKeyNotFound):
            await session.start()
        self.assertEqual(sdk.SessionState.STOPPED, session.state)

    async def test_concurrent_start_during_backoff_does_not_take_ownership(self):
        session, connection = self.bootstrap_session()
        entered = asyncio.Event()
        async def sleep(delay):
            entered.set()
            await asyncio.Future()
        session.send.side_effect = OSError('failed')
        with patch.object(sdk.asyncio, 'sleep', side_effect=sleep):
            task = asyncio.create_task(session.start())
            await asyncio.wait_for(entered.wait(), 1)
            generation = session._run_generation
            await session.start()
            self.assertEqual(generation, session._run_generation)
            self.assertIsNot(task, session._start_task)
            self.assertFalse(session._start_task.done())
            await asyncio.gather(session.stop(), session.stop())
        self.assertTrue(task.cancelled())
        self.assertEqual(1, connection.connect.await_count)
        self.assertEqual(sdk.SessionState.STOPPED, session.state)

    async def test_manual_restart_cannot_override_stop_during_close(self):
        session, connection = self.bootstrap_session()
        await session.start()
        entered, release = asyncio.Event(), asyncio.Event()
        async def close():
            entered.set()
            await release.wait()
        connection.close.side_effect = close
        restart = asyncio.create_task(session.restart())
        await asyncio.wait_for(entered.wait(), 1)
        stop = asyncio.create_task(session.stop())
        await self.wait_until(lambda: session._run_generation == 3)
        release.set()
        await asyncio.gather(restart, stop)
        self.assertEqual(1, connection.connect.await_count)
        self.assertFalse(session.is_started.is_set())

    async def test_stop_during_failed_attempt_close_joins_before_return(self):
        session, connection = self.bootstrap_session()
        session.send.side_effect = OSError('failed')
        entered, release = asyncio.Event(), asyncio.Event()
        async def close():
            entered.set()
            await release.wait()
        connection.close.side_effect = close
        start = asyncio.create_task(session.start())
        await asyncio.wait_for(entered.wait(), 1)
        stop = asyncio.create_task(session.stop())
        await self.wait_until(session._start_task.cancelling)
        self.assertFalse(stop.done())
        release.set()
        await stop
        self.assertTrue(start.cancelled())
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertEqual(1, connection.connect.await_count)
        self.assertIsNone(session.recv_task)

    async def test_stop_cancels_ping_before_waiting_for_transport_close_lock(self):
        connection = self.connection(self.writer())
        session = self.session(connection)
        entered = asyncio.Event()
        async def ping():
            async with connection.protocol.lock:
                entered.set()
                await asyncio.Future()
        session.ping_task = asyncio.create_task(ping())
        await asyncio.wait_for(entered.wait(), 1)
        ping_task = session.ping_task
        await asyncio.wait_for(session.stop(), 1)
        self.assertTrue(ping_task.cancelled())
        self.assertEqual(sdk.SessionState.STOPPED, session.state)

    async def test_factory_failure_is_owned_and_retries_without_stale_connection(self):
        session, connection = self.bootstrap_session()
        session.client.connection_factory.side_effect = [OSError('factory failed'), connection]
        with patch.object(sdk.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            await session.start()
        sleep.assert_awaited_once_with(1)
        self.assertTrue(session.is_started.is_set())
        self.assertEqual(1, connection.connect.await_count)
        await session.stop()

    async def test_disconnect_callback_can_stop_retry_and_qualified_restart(self):
        for bootstrap in (False, True):
            session, connection = self.bootstrap_session()
            async def disconnected(client, current):
                self.assertFalse(current._lifecycle_lock.locked())
                self.assertEqual(sdk.SessionState.STOPPED, current.state)
                await current.stop()
            session.client.disconnect_handler = AsyncMock(side_effect=disconnected)
            if bootstrap:
                session.send.side_effect = OSError('failed')
                await asyncio.wait_for(session.start(), 1)
            else:
                await session.start()
                await asyncio.wait_for(session.restart(connection), 1)
            session.client.disconnect_handler.assert_awaited_once_with(session.client, session)
            self.assertEqual(1, connection.connect.await_count)
            self.assertFalse(session.is_started.is_set())

    async def test_fatal_receive_remains_visible_to_stop_and_qualified_restart(self):
        for restart in (False, True):
            session, connection = self.bootstrap_session()
            await session.start()
            session.recv_task.cancel()
            await asyncio.gather(session.recv_task, return_exceptions=True)
            async def fatal():
                raise sdk.AuthKeyNotFound('404')
            session.recv_task = asyncio.create_task(fatal())
            await asyncio.sleep(0)
            with self.assertRaises(sdk.AuthKeyNotFound):
                if restart:
                    await session.restart(connection)
                else:
                    await session.stop()
            self.assertEqual(1, connection.connect.await_count)
            self.assertEqual(sdk.SessionState.STOPPED, session.state)
            self.assertIsNone(session.connection)

    async def test_delayed_unpack_cannot_mutate_stopped_session_without_replacement(self):
        old = self.connection()
        session = self.session(old)
        response = session.results[123] = sdk.Result()
        packet = Message(raw.types.Pong(msg_id=123, ping_id=1), 10, 1, 0)
        unpack, entered, release = self.blocked_crypto(packet)
        with patch.object(sdk.mtproto, 'unpack', side_effect=unpack):
            task = asyncio.create_task(session.handle_packet(b'fixture', old))
            await asyncio.wait_for(entered.wait(), 1)
            await session.stop()
            self.assertIsNone(session.connection)
            release.set()
            await task
        self.assertEqual([], session.stored_msg_ids)
        self.assertIsNone(response.value)
        self.assertFalse(response.event.is_set())
        self.assertEqual(sdk.SessionState.STOPPED, session.state)

    async def test_failed_close_is_terminal_and_preserves_bootstrap_cause(self):
        session, connection = self.bootstrap_session()
        bootstrap_error = OSError('bootstrap failed')
        cleanup_error = OSError('close failed')
        session.send.side_effect = bootstrap_error
        connection.close.side_effect = cleanup_error
        session.client.disconnect_handler = AsyncMock()
        with patch.object(sdk.asyncio, 'sleep', new_callable=AsyncMock) as sleep:
            with self.assertRaisesRegex(OSError, 'close failed') as raised:
                await session.start()
        self.assertIs(bootstrap_error, raised.exception.__cause__)
        sleep.assert_not_awaited()
        session.client.connection_factory.assert_called_once()
        connection.connect.assert_awaited_once()
        connection.close.assert_awaited_once()
        session.client.disconnect_handler.assert_awaited_once()
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertIsNone(session._start_task)
        self.assertIsNone(session.connection)

    async def test_stop_joins_sdk_operation_not_application_caller_lifetime(self):
        session, connection = self.bootstrap_session()
        entered, continued, unrelated_release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def connect():
            entered.set()
            await asyncio.Future()
        connection.connect.side_effect = connect
        async def application():
            try:
                await session.start()
            except asyncio.CancelledError:
                pass
            continued.set()
            await unrelated_release.wait()
        caller = asyncio.create_task(application())
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.assertIsNot(caller, session._start_task)
            await asyncio.wait_for(session.stop(), 1)
            await asyncio.wait_for(continued.wait(), 1)
            self.assertFalse(caller.done())
            self.assertEqual(sdk.SessionState.STOPPED, session.state)
            self.assertIsNone(session._start_task)
            connection.close.assert_awaited_once()
        finally:
            unrelated_release.set()
            await caller

    async def test_cancel_get_session_in_connect_callback_cleans_before_cache_eviction(self):
        from pyrogram.client import Client
        from pyrogram import client as client_module
        for replace in (False, True):
            with self.subTest(replace=replace):
                session, connection = self.bootstrap_session()
                client = session.client
                client.storage.dc_id = AsyncMock(return_value=2)
                client.storage.test_mode = AsyncMock(return_value=False)
                client.sessions, client.media_sessions, client.ipv6 = {}, {}, False
                client.get_session = AsyncMock(return_value=SimpleNamespace(auth_key=b'key'))
                client.get_dc_option = AsyncMock(return_value=SimpleNamespace(ip_address='127.0.0.1', port=443))
                entered = asyncio.Event()
                replacement = object()
                async def callback(*args):
                    self.assertFalse(session._lifecycle_lock.locked())
                    if replace:
                        client.media_sessions[2] = replacement
                    entered.set()
                    await asyncio.Future()
                client.connect_handler = callback
                with patch.object(client_module, 'Session', return_value=session):
                    caller = asyncio.create_task(Client.get_session(client, dc_id=2, is_media=True))
                    await asyncio.wait_for(entered.wait(), 1)
                    self.assertTrue(session.is_started.is_set())
                    caller.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await caller
                self.assertEqual({2: replacement} if replace else {}, client.media_sessions)
                self.assertEqual(sdk.SessionState.STOPPED, session.state)
                self.assertFalse(session.is_started.is_set())
                self.assertIsNone(session.connection)
                self.assertIsNone(session._start_task)
                self.assertIsNone(session.recv_task)
                self.assertIsNone(session.ping_task)
                connection.close.assert_awaited_once()

    async def test_old_connect_callback_cancellation_preserves_reentrant_new_intent(self):
        for restart in (False, True):
            with self.subTest(restart=restart):
                session, old = self.bootstrap_session()
                replacement = SimpleNamespace(connect=AsyncMock(), close=AsyncMock())
                entered = asyncio.Event()
                calls = 0
                async def callback(*args):
                    nonlocal calls
                    calls += 1
                    if calls > 1:
                        return
                    await session.stop()
                    if restart:
                        session.client.connection_factory.return_value = replacement
                        await session.restart()
                    entered.set()
                    await asyncio.Future()
                session.client.connect_handler = callback
                caller = asyncio.create_task(session.start())
                await asyncio.wait_for(entered.wait(), 1)
                caller.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await caller
                old.close.assert_awaited_once()
                replacement.close.assert_not_awaited()
                if restart:
                    self.assertIs(replacement, session.connection)
                    self.assertTrue(session.is_started.is_set())
                    self.assertEqual(sdk.SessionState.STARTED, session.state)
                else:
                    self.assertIsNone(session.connection)
                    self.assertEqual(sdk.SessionState.STOPPED, session.state)
                await session.stop()

    async def test_repeated_start_and_competing_stop_cancellation_cannot_interrupt_cleanup(self):
        session, connection = self.bootstrap_session()
        connect_entered, close_entered, close_release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def connect():
            connect_entered.set()
            await asyncio.Future()
        async def close():
            close_entered.set()
            await close_release.wait()
        connection.connect.side_effect = connect
        connection.close.side_effect = close
        caller = asyncio.create_task(session.start())
        await asyncio.wait_for(connect_entered.wait(), 1)
        owner = session._start_task
        caller.cancel()
        await asyncio.wait_for(close_entered.wait(), 1)
        first_stop = asyncio.create_task(session.stop())
        second_stop = asyncio.create_task(session.stop())
        await self.wait_until(lambda: session._run_generation == 3)
        for _ in range(3):
            caller.cancel()
            first_stop.cancel()
            await asyncio.sleep(0)
        self.assertFalse(owner.done())
        self.assertFalse(second_stop.done())
        self.assertEqual(1, owner.cancelling())
        close_release.set()
        for task in (caller, first_stop):
            with self.assertRaises(asyncio.CancelledError):
                await task
        await asyncio.wait_for(second_stop, 1)
        connection.close.assert_awaited_once()
        self.assertTrue(owner.cancelled())
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertFalse(session.is_started.is_set())
        self.assertIsNone(session.connection)
        self.assertIsNone(session._start_task)

    async def test_competing_stop_waiters_cannot_cancel_established_close(self):
        session, connection = self.bootstrap_session()
        await session.start()
        entered, release = asyncio.Event(), asyncio.Event()
        async def close():
            entered.set()
            await release.wait()
        connection.close.side_effect = close
        first = asyncio.create_task(session.stop())
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(session.stop())
        await self.wait_until(lambda: session._run_generation == 3)
        for _ in range(3):
            first.cancel()
            await asyncio.sleep(0)
        self.assertFalse(second.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await first
        await asyncio.wait_for(second, 1)
        connection.close.assert_awaited_once()
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertIsNone(session.connection)

    async def test_get_session_callback_swallowing_cancellation_still_cleans_current_run(self):
        from pyrogram.client import Client
        from pyrogram import client as client_module
        for uncancel in (False, True):
            with self.subTest(uncancel=uncancel):
                session, connection = self.bootstrap_session()
                client = session.client
                client.storage.dc_id = AsyncMock(return_value=2)
                client.storage.test_mode = AsyncMock(return_value=False)
                client.sessions, client.media_sessions, client.ipv6 = {}, {}, False
                client.get_session = AsyncMock(return_value=SimpleNamespace(auth_key=b'key'))
                client.get_dc_option = AsyncMock(return_value=SimpleNamespace(ip_address='127.0.0.1', port=443))
                entered = asyncio.Event()
                async def callback(*args):
                    entered.set()
                    try:
                        await asyncio.Future()
                    except asyncio.CancelledError:
                        if uncancel:
                            asyncio.current_task().uncancel()
                client.connect_handler = callback
                with patch.object(client_module, 'Session', return_value=session):
                    caller = asyncio.create_task(Client.get_session(client, dc_id=2, is_media=True))
                    await asyncio.wait_for(entered.wait(), 1)
                    caller.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await caller
                self.assertEqual({}, client.media_sessions)
                self.assertEqual(sdk.SessionState.STOPPED, session.state)
                self.assertFalse(session.is_started.is_set())
                self.assertIsNone(session.connection)
                self.assertIsNone(session._start_task)
                self.assertIsNone(session.recv_task)
                self.assertIsNone(session.ping_task)
                connection.close.assert_awaited_once()

    async def test_cancel_old_get_session_preserves_same_object_new_ready_starting_or_backoff_run(self):
        from pyrogram.client import Client
        from pyrogram import client as client_module
        for phase in ('starting', 'backoff', 'ready'):
            ready = phase == 'ready'
            with self.subTest(phase=phase):
                session, old = self.bootstrap_session()
                client = session.client
                client.storage.dc_id = AsyncMock(return_value=2)
                client.storage.test_mode = AsyncMock(return_value=False)
                client.sessions, client.media_sessions, client.ipv6 = {}, {}, False
                client.get_session = AsyncMock(return_value=SimpleNamespace(auth_key=b'key'))
                client.get_dc_option = AsyncMock(return_value=SimpleNamespace(ip_address='127.0.0.1', port=443))
                entered, connecting = asyncio.Event(), asyncio.Event()
                replacement = SimpleNamespace(connect=AsyncMock(), close=AsyncMock())
                async def connect():
                    connecting.set()
                    if phase == 'starting':
                        await asyncio.Future()
                replacement.connect.side_effect = connect
                new_caller = None
                calls = 0
                async def callback(*args):
                    nonlocal calls, new_caller
                    calls += 1
                    if calls > 1:
                        return
                    await session.stop()
                    client.connection_factory.return_value = replacement
                    if phase == 'backoff':
                        session.send.side_effect = OSError('new run retry')
                    new_caller = asyncio.create_task(session.start())
                    await connecting.wait()
                    if ready:
                        await new_caller
                    elif phase == 'backoff':
                        await self.wait_until(lambda: session.state == sdk.SessionState.STOPPED
                            and session.connection is None and session._has_live_intent())
                    entered.set()
                    try:
                        await asyncio.Future()
                    except asyncio.CancelledError:
                        asyncio.current_task().uncancel()
                client.connect_handler = callback
                with patch.object(client_module, 'Session', return_value=session):
                    old_caller = asyncio.create_task(Client.get_session(client, dc_id=2, is_media=True))
                    await asyncio.wait_for(entered.wait(), 1)
                    old_caller.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await old_caller
                self.assertIs(session, client.media_sessions[2])
                self.assertIs(None if phase == 'backoff' else replacement, session.connection)
                expected_state = {'ready': sdk.SessionState.STARTED, 'starting': sdk.SessionState.STARTING,
                    'backoff': sdk.SessionState.STOPPED}[phase]
                self.assertEqual(expected_state, session.state)
                self.assertTrue(session._has_live_intent())
                self.assertEqual(ready, session.is_started.is_set())
                old.close.assert_awaited_once()
                self.assertEqual(1 if phase == 'backoff' else 0, replacement.close.await_count)
                await session.stop()
                await asyncio.gather(new_caller, return_exceptions=True)

    async def test_old_get_session_does_not_retain_invalidated_same_object_stopping_run(self):
        from pyrogram.client import Client
        from pyrogram import client as client_module
        session, old = self.bootstrap_session()
        client = session.client
        client.storage.dc_id = AsyncMock(return_value=2)
        client.storage.test_mode = AsyncMock(return_value=False)
        client.sessions, client.media_sessions, client.ipv6 = {}, {}, False
        client.get_session = AsyncMock(return_value=SimpleNamespace(auth_key=b'key'))
        client.get_dc_option = AsyncMock(return_value=SimpleNamespace(ip_address='127.0.0.1', port=443))
        connecting, closing, release, entered = (asyncio.Event() for _ in range(4))
        async def connect():
            connecting.set()
            await asyncio.Future()
        async def close():
            closing.set()
            await release.wait()
        replacement = SimpleNamespace(connect=connect, close=AsyncMock(side_effect=close))
        new_caller = stopping = None
        async def callback(*args):
            nonlocal new_caller, stopping
            await session.stop()
            client.connection_factory.return_value = replacement
            new_caller = asyncio.create_task(session.start())
            await connecting.wait()
            stopping = asyncio.create_task(session.stop())
            await closing.wait()
            entered.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                asyncio.current_task().uncancel()
        client.connect_handler = callback
        with patch.object(client_module, 'Session', return_value=session):
            old_caller = asyncio.create_task(Client.get_session(client, dc_id=2, is_media=True))
            await asyncio.wait_for(entered.wait(), 1)
            self.assertEqual(sdk.SessionState.STOPPING, session.state)
            self.assertFalse(session._has_live_intent())
            old_caller.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await old_caller
        self.assertEqual({}, client.media_sessions)
        self.assertFalse(stopping.done())
        release.set()
        await asyncio.wait_for(stopping, 1)
        await asyncio.gather(new_caller, return_exceptions=True)
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        self.assertIsNone(session._start_task)
        replacement.close.assert_awaited_once()

    async def test_start_operation_cancelled_before_first_step_releases_owner(self):
        session, connection = self.bootstrap_session()
        original = asyncio.create_task
        def cancel_operation(coroutine):
            task = original(coroutine)
            if coroutine.cr_code.co_name == '_start':
                task.cancel()
            return task
        with patch.object(sdk.asyncio, 'create_task', side_effect=cancel_operation):
            with self.assertRaises(asyncio.CancelledError):
                await session.start()
        self.assertIsNone(session._start_task)
        self.assertEqual(sdk.SessionState.STOPPED, session.state)
        session.client.connection_factory.assert_not_called()

    async def test_get_session_evicts_only_its_failed_cached_start(self):
        from pyrogram.client import Client
        from pyrogram import client as client_module
        for cancel in (False, True):
            for replace in (False, True):
                for temporary in (False, True):
                    with self.subTest(cancel=cancel, replace=replace, temporary=temporary):
                        replacement = object()
                        client = SimpleNamespace(storage=SimpleNamespace(dc_id=AsyncMock(return_value=2),
                            test_mode=AsyncMock(return_value=False), auth_key=AsyncMock(return_value=b'key')),
                            sessions={}, media_sessions={}, ipv6=False,
                            get_dc_option=AsyncMock(return_value=SimpleNamespace(ip_address='127.0.0.1', port=443)))
                        session = SimpleNamespace(_has_live_intent=lambda: False)
                        error = asyncio.CancelledError() if cancel else RuntimeError('startup')
                        async def start():
                            if replace:
                                client.media_sessions[2] = replacement
                            raise error
                        session.start = start
                        client.get_session = AsyncMock(return_value=SimpleNamespace(auth_key=b'key'))
                        with patch.object(client_module, 'Session', return_value=session):
                            with self.assertRaises(type(error)):
                                await Client.get_session(client, dc_id=2, is_media=True, temporary=temporary)
                        self.assertEqual({2: replacement} if replace else {}, client.media_sessions)

    async def test_missing_connection_or_protocol_is_retryable_before_factory_and_results(self):
        for state in (sdk.SessionState.STOPPED, sdk.SessionState.STARTING, sdk.SessionState.STARTED):
            for missing in ('connection', 'protocol'):
                for wait_response in (False, True):
                    with self.subTest(state=state, missing=missing, wait_response=wait_response):
                        session = self.session()
                        session._state = state
                        if state != sdk.SessionState.STARTED:
                            session.is_started.clear()
                        session.connection = None if missing == 'connection' else Connection(2, '127.0.0.1', 1, True)
                        session.msg_factory.create = AsyncMock()
                        unrelated = session.results[123] = sdk.Result()
                        with patch.object(sdk.mtproto, 'pack') as pack:
                            with self.assertRaisesRegex(OSError, 'Session transport is not connected'):
                                await session.send(raw.functions.Ping(ping_id=1), wait_response=wait_response)
                        session.msg_factory.create.assert_not_awaited()
                        pack.assert_not_called()
                        self.assertEqual({123: unrelated}, session.results)
                        self.assertEqual(0, session.transport_send_failures)
                        self.assertEqual(state == sdk.SessionState.STARTED, session.is_started.is_set())

    async def test_actual_invoke_missing_transport_after_readiness_timeout_recovers_on_retry(self):
        for missing in ('connection', 'protocol'):
            with self.subTest(missing=missing):
                session = self.session()
                session.connection = None if missing == 'connection' else Connection(2, '127.0.0.1', 1, True)
                session._state = sdk.SessionState.STOPPED
                session.is_started.clear()
                session.restart = AsyncMock()
                writer = self.writer()
                replacement = self.connection(writer)
                async def drain():
                    result = session.results[session.msg_factory._last_msg_id]
                    result.value = 'success'
                    result.event.set()
                writer.drain.side_effect = drain
                original_wait_for = asyncio.wait_for
                waits, retries = [], []
                async def wait_for(operation, timeout):
                    waits.append(timeout)
                    return await original_wait_for(operation, timeout if session.is_started.is_set() else 0)
                async def sleep(delay):
                    retries.append(delay)
                    self.assertEqual({}, session.results)
                    self.assertEqual(0, session.transport_send_failures)
                    session.connection = replacement
                    session._state = sdk.SessionState.STARTED
                    session.is_started.set()
                with patch.object(sdk.asyncio, 'wait_for', side_effect=wait_for), patch.object(sdk.asyncio, 'sleep', side_effect=sleep):
                    self.assertEqual('success', await session.invoke(raw.functions.Ping(ping_id=1), retries=2, retry_delay=0))
                self.assertEqual(session.WAIT_TIMEOUT, waits[0])
                self.assertEqual([0], retries)
                session.restart.assert_not_awaited()
                writer.close.assert_not_called()
                self.assertEqual({}, session.results)
                self.assertEqual(0, session.transport_send_failures)
                self.assertTrue(session.is_started.is_set())
                self.assertEqual(1, writer.write.call_count)

    async def test_missing_capture_invoke_failure_cannot_schedule_manual_restart_of_replacement(self):
        session = self.session()
        session.connection = None
        writer = self.writer()
        replacement = self.connection(writer)
        session.restart = AsyncMock()
        entered, release = asyncio.Event(), asyncio.Event()
        original_send = session.send
        async def send(*args, **kwargs):
            try:
                return await original_send(*args, **kwargs)
            except OSError:
                entered.set()
                await release.wait()  # Restore a healthy connection before invoke handles this failure.
                raise
        async def drain():
            result = session.results[session.msg_factory._last_msg_id]
            result.value = 'success'
            result.event.set()
        writer.drain.side_effect = drain
        session.send = send
        caller = asyncio.create_task(session.invoke(raw.functions.Ping(ping_id=1), retries=2, retry_delay=0))
        await asyncio.wait_for(entered.wait(), 1)
        session.connection = replacement
        session._state = sdk.SessionState.STARTED
        session.is_started.set()
        release.set()
        self.assertEqual('success', await asyncio.wait_for(caller, 1))
        await self.settle_tasks()
        session.restart.assert_not_awaited()
        self.assertTrue(session.is_started.is_set())
        self.assertIs(replacement, session.connection)
        self.assertEqual({}, session.results)
        self.assertEqual(0, session.transport_send_failures)
        writer.close.assert_not_called()
        writer.transport.abort.assert_not_called()

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
