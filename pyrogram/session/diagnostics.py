"""Opt-in, fixed-size snapshots of local Connection.send work, never server acceptance."""

import asyncio
import itertools
import json
import logging
import time

from pyrogram import raw

log = logging.getLogger(__name__)
_ordinals = itertools.count(1)
_CATEGORIES = ('bootstrap', 'history', 'update_difference', 'ack', 'ping', 'other')
_FIELDS = ('attempts', 'success', 'oserror', 'cancelled', 'other_error',
           'starting', 'not_ready', 'not_current_connection', 'attempt_bucket_1s_peak')


class ConnectionDiagnostics:
    """Numeric metadata only; no connection, Session, RPC, or payload references.

    Attempt bucket peaks count local Connection.send entries before TCP lock/drain,
    not wire rate or completed writes. Bootstrap is InitConnection shape or a Ping
    from the owned startup task; only the separate phase counters establish STARTING
    and not-ready state. InitConnection shape alone does not establish caller ownership.
    """

    __slots__ = ('ordinal', 'generation', 'dc_id', 'started', 'interval', 'opened',
                 'reported', 'counts', 'bucket', 'bucket_counts', 'bucket_total_peak')

    def __init__(self, generation, dc_id, previous_start):
        self.ordinal = next(_ordinals)
        self.generation = generation
        self.dc_id = dc_id
        self.started = time.monotonic()
        self.interval = None if previous_start is None else self.started - previous_start
        self.opened = None
        self.reported = False
        self.counts = [[0] * len(_FIELDS) for _ in _CATEGORIES]
        self.bucket = 0
        self.bucket_counts = [0] * len(_CATEGORIES)
        self.bucket_total_peak = 0

    def connected(self):
        self.opened = time.monotonic()

    @staticmethod
    def category(query, bootstrap=False):
        # Bounded unwrapping: malformed/cyclic wrappers become the fixed other bucket.
        for _ in range(4):
            if isinstance(query, (raw.functions.InvokeWithLayer, raw.functions.InvokeWithoutUpdates,
                                  raw.functions.InvokeWithTakeout)):
                query = query.query
            else:
                break
        if isinstance(query, raw.functions.InitConnection) or (
            isinstance(query, raw.functions.Ping) and bootstrap
        ):
            return 0
        if isinstance(query, (raw.functions.messages.GetHistory, raw.functions.messages.GetReplies)):
            return 1
        if isinstance(query, raw.functions.updates.GetChannelDifference):
            # Empty-filter crawler history versus ranged SDK update hydration; inspect type only.
            return 1 if isinstance(query.filter, raw.types.ChannelMessagesFilterEmpty) else 2
        if isinstance(query, raw.functions.updates.GetDifference):
            return 2
        if isinstance(query, raw.types.MsgsAck):
            return 3
        if isinstance(query, (raw.functions.Ping, raw.functions.PingDelayDisconnect)):
            return 4
        return 5

    def attempt(self, query, state, ready, current, bootstrap=False):
        if self.reported:
            return None
        category = self.category(query, bootstrap)
        bucket = int(time.monotonic() - self.started)
        if bucket != self.bucket:
            self.bucket = bucket
            self.bucket_counts[:] = [0] * len(_CATEGORIES)
        self.bucket_counts[category] += 1
        row = self.counts[category]
        row[0] += 1
        row[5] += state == 'STARTING'
        row[6] += not ready
        row[7] += not current
        row[8] = max(row[8], self.bucket_counts[category])
        self.bucket_total_peak = max(self.bucket_total_peak, sum(self.bucket_counts))
        return category

    def complete(self, category, error=None):
        if self.reported or category is None:
            return
        outcome = 1 if error is None else (2 if isinstance(error, OSError) else (
            3 if isinstance(error, asyncio.CancelledError) else 4))
        self.counts[category][outcome] += 1

    def emit(self, reason, state, ready, primary, current, close_succeeded=None):
        if self.reported:
            return
        self.reported = True  # Freeze AS OF first 429/close, including explicitly unfinished sends.
        now = time.monotonic()
        counts = {name: dict(zip(_FIELDS, row)) for name, row in zip(_CATEGORIES, self.counts)}
        attempts = sum(row[0] for row in self.counts)
        completions = sum(sum(row[1:5]) for row in self.counts)
        summary = dict(connection_ordinal=self.ordinal, run_generation=self.generation, dc_id=self.dc_id,
            reason=reason, state=state, ready=ready, is_current_primary=primary,
            is_current_connection=current, close_succeeded=close_succeeded,
            logical_connect_calls=1, socket_attempt_count=None,
            logical_connect_start_monotonic_s=self.started, logical_connect_interval_s=self.interval,
            logical_connect_duration_s=None if self.opened is None else self.opened - self.started,
            logical_open_duration_s=None if self.opened is None else now - self.opened,
            snapshot_duration_s=now - self.started, snapshot='first_429_or_close',
            send_semantics='local_connection_send_not_server_acceptance',
            actual_connection_send_attempts=attempts, actual_connection_send_completions=completions,
            inflight_at_cutoff=attempts - completions, attempt_bucket_1s_total_peak=self.bucket_total_peak,
            categories=counts)
        log.info('Session diagnostics: %s', json.dumps(summary, separators=(',', ':'), sort_keys=True))


def record_for(connection):
    try:
        value = getattr(connection, '_session_diagnostics', None)
        return value if isinstance(value, ConnectionDiagnostics) else None
    except Exception:
        return None
