from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from pyrogram.connection.transport.tcp.tcp import TCP


@pytest.fixture
async def transport():
    transport = TCP()
    transport.marker_event.set()
    yield transport
    await transport.close()
    transport.crypto_executor.shutdown(wait=True, cancel_futures=True)


def closing_writer():
    return SimpleNamespace(
        is_closing=Mock(return_value=True),
        transport=SimpleNamespace(abort=Mock()),
        write=Mock(),
        close=Mock(),
        drain=AsyncMock(),
        wait_closed=AsyncMock(),
    )


@pytest.mark.parametrize("has_writer", [False, True])
async def test_send_to_disconnected_transport_raises(transport, has_writer):
    if has_writer:
        transport.writer = closing_writer()
    with pytest.raises(OSError, match="TCP transport is not connected"):
        await transport.send(b"payload")


async def test_close_finishes_closing_writer_and_forgets_it(transport):
    writer = transport.writer = closing_writer()
    await transport.close()
    writer.transport.abort.assert_called_once()
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()
    assert transport.writer is None
    await transport.close()
    writer.close.assert_called_once()


async def test_cancelling_close_wait_still_forgets_writer(transport):
    writer = transport.writer = closing_writer()
    entered = asyncio.Event()

    async def wait_closed():
        entered.set()
        await asyncio.Future()

    writer.wait_closed.side_effect = wait_closed
    task = asyncio.create_task(transport.close())
    await asyncio.wait_for(entered.wait(), 1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.writer is None


async def test_web_carrier_does_not_require_a_writer(transport):
    carrier = transport._web_carrier = SimpleNamespace(send=AsyncMock(), close=AsyncMock())
    await transport.send(b"payload")
    carrier.send.assert_awaited_once_with(b"payload")
    await transport.close()
    carrier.close.assert_awaited_once()
    assert transport._web_carrier is None
