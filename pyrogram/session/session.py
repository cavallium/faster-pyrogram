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

import asyncio
import bisect
import logging
import os
from enum import Enum, auto
from hashlib import sha1
from io import BytesIO
from itertools import islice
from typing import Any, Dict, List, Optional, Set

import pyrogram
from pyrogram import raw, utils
from pyrogram.connection import Connection
from pyrogram.crypto import mtproto
from pyrogram.errors import (
    AuthKeyDuplicated,
    BadMsgNotification,
    FloodPremiumWait,
    FloodWait,
    InternalServerError,
    RPCError,
    SecurityCheckMismatch,
    ServiceUnavailable,
    Unauthorized,
)
from pyrogram.raw.all import layer
from pyrogram.raw.core import FutureSalts, Int, MsgContainer, TLObject

from .internals import MsgFactory
from .diagnostics import ConnectionDiagnostics, record_for

log = logging.getLogger(__name__)
_SESSION_DIAGNOSTICS = os.environ.get("PYROGRAM_SESSION_DIAGNOSTICS") == "1"


class SessionState(Enum):
    STARTING = auto()
    STARTED = auto()
    STOPPING = auto()
    STOPPED = auto()


class TransportError(Exception):
    pass


class AuthKeyNotFound(TransportError):
    pass


class TransportFlood(TransportError):
    pass


class InvalidDC(TransportError):
    pass


class Result:
    __slots__ = ("value", "event")

    def __init__(self):
        self.value: Any = None
        self.event: asyncio.Event = asyncio.Event()


