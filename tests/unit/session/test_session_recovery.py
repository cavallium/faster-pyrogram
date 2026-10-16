from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from pyrogram import raw
from pyrogram.connection import Connection
from pyrogram.connection.transport.tcp import TCPAbridged
from pyrogram.errors import InternalServerError, ServiceUnavailable
from pyrogram.raw.core import Message, MsgContainer
from pyrogram.session import session as sdk

from tests.unit.connection.transport.tcp.test_tcp_lifecycle import closing_writer

from .test_session import StubConnection, _started_session


@pytest.fixture
async def inline_crypto(monkeypatch):
    def execute(executor, function, *args):
        future = asyncio.get_running_loop().create_future()
        try:
            future.set_result(function(*args))
        except Exception as error:
            future.set_exception(error)
        return future

    monkeypatch.setattr(asyncio.get_running_loop(), "run_in_executor", execute)
    monkeypatch.setattr(sdk.mtproto, "pack", lambda *args: b"payload")


async def wait_until(predicate):
    async def wait():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), 1)


@pytest.mark.parametrize("stage", ["pack", "send", "response"])
async def test_cancelled_send_cleans_up_registration(monkeypatch, inline_crypto, stage):
    session = _started_session()
    entered = asyncio.Event()

    async def send(payload):
        entered.set()
        if stage == "send":
            await asyncio.Future()

    monkeypatch.setattr(session.connection, "send", send)
    if stage == "pack":

        def execute(*args):
            entered.set()
            return asyncio.get_running_loop().create_future()

        monkeypatch.setattr(asyncio.get_running_loop(), "run_in_executor", execute)

    for _ in range(3):
        entered.clear()
        task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=0)))
        await asyncio.wait_for(entered.wait(), 1)
        if stage == "response":
            await wait_until(lambda: next(iter(session.results.values())).event._waiters)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert session.results == {}


@pytest.mark.parametrize("error_type", [ValueError, OSError])
async def test_pack_failure_cleans_up_without_closing_transport(
    monkeypatch, inline_crypto, error_type
):
    session = _started_session()
    connection = session.connection
    error = error_type("packing failed")

    def pack(*args):
        raise error

    monkeypatch.setattr(sdk.mtproto, "pack", pack)
    with pytest.raises(error_type) as raised:
        await session.send(raw.functions.Ping(ping_id=0))
    assert raised.value is error
    assert session.results == {}
    assert not connection.closed.is_set()
    assert session.is_started.is_set()


async def test_cancel_does_not_remove_replacement_result(monkeypatch, inline_crypto):
    session = _started_session()
    task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=0)))
    await wait_until(
        lambda: session.results and next(iter(session.results.values())).event._waiters
    )
    msg_id = next(iter(session.results))
    replacement = session.results[msg_id] = sdk.Result()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert session.results == {msg_id: replacement}


@pytest.mark.parametrize("stage", ["factory", "pack"])
async def test_send_cannot_move_to_replacement_connection(monkeypatch, inline_crypto, stage):
    session = _started_session()
    old = session.connection
    replacement = StubConnection()
    entered = asyncio.Event()
    release = asyncio.Event()
    if stage == "factory":
        original = session.msg_factory.create

        async def create(data):
            entered.set()
            await release.wait()
            return await original(data)

        monkeypatch.setattr(session.msg_factory, "create", create)
    else:

        def execute(*args):
            entered.set()
            return asyncio.create_task(release.wait())

        monkeypatch.setattr(asyncio.get_running_loop(), "run_in_executor", execute)
    task = asyncio.create_task(session.send(raw.functions.Ping(ping_id=0), wait_response=False))
    await asyncio.wait_for(entered.wait(), 1)
    session.connection = replacement
    release.set()
    try:
        await task
    except OSError:
        pass
    assert replacement.sent == []
    assert session.results == {}
    assert session.is_started.is_set()
    assert not replacement.closed.is_set()
    assert old is not session.connection


