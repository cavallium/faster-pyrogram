#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations as _annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from pyrogram import raw
from pyrogram.errors import (
    FloodPremiumWait,
    FloodWait,
    HistoryGetFailed,
    InternalServerError,
    ServiceUnavailable,
)
from pyrogram.session.session import Session

if TYPE_CHECKING:
    from pyrogram.raw.core import TLObject


class FakeClient:
    name = "test"


class _Session(Session):
    """A session whose `send()` always raises FloodWait, without the real transport."""

    def __init__(self, seconds) -> None:
        self.is_started = asyncio.Event()
        self.is_started.set()
        self.client = FakeClient()
        self.seconds = seconds
        self.send_calls = 0

    async def send(
        self,
        data: TLObject,
        wait_response: bool = True,
        timeout: float = Session.WAIT_TIMEOUT,
    ) -> TLObject:
        self.send_calls += 1
        raise FloodWait(self.seconds)


class _Query:
    QUALNAME = "test.Query"


@pytest.mark.asyncio
async def test_flood_wait_with_no_parsed_seconds_reraises() -> None:
    # `FloodWait.seconds` is `int | None`: when Telegram's message doesn't match the
    #  expected pattern, `amount` ends up None, and `amount > sleep_threshold >= 0`
    #  raised TypeError instead of the intended FloodWait re-raise.
    session = _Session(seconds=None)

    with pytest.raises(FloodWait):
        await session.invoke(_Query())

    assert session.send_calls == 1


@pytest.mark.asyncio
async def test_flood_wait_past_threshold_reraises() -> None:
    session = _Session(seconds=999)

    with pytest.raises(FloodWait):
        await session.invoke(_Query(), sleep_threshold=10)

    assert session.send_calls == 1


@pytest.mark.asyncio
async def test_history_get_failed_is_not_retried(monkeypatch) -> None:
    session = _Session(seconds=None)
    calls = 0
    error = HistoryGetFailed()

    async def send(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise error

    monkeypatch.setattr(session, "send", send)
    with pytest.raises(HistoryGetFailed) as raised:
        await session.invoke(_Query(), retry_delay=0)
    assert raised.value is error
    assert calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("wrapper", [None, "updates", "takeout"])
async def test_zero_retries_still_sends_initial_query(monkeypatch, wrapper) -> None:
    session = _Session(seconds=None)
    query = _Query()
    if wrapper == "updates":
        query = raw.functions.InvokeWithoutUpdates(query=query)
    elif wrapper == "takeout":
        query = raw.functions.InvokeWithTakeout(takeout_id=123, query=query)
    result = object()
    sent = []

    async def send(data, *, timeout):
        sent.append((data, timeout))
        return result

    monkeypatch.setattr(session, "send", send)
    assert await session.invoke(query, retries=0, timeout=42) is result
    assert sent == [(query, 42)]


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [OSError, InternalServerError, ServiceUnavailable])
@pytest.mark.parametrize("retries", [0, 2])
async def test_exhausted_retries_preserve_final_error(monkeypatch, error_type, retries) -> None:
    session = _Session(seconds=None)
    errors = [error_type() for _ in range(retries + 1)]
    calls = 0
    sleeps = []

    async def send(*args, **kwargs):
        nonlocal calls
        error = errors[calls]
        calls += 1
        raise error

    async def sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(session, "send", send)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    with pytest.raises(error_type) as raised:
        await session.invoke(_Query(), retries=retries, retry_delay=0.25)
    assert raised.value is errors[-1]
    assert calls == retries + 1
    assert sleeps == [0.25] * retries


@pytest.mark.asyncio
@pytest.mark.parametrize("flood_type", [FloodWait, FloodPremiumWait])
async def test_flood_wait_does_not_consume_transient_retries(monkeypatch, flood_type) -> None:
    session = _Session(seconds=None)
    result = object()
    outcomes = iter([flood_type(1), OSError(), flood_type(2), result])
    calls = 0
    sleeps = []

    async def send(*args, **kwargs):
        nonlocal calls
        calls += 1
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(session, "send", send)
    monkeypatch.setattr(asyncio, "sleep", sleep)
    assert await session.invoke(_Query(), retries=1, retry_delay=0.25) is result
    assert calls == 4
    assert sleeps == [1, 0.25, 2]