class Session:
    START_TIMEOUT = 2
    WAIT_TIMEOUT = 15
    SLEEP_THRESHOLD = 10
    MAX_RETRIES = 10
    ACKS_THRESHOLD = 10
    ACKS_MAX_IDS = 8192  # https://core.telegram.org/mtproto/service_messages_about_messages
    PING_INTERVAL = 5
    RETRY_DELAY = 1
    STORED_MSG_IDS_MAX_SIZE = 1000 * 2
    CRYPTO_EXECUTOR_WORKERS = 1
    MAX_CONSECUTIVE_IGNORED = 30

    def __init__(
        self,
        client: "pyrogram.Client",
        dc_id: int,
        server_address: str,
        port: int,
        auth_key: bytes,
        test_mode: bool,
        is_media: bool = False,
        is_cdn: bool = False,
    ):
        self.client = client
        self.dc_id = dc_id
        self.server_address = server_address
        self.port = port
        self.auth_key = auth_key
        self.test_mode = test_mode
        self.is_media = is_media
        self.is_cdn = is_cdn

        self.connection: Optional[Connection] = None

        self._state = SessionState.STOPPED
        self._state_lock = asyncio.Lock()

        self.auth_key_id = sha1(auth_key).digest()[-8:]

        self.session_id = os.urandom(8)
        self.msg_factory = MsgFactory(self.client)

        self.salt = 0

        self.ignore_count = 0

        self.pending_acks: Set[int] = set()
        self._ack_task: Optional[asyncio.Task] = None

        self.results: Dict[int, Result] = {}

        self.stored_msg_ids: List[int] = []
        self.recent_msg_ids: List[int] = []

        self.ping_task: Optional[asyncio.Task] = None
        self.ping_task_event = asyncio.Event()

        self.recv_task: Optional[asyncio.Task] = None

        self.is_started = asyncio.Event()
        self.restart_lock = asyncio.Lock()
        self._lifecycle_lock = asyncio.Lock()
        self._run_generation = 0
        self._start_task: Optional[asyncio.Task] = None
        self._start_generation = None
        if _SESSION_DIAGNOSTICS:
            self._diagnostic_last_open = None
        self.transport_send_failures = 0
        self.restart_requests_ignored = 0

    @property
    def state(self) -> SessionState:
        """Get current session state"""
        return self._state

    async def _set_state(self, new_state: SessionState) -> None:
        """Set session state"""
        async with self._state_lock:
            old_state = self._state
            self._state = new_state

            log.debug("Session state changed: %s -> %s", old_state.name, new_state.name)

    def _owns_start(self, generation, connection):
        return self._run_generation == generation and self.connection is connection

    def _has_live_intent(self):
        task = self._start_task
        return (self.state == SessionState.STARTED and self.is_started.is_set()) or (
            task is not None and self._start_generation == self._run_generation
            and not task.done() and not task.cancelling()
        )

    @staticmethod
    async def _await_task(task, *, cancel_on_cancel=False, ignore_cancelled=False):
        """Join SDK work without forwarding repeated waiter cancellation into cleanup."""
        cancelled = None
        waiter = asyncio.current_task()
        cancellation_count = waiter.cancelling()
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError as e:
                if not task.cancelled() or waiter.cancelling() > cancellation_count:
                    cancelled = e
                if task.cancelled():
                    break
                if cancel_on_cancel and not task.cancelling():
                    task.cancel()
            except Exception:
                break
        if cancelled is not None:
            failure = None if task.cancelled() else task.exception()
            raise cancelled from failure
        if ignore_cancelled and task.cancelled():
            return
        return task.result()

    async def start(self):
        current = asyncio.current_task()
        if self._state in (SessionState.STARTED, SessionState.STARTING) or (
            self._start_task is not None and self._start_generation == self._run_generation
            and self._start_task is not current and not self._start_task.done()
        ):
            log.debug("Session already started")
            return

        self._run_generation += 1
        generation = self._run_generation
        operation = asyncio.create_task(self._start(generation))
        self._start_task = operation
        self._start_generation = generation
        try:
            return await self._await_task(operation, cancel_on_cancel=True)
        except asyncio.CancelledError as cancelled:
            # A callback may swallow the operation's cancellation, even uncancel it.
            # The public caller still owns cancellation of this particular run.
            async def stop_current():
                if self._run_generation == generation:
                    await self.stop()
            if self._run_generation == generation:
                try:
                    await self._await_task(asyncio.create_task(stop_current()))
                except Exception as cleanup_error:
                    raise cancelled from cleanup_error
            raise
        finally:
            if self._start_task is operation and operation.done():
                self._start_task = None
                self._start_generation = None

    async def _start(self, generation):
        owner = asyncio.current_task()
        connection = None
        delay = self.RETRY_DELAY
        try:
            while self._run_generation == generation:
                error = None
                cleanup_failed = False
                async with self._lifecycle_lock:
                    if self._run_generation != generation:
                        return
                    await self._set_state(SessionState.STARTING)
                    connection = self.connection = None
                    try:
                        connection = self.connection = self.client.connection_factory(
                            dc_id=self.dc_id,
                            server_address=self.server_address,
                            port=self.port,
                            test_mode=self.test_mode,
                            proxy=self.client.proxy,
                            media=self.is_media,
                            protocol_factory=self.client.protocol_factory,
                            crypto_executor_workers=self.CRYPTO_EXECUTOR_WORKERS,
                            loop=self.client.loop
                        )

                        diagnostics = None
                        if _SESSION_DIAGNOSTICS:
                            try:
                                diagnostics = ConnectionDiagnostics(generation, self.dc_id, self._diagnostic_last_open,
                                    len(self.pending_acks))
                                connection._session_diagnostics = diagnostics
                                self._diagnostic_last_open = diagnostics.started
                            except Exception:
                                diagnostics = None
                        await connection.connect()
                        if diagnostics is not None:
                            try:
                                diagnostics.connected()
                            except Exception:
                                pass

                        if not self._owns_start(generation, connection):
                            raise asyncio.CancelledError
                        self.recv_task = self.client.loop.create_task(self.recv_worker())

                        await self.send(raw.functions.Ping(ping_id=0), timeout=self.START_TIMEOUT)

                        if not self._owns_start(generation, connection):
                            raise asyncio.CancelledError
                        init_connection_params = self.client.init_connection_params

                        if isinstance(init_connection_params, dict):
                            init_connection_params = utils.obj_to_jsonvalue(init_connection_params)

                        if not self.is_cdn:
                            api_id = await self.client.storage.api_id()
                            if not self._owns_start(generation, connection):
                                raise asyncio.CancelledError
                            await self.send(
                                raw.functions.InvokeWithLayer(
                                    layer=layer,
                                    query=raw.functions.InitConnection(
                                        api_id=api_id,
                                        app_version=self.client.app_version,
                                        device_model=self.client.device_model,
                                        system_version=self.client.system_version,
                                        system_lang_code=self.client.system_lang_code,
                                        lang_pack=self.client.lang_pack,
                                        lang_code=self.client.lang_code,
                                        query=raw.functions.help.GetConfig(),
                                        params=init_connection_params,
                                    )
                                ),
                                timeout=self.START_TIMEOUT
                            )

                        if not self._owns_start(generation, connection):
                            raise asyncio.CancelledError
                        self.ping_task = self.client.loop.create_task(self.ping_worker())

                        log.info(
                            "Session initialized: Pyrogram v%s (Layer %s)", pyrogram.__version__, layer
                        )
                        log.info("Device: %s - %s", self.client.device_model, self.client.app_version)
                        log.info("System: %s (%s)", self.client.system_version, self.client.lang_code)
                        await self._set_state(SessionState.STARTED)
                        if not self._owns_start(generation, connection):
                            raise asyncio.CancelledError
                        self.is_started.set()
                        log.info("Session started")
                    except BaseException as e:
                        error = e
                        try:
                            failure = await self._teardown()
                            if failure is not None and not isinstance(error, asyncio.CancelledError):
                                error = failure
                        except asyncio.CancelledError as cleanup_cancelled:
                            error = cleanup_cancelled
                        except Exception as cleanup_error:
                            cleanup_error.__cause__ = error
                            error = cleanup_error
                            cleanup_failed = True

                if error is None:
                    break
                await self._notify_stopped()
                if cleanup_failed or isinstance(error, (AuthKeyDuplicated, Unauthorized)) or not isinstance(error, (OSError, RPCError)):
                    raise error
                if self._run_generation != generation:
                    return
                wait = max(delay, error.value if isinstance(error, (FloodWait, FloodPremiumWait)) else 0)
                log.info("Session bootstrap retry in %s s: dc_id=%s primary=%s (%s)",
                         wait, self.dc_id, getattr(self.client, "session", None) is self,
                         error.__class__.__name__)
                await asyncio.sleep(wait)
                delay = min(delay * 2, self.WAIT_TIMEOUT)
            if self._run_generation == generation and self.is_started.is_set() and callable(self.client.connect_handler):
                try:
                    await self.client.connect_handler(self.client, self)
                except Exception as e:
                    log.exception(e)
        except BaseException:
            # The connect callback is part of startup too. Never tear down a newer intent.
            if self.state != SessionState.STOPPED and self._owns_start(generation, connection):
                async with self._lifecycle_lock:
                    if self._owns_start(generation, connection):
                        await self._teardown()
                await self._notify_stopped()
            raise
        finally:
            if self._start_task is owner:
                self._start_task = None
                self._start_generation = None

    async def _notify_stopped(self):
        log.info("Session stopped")
        if callable(self.client.disconnect_handler):
            try:
                await self.client.disconnect_handler(self.client, self)
            except Exception as e:
                log.exception(e)

    async def _teardown(self):
        """Close the attempt while its caller owns the lifecycle lock."""
        await self._set_state(SessionState.STOPPING)
        self.is_started.clear()
        self.ignore_count = 0
        self.stored_msg_ids.clear()
        self.ping_task_event.set()
        ack_task = self._ack_task
        tasks = [task for task in (self.ping_task, self.recv_task, ack_task)
                 if task is not None and task is not asyncio.current_task()]
        connection = self.connection

        diagnostics = record_for(connection) if _SESSION_DIAGNOSTICS else None

        async def close_attempt():
            # A ping may own the transport send lock that close also needs.
            for task in tasks:
                if not task.done():
                    task.cancel()
            closed = False
            try:
                # Join the ACK owner before close needs the same transport send lock.
                if ack_task is not None and ack_task is not asyncio.current_task() and ack_task in tasks:
                    await asyncio.gather(ack_task, return_exceptions=True)
                if connection is not None:
                    await connection.close()
                closed = True
            finally:
                if diagnostics is not None:
                    try:
                        diagnostics.emit('close', self.state.name, self.is_started.is_set(),
                            getattr(self.client, 'session', None) is self, self.connection is connection, closed,
                            len(self.pending_acks) if self.connection is connection else None)
                    except Exception:
                        pass
                outcomes = await asyncio.gather(*tasks, return_exceptions=True)
                self.ping_task = self.recv_task = None
                if self._ack_task is ack_task:
                    self._ack_task = None
                if self.connection is connection:
                    self.connection = None
                self.ping_task_event.clear()
                await self._set_state(SessionState.STOPPED)
            return next((value for value in outcomes if isinstance(value, AuthKeyNotFound)), None)

        cleanup = asyncio.create_task(close_attempt())
        return await self._await_task(cleanup)

    async def stop(self):
        self._run_generation += 1
        generation = self._run_generation
        self.is_started.clear()
        owner = self._start_task
        if owner is not None and owner is not asyncio.current_task() and not owner.done():
            if not owner.cancelling():
                owner.cancel()
            await self._await_task(owner, ignore_cancelled=True)
        async with self._lifecycle_lock:
            if self._run_generation != generation or self._state == SessionState.STOPPED:
                return
            failure = await self._teardown()
        await self._notify_stopped()
        if failure is not None:
            raise failure

    async def restart(self, expected_connection: Optional[Connection] = None):
        async with self.restart_lock:
            if expected_connection is not None and (
                self.connection is not expected_connection or self.state != SessionState.STARTED
            ):
                self.restart_requests_ignored += 1
                return
            generation = self._run_generation
            if self.stored_msg_ids:
                self.recent_msg_ids = self.stored_msg_ids[:30]
            if expected_connection is None:
                generation += 1  # The increment performed by our own stop, not a later external stop.
                await self.stop()
            else:
                async with self._lifecycle_lock:
                    if self._run_generation != generation:
                        return
                    failure = await self._teardown()
                await self._notify_stopped()
                if failure is not None:
                    raise failure
            if self._run_generation == generation:
                await self.start()

    async def handle_packet(self, packet, connection: Optional[Connection] = None):
        connection = self.connection if connection is None else connection
        if connection is not self.connection:
            return
        try:
            data = await self.client.loop.run_in_executor(
                connection.protocol.crypto_executor,
                mtproto.unpack,
                BytesIO(packet),
                self.session_id,
                self.auth_key,
                self.auth_key_id
            )
        except ValueError as e:
            if connection is self.connection:
                log.debug(e)
                log.info("Restarting session due to - %s - %s", e.__class__.__name__, e)
                self.client.loop.create_task(self.restart(connection))
            return
        if connection is not self.connection:
            return

        diagnostics = record_for(connection) if _SESSION_DIAGNOSTICS else None
        messages = (
            data.body.messages
            if isinstance(data.body, MsgContainer)
            else [data]
        )

        log.debug("Received: %s", data)

        for msg in messages:
            if msg.seq_no == 0:
                self.client._set_server_time(msg.msg_id)

            if msg.seq_no % 2 != 0:
                already_pending = msg.msg_id in self.pending_acks
                if diagnostics is not None:
                    try:
                        diagnostics.inbound(True, not already_pending)
                    except Exception:
                        pass
                if already_pending:
                    continue
                else:
                    self.pending_acks.add(msg.msg_id)

            try:
                if len(self.stored_msg_ids) > Session.STORED_MSG_IDS_MAX_SIZE:
                    del self.stored_msg_ids[:Session.STORED_MSG_IDS_MAX_SIZE // 2]

                if msg.msg_id in self.recent_msg_ids:
                   self.recent_msg_ids.remove(msg.msg_id)
                   raise SecurityCheckMismatch(
                         "The msg_id is belong to most recent closed connection."
                   )

                if self.stored_msg_ids:
                    if msg.msg_id < self.stored_msg_ids[0]:
                        raise SecurityCheckMismatch(
                            "The msg_id is lower than all the stored values"
                        )

                    if msg.msg_id in self.stored_msg_ids:
                        raise SecurityCheckMismatch(
                            "The msg_id is equal to any of the stored values"
                        )

                    current_msg_id = await self.msg_factory.allocate_message_identity()
                    if connection is not self.connection:
                        return
                    time_diff = (msg.msg_id - current_msg_id) / 2 ** 32

                    if time_diff > 30:
                        raise SecurityCheckMismatch(
                            "The msg_id belongs to over 30 seconds in the future. "
                            "Most likely the client time has to be synchronized."
                        )

                    if time_diff < -300:
                        raise SecurityCheckMismatch(
                            "The msg_id belongs to over 300 seconds in the past. "
                            "Most likely the client time has to be synchronized."
                        )

                    self.ignore_count = 0
            except SecurityCheckMismatch as e:
                log.info("Discarding packet: %s", e)

                self.ignore_count += 1

                if self.ignore_count >= self.MAX_CONSECUTIVE_IGNORED:
                    log.info("Restarting session due to - %s - %s", e.__class__.__name__, e)
                    self.client.loop.create_task(self.restart(connection))

                return
            else:
                bisect.insort(self.stored_msg_ids, msg.msg_id)

            if isinstance(msg.body, (raw.types.MsgDetailedInfo, raw.types.MsgNewDetailedInfo)):
                if diagnostics is not None:
                    try:
                        diagnostics.inbound(False, msg.body.answer_msg_id not in self.pending_acks)
                    except Exception:
                        pass
                self.pending_acks.add(msg.body.answer_msg_id)
                continue

            if isinstance(msg.body, raw.types.NewSessionCreated):
                continue

            msg_id = None

            if isinstance(msg.body, (raw.types.BadMsgNotification, raw.types.BadServerSalt)):
                msg_id = msg.body.bad_msg_id
            elif isinstance(msg.body, (FutureSalts, raw.types.RpcResult)):
                msg_id = msg.body.req_msg_id
            elif isinstance(msg.body, raw.types.Pong):
                msg_id = msg.body.msg_id
            else:
                if self.client is not None:
                    self.client.loop.create_task(self.client.handle_updates(msg.body))

            if msg_id in self.results:
                self.results[msg_id].value = getattr(msg.body, "result", msg.body)
                self.results[msg_id].event.set()

        if (len(self.pending_acks) >= self.ACKS_THRESHOLD
                and connection is self.connection
                and self.state in (SessionState.STARTING, SessionState.STARTED)
                and (self._ack_task is None or self._ack_task.done())):
            self._ack_task = self.client.loop.create_task(self._flush_acks(connection, self._run_generation))

    async def _flush_acks(self, connection, generation):
        owner = asyncio.current_task()
        try:
            while (self._ack_task is owner and self._owns_start(generation, connection)
                    and self.state in (SessionState.STARTING, SessionState.STARTED) and self.pending_acks):
                ack_ids = list(islice(self.pending_acks, self.ACKS_MAX_IDS))
                log.debug("Sending %s acks", len(ack_ids))
                try:
                    await self.send(raw.types.MsgsAck(msg_ids=ack_ids), False)
                except OSError:
                    return  # Keep the snapshot for the next eligible incoming packet.
                if (self._ack_task is not owner or not self._owns_start(generation, connection)
                        or self.state not in (SessionState.STARTING, SessionState.STARTED)):
                    return
                self.pending_acks.difference_update(ack_ids)
        finally:
            if self._ack_task is owner:
                self._ack_task = None

    async def ping_worker(self):
        log.info("PingTask started")

        while True:
            try:
                await asyncio.wait_for(self.ping_task_event.wait(), self.PING_INTERVAL)
            except asyncio.TimeoutError:
                pass
            else:
                break

            ping_id = await self.msg_factory.allocate_message_identity()
            connection = self.connection
            try:
                await self.send(
                    raw.functions.PingDelayDisconnect(
                        ping_id=ping_id,
                        disconnect_delay=self.WAIT_TIMEOUT + 10
                    ),
                    wait_response=False
                )
            except OSError as e:
                log.info("Restarting session due to - %s - %s", e.__class__.__name__, e)
                self.client.loop.create_task(self.restart(connection))
                break
            except RPCError:
                pass

        log.info("PingTask stopped")

    async def recv_worker(self):
        log.info("NetworkTask started")

        while True:
            connection = self.connection
            packet = await connection.recv()
            if connection is not self.connection:
                break

            if packet is None or len(packet) == 4:
                if packet:
                    error_code = -Int.read(BytesIO(packet))
                    error_msg = "unknown error"

                    if error_code == 404:
                        raise AuthKeyNotFound(
                            "Auth key not found in the system. Try again or delete your session file "
                            "and log in again with your phone number or bot token."
                        )

                    try:
                        if error_code == 429:
                            if _SESSION_DIAGNOSTICS:
                                diagnostics = record_for(connection)
                                if diagnostics is not None:
                                    try:
                                        diagnostics.emit('transport_429', self.state.name, self.is_started.is_set(),
                                            getattr(self.client, 'session', None) is self, self.connection is connection,
                                            pending_count=len(self.pending_acks) if self.connection is connection else None)
                                    except Exception:
                                        pass
                            raise TransportFlood(
                                "Transport flood. Please slow down your requests."
                            )
                        elif error_code == 444:
                            raise InvalidDC(
                                "Invalid data center. Please check your configuration."
                            )
                    except TransportError as e:
                        error_msg = str(e)

                    log.warning("Server sent transport error: %s (%s)", error_code, error_msg)


                if self.state == SessionState.STARTED:
                    if packet:
                        error = f"Server sent transport error - {error_code} - ({error_msg})."
                    else:
                        error = "Server sent a null packet."

                    log.info("Restarting session due to - %s", error)
                    self.client.loop.create_task(self.restart(connection))

                break

            self.client.loop.create_task(self.handle_packet(packet, connection))

        log.info("NetworkTask stopped")

    async def send(
        self, data: TLObject, wait_response: bool = True, timeout: float = WAIT_TIMEOUT
    ):
        connection = self.connection
        if connection is None or connection.protocol is None:
            raise OSError("Session transport is not connected")
        diagnostics = record_for(connection) if _SESSION_DIAGNOSTICS else None
        message = await self.msg_factory.create(data)
        msg_id = message.msg_id

        if wait_response:
            pending_result = self.results[msg_id] = Result()

        try:
            log.debug("Sent: %s", message)

            payload = await self.client.loop.run_in_executor(
                connection.protocol.crypto_executor,
                mtproto.pack,
                message,
                self.salt,
                self.session_id,
                self.auth_key,
                self.auth_key_id
            )

            try:
                if diagnostics is None:
                    await connection.send(payload)
                else:
                    category = None
                    try:
                        category = diagnostics.attempt(data, self.state.name, self.is_started.is_set(),
                            self.connection is connection,
                            self.state == SessionState.STARTING and asyncio.current_task() is self._start_task)
                    except Exception:
                        pass
                    try:
                        await connection.send(payload)
                    except BaseException as error:
                        try:
                            diagnostics.complete(category, error)
                        except Exception:
                            pass
                        raise
                    else:
                        try:
                            diagnostics.complete(category)
                        except Exception:
                            pass
            except OSError:
                self.transport_send_failures += 1
                if self.connection is connection and self.state == SessionState.STARTED:
                    self.is_started.clear()
                closed = False
                try:
                    await connection.close()
                    closed = True
                except Exception:
                    pass
                finally:
                    if diagnostics is not None:
                        try:
                            diagnostics.emit('send_oserror_close', self.state.name, self.is_started.is_set(),
                                getattr(self.client, 'session', None) is self, self.connection is connection, closed,
                                len(self.pending_acks) if self.connection is connection else None)
                        except Exception:
                            pass
                raise

            if wait_response:
                try:
                    await asyncio.wait_for(self.results[msg_id].event.wait(), timeout)
                except asyncio.TimeoutError:
                    pass

                result = self.results.pop(msg_id).value
        finally:
            if wait_response and self.results.get(msg_id) is pending_result:
                self.results.pop(msg_id)

        if wait_response:
            if result is None:
                raise TimeoutError("Request timed out")

            if isinstance(result, raw.types.RpcError):
                if isinstance(
                    data, (raw.functions.InvokeWithoutUpdates, raw.functions.InvokeWithTakeout)
                ):
                    data = data.query

                RPCError.raise_it(result, type(data))

            if isinstance(result, raw.types.BadMsgNotification):
                log.warning(
                    "%s: %s", BadMsgNotification.__name__, BadMsgNotification(result.error_code)
                )

            if isinstance(result, raw.types.BadServerSalt):
                self.salt = result.new_server_salt
                return await self.send(data, wait_response, timeout)

            return result

    async def invoke(
        self,
        query: TLObject,
        retries: int = MAX_RETRIES,
        timeout: float = WAIT_TIMEOUT,
        sleep_threshold: float = SLEEP_THRESHOLD,
        retry_delay: float = RETRY_DELAY
    ):
        try:
            await asyncio.wait_for(self.is_started.wait(), self.WAIT_TIMEOUT)
        except asyncio.TimeoutError:
            pass

        if isinstance(
            query, (raw.functions.InvokeWithoutUpdates, raw.functions.InvokeWithTakeout)
        ):
            inner_query = query.query
        else:
            inner_query = query

        query_name = ".".join(inner_query.QUALNAME.split(".")[1:])

        for attempt in range(1, retries + 1):
            connection = self.connection
            try:
                return await self.send(query, timeout=timeout)
            except (FloodWait, FloodPremiumWait) as e:
                amount = e.value

                if amount > sleep_threshold >= 0:
                    raise

                log.warning(
                    '[%s] Waiting for %s seconds before continuing (required by "%s")',
                    self.client.name,
                    amount,
                    query_name,
                )

                await asyncio.sleep(amount)
            except (OSError, InternalServerError, ServiceUnavailable) as e:
                if isinstance(e, InternalServerError) \
                        and e.CODE == 500 \
                        and (e.ID or e.NAME) == "HISTORY_GET_FAILED":
                    raise e from None

                (log.warning if attempt < retries else log.info)(
                    '[%s] Retrying "%s" due to: %s',
                    attempt,
                    query_name, str(e) or repr(e)
                )

                if connection is not None and self.state == SessionState.STARTED and not self.restart_lock.locked():
                    self.client.loop.create_task(self.restart(connection))

                await asyncio.sleep(retry_delay)

        raise TimeoutError(f'Failed to invoke "{query_name}" after {retries} retries')

    def __str__(self) -> str:
        return f"Session(dc_id={self.dc_id}, test_mode={self.test_mode}, is_media={self.is_media}, is_cdn={self.is_cdn}, state={self._state.name})"