@pytest.mark.parametrize("phase", ["before", "unpack", "unpack_error", "identity"])
async def test_stale_packet_cannot_mutate_replacement(monkeypatch, inline_crypto, phase):
    session = _started_session()
    old = session.connection
    replacement = StubConnection()
    result = session.results[123] = sdk.Result()
    packet = Message(raw.types.Pong(msg_id=123, ping_id=1), 10, 2, 0)
    monkeypatch.setattr(sdk.mtproto, "unpack", Mock(return_value=packet))
    session.restart = AsyncMock()
    if phase == "before":
        session.connection = replacement
        await session.handle_packet(b"packet", old)
        sdk.mtproto.unpack.assert_not_called()
    else:
        entered = asyncio.Event()
        release = asyncio.get_running_loop().create_future()
        if phase == "identity":
            session.stored_msg_ids = [1]

            async def allocate():
                entered.set()
                return await release

            monkeypatch.setattr(session.msg_factory, "allocate_message_identity", allocate)
        else:

            def execute(*args):
                entered.set()
                return release

            monkeypatch.setattr(asyncio.get_running_loop(), "run_in_executor", execute)
        task = asyncio.create_task(session.handle_packet(b"packet", old))
        await asyncio.wait_for(entered.wait(), 1)
        session.connection = replacement
        session.stored_msg_ids = [888]
        session.pending_acks = {999}
        session.ignore_count = 7
        if phase == "unpack_error":
            release.set_exception(ValueError("invalid old packet"))
        else:
            release.set_result(10 if phase == "identity" else packet)
        await task
        assert session.stored_msg_ids == [888]
        assert session.pending_acks == {999}
        assert session.ignore_count == 7
    assert result.value is None
    assert not result.event.is_set()
    session.restart.assert_not_awaited()


@pytest.mark.parametrize("replace_connection", [False, True])
async def test_ack_completion_removes_only_current_snapshot(
    monkeypatch, inline_crypto, replace_connection
):
    session = _started_session()
    old = session.connection
    original = set(range(session.ACKS_THRESHOLD))
    session.pending_acks = original.copy()
    entered = asyncio.Event()
    release = asyncio.Event()
    sent = []

    async def send(query, wait_response):
        sent.append(set(query.msg_ids))
        entered.set()
        await release.wait()

    monkeypatch.setattr(session, "send", send)
    monkeypatch.setattr(sdk.mtproto, "unpack", lambda *args: Message(MsgContainer([]), 1, 0, 0))
    task = asyncio.create_task(session.handle_packet(b"packet"))
    await asyncio.wait_for(entered.wait(), 1)
    if replace_connection:
        session.connection = StubConnection()
        session.pending_acks = {999}
    else:
        session.pending_acks.add(999)
    release.set()
    await task
    assert sent == [original]
    assert session.pending_acks == {999}
    assert (session.connection is not old) == replace_connection


@pytest.mark.parametrize("stale", [False, True])
async def test_recv_forwards_generation_and_restarts_even_after_readiness_clear(monkeypatch, stale):
    session = _started_session()
    old = session.connection
    session.is_started.clear()
    session.handle_packet = AsyncMock()
    session.restart = AsyncMock()
    queued = []
    create_task = asyncio.create_task

    def track(coroutine):
        task = create_task(coroutine)
        queued.append(task)
        return task

    packets = [b"packet", None]

    async def receive():
        if stale:
            session.connection = StubConnection()
        return packets.pop(0)

    monkeypatch.setattr(old, "recv", receive)
    monkeypatch.setattr(asyncio, "create_task", track)
    await asyncio.wait_for(session.recv_worker(), 1)
    await asyncio.gather(*queued)
    if stale:
        session.handle_packet.assert_not_awaited()
        session.restart.assert_not_awaited()
    else:
        session.handle_packet.assert_awaited_once_with(b"packet", old)
        session.restart.assert_awaited_once_with(old)


async def test_queued_restarts_only_replace_expected_generation_once(monkeypatch):
    session = _started_session()
    old = session.connection
    replacement = StubConnection()
    calls = []

    async def start():
        calls.append(True)
        session.connection = replacement
        session._state = sdk.SessionState.STARTED
        session.is_started.set()

    monkeypatch.setattr(session, "start", start)
    await session.restart_lock.acquire()
    first = asyncio.create_task(session.restart(old))
    second = asyncio.create_task(session.restart(old))
    session.restart_lock.release()
    await asyncio.gather(first, second)
    assert calls == [True]
    assert session.connection is replacement
    assert session.is_started.is_set()
    assert not replacement.closed.is_set()


async def test_dead_writer_recovers_once_and_repeated_requests_succeed(monkeypatch, inline_crypto):
    session = _started_session()
    old = Connection(2, "127.0.0.1", 443, True)
    transport = old.protocol = TCPAbridged()
    transport.marker_event.set()
    writer = transport.writer = closing_writer()
    eof = asyncio.Event()
    reading = asyncio.Event()

    async def read(length):
        reading.set()
        await eof.wait()
        return b""

    writer.transport.abort.side_effect = eof.set
    transport.reader = SimpleNamespace(read=read)
    session.connection = old
    session.recv_task = asyncio.create_task(session.recv_worker())
    await asyncio.wait_for(reading.wait(), 1)
    replacement = StubConnection()
    starts = []

    async def start():
        starts.append(True)
        session.connection = replacement
        session._state = sdk.SessionState.STARTED
        session.is_started.set()

    async def send(payload):
        pending = session.results[session.msg_factory._last_msg_id]
        pending.value = "success"
        pending.event.set()

    monkeypatch.setattr(session, "start", start)
    monkeypatch.setattr(replacement, "send", send)
    try:
        assert await session.invoke(raw.functions.Ping(ping_id=1), retry_delay=0) == "success"
        assert await session.invoke(raw.functions.Ping(ping_id=2), retries=0) == "success"
        await asyncio.sleep(0)
        assert starts == [True]
        assert session.is_started.is_set()
        assert session.results == {}
        assert transport.writer is None
        assert not replacement.closed.is_set()
    finally:
        await session.stop()
        transport.crypto_executor.shutdown(wait=True, cancel_futures=True)


async def test_old_send_failure_cannot_clear_replacement_readiness(monkeypatch, inline_crypto):
    session = _started_session()
    old = session.connection
    replacement = StubConnection()
    error = OSError("old transport failed")
    registered = []

    async def send(payload):
        msg_id = next(iter(session.results))
        registered.append((msg_id, sdk.Result()))
        session.results[msg_id] = registered[-1][1]
        session.connection = replacement
        raise error

    monkeypatch.setattr(old, "send", send)
    monkeypatch.setattr(old, "close", AsyncMock(side_effect=ValueError("close failed")))
    with pytest.raises(OSError) as raised:
        await session.send(raw.functions.Ping(ping_id=0))
    assert raised.value is error
    assert session.results == dict(registered)
    assert session.is_started.is_set()
    assert not replacement.closed.is_set()
    old.close.assert_awaited_once()


async def test_old_invoke_failure_cannot_restart_replacement(monkeypatch):
    session = _started_session()
    replacement = StubConnection()

    async def send(*args, **kwargs):
        session.connection = replacement
        raise OSError("old send failed")

    monkeypatch.setattr(session, "send", send)
    monkeypatch.setattr(session, "_stop", AsyncMock())
    monkeypatch.setattr(session, "start", AsyncMock())
    with pytest.raises(OSError):
        await session.invoke(raw.functions.Ping(ping_id=0), retries=1, retry_delay=0)
    await asyncio.sleep(0)
    session._stop.assert_not_awaited()
    session.start.assert_not_awaited()
    assert session.is_started.is_set()
    assert not replacement.closed.is_set()


@pytest.mark.parametrize("kind", ["unpack", "security", "ping"])
async def test_packet_and_ping_recovery_capture_connection(monkeypatch, inline_crypto, kind):
    session = _started_session()
    expected = session.connection
    session.restart = AsyncMock()
    if kind == "unpack":
        monkeypatch.setattr(sdk.mtproto, "unpack", Mock(side_effect=ValueError("invalid packet")))
        await session.handle_packet(b"packet")
    elif kind == "security":
        session.stored_msg_ids = [2]
        session.ignore_count = session.MAX_CONSECUTIVE_IGNORED - 1
        packet = Message(raw.types.Pong(msg_id=123, ping_id=1), 1, 2, 0)
        monkeypatch.setattr(sdk.mtproto, "unpack", lambda *args: packet)
        await session.handle_packet(b"packet")
    else:
        replacement = StubConnection()

        async def allocate():
            session.connection = replacement
            return 10

        monkeypatch.setattr(session.msg_factory, "allocate_message_identity", allocate)
        monkeypatch.setattr(session, "send", AsyncMock(side_effect=OSError("ping failed")))
        session.PING_INTERVAL = 0.001
        expected = replacement
        await session.ping_worker()
    await asyncio.sleep(0)
    session.restart.assert_awaited_once_with(expected)


@pytest.mark.parametrize("error_type", [InternalServerError, ServiceUnavailable])
async def test_rpc_server_failures_retry_without_restarting(monkeypatch, error_type):
    session = _started_session()
    connection = session.connection
    monkeypatch.setattr(session, "restart", AsyncMock())
    monkeypatch.setattr(session, "send", AsyncMock(side_effect=[error_type(), "success"]))
    assert (
        await session.invoke(raw.functions.Ping(ping_id=0), retries=1, retry_delay=0) == "success"
    )
    await asyncio.sleep(0)
    assert session.send.await_count == 2
    session.restart.assert_not_awaited()
    assert session.connection is connection
    assert session.is_started.is_set()
    assert not connection.closed.is_set()


@pytest.mark.parametrize("outcome", ["ready", "timeout", "stop"])
async def test_invoke_retries_wait_for_restart_readiness(monkeypatch, outcome):
    session = _started_session()
    replacement = StubConnection()
    initializing = asyncio.Event()
    release = asyncio.Event()
    restarts = []
    calls = []
    original_restart = session.restart

    async def restart(expected_connection=None):
        restarts.append(asyncio.current_task())
        await original_restart(expected_connection)

    async def start():
        session._state = sdk.SessionState.STARTING
        initializing.set()
        await release.wait()
        session.connection = replacement
        session._state = sdk.SessionState.STARTED
        session.is_started.set()

    async def send(*args, **kwargs):
        calls.append(session.state)
        if len(calls) == 1:
            session.is_started.clear()
            raise OSError("transport failed")
        return "success"

    monkeypatch.setattr(session, "start", start)
    monkeypatch.setattr(session, "restart", restart)
    monkeypatch.setattr(session, "send", send)
    session.WAIT_TIMEOUT = 0.05
    invoking = asyncio.create_task(
        session.invoke(raw.functions.Ping(ping_id=0), retries=1, retry_delay=0)
    )
    try:
        await asyncio.wait_for(initializing.wait(), 1)
        if outcome == "timeout":
            with pytest.raises(TimeoutError, match='invoke "Ping"'):
                await invoking
        else:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(invoking), 0.01)
            assert calls == [sdk.SessionState.STARTED]
            if outcome == "stop":
                await session.stop()
            release.set()
            if outcome == "stop":
                with pytest.raises(ConnectionError, match='invoke "Ping"'):
                    await invoking
            else:
                assert await invoking == "success"
                assert calls == [sdk.SessionState.STARTED, sdk.SessionState.STARTED]
        if outcome != "ready":
            assert calls == [sdk.SessionState.STARTED]
    finally:
        release.set()
        await asyncio.gather(*restarts, return_exceptions=True)
        if not invoking.done():
            invoking.cancel()
        await asyncio.gather(invoking, return_exceptions=True)
        await session.stop()
