import io
import json
import unittest

from pyrogram import raw
from pyrogram.raw.core import List, TLObject
from pyrogram.raw.core.primitives import Bool, Int, Long, String, Vector


def baseline_read(data, t=None):
    count = Int.read(data)
    left = len(data.read())
    size = (left / count) if count else 0
    data.seek(-left, 1)
    return List(t.read(data) if t else Vector.read_bare(data, size)
                for _ in range(count))


def outcome(read, source, t=None, position=0):
    data = io.BytesIO(source)
    data.seek(position)
    try:
        value = read(data, t)
        return "value", json.dumps(value, default=TLObject.default, sort_keys=True), data.tell()
    except Exception as error:
        return "error", type(error), str(error), data.tell()


class NoSuffixRead(io.BytesIO):
    def read(self, size=-1):
        if size < 0:
            raise AssertionError("Vector must not read the remaining stream to measure it")
        return super().read(size)


class VectorTests(unittest.TestCase):
    def test_typed_and_bare_vectors_preserve_values_exceptions_and_cursor(self):
        cases = [
            ("typed-int", [0, -1, 2 ** 31 - 1], Int, Int),
            ("typed-long", [0, -(2 ** 63), 2 ** 63 - 1], Long, Long),
            ("typed-bool", [True, False], Bool, Bool),
            ("typed-string", ["", "ascii", "é界🐾"], String, String),
            ("typed-object", [raw.types.PeerUser(user_id=7), raw.types.PeerChannel(channel_id=9)], None, TLObject),
            ("bare-int", [1, -2, 3], Int, None),
            ("bare-long", [1, -2, 2 ** 50], Long, None),
            ("bare-bool", [True, False], Bool, None),
            ("bare-object", [raw.types.PeerUser(user_id=7), raw.types.PeerChannel(channel_id=9)], None, None),
            ("large-typed", list(range(10000)), Int, Int),
        ]
        for name, values, wire_type, read_type in cases:
            wire = bytes(Vector(values, wire_type))[4:]
            for prefix, trailer in [(b"", b""), (b"prefix", b""), (b"prefix", b"trailer")]:
                with self.subTest(name=name, prefix=prefix, trailer=trailer):
                    source = prefix + wire + trailer
                    self.assertEqual(outcome(baseline_read, source, read_type, len(prefix)),
                                     outcome(Vector.read, source, read_type, len(prefix)))
            for cut in (1, 2, 3, 4, 7):
                with self.subTest(name=name, truncated=cut):
                    source = wire[:-cut] if len(wire) >= cut else b""
                    self.assertEqual(outcome(baseline_read, source, read_type),
                                     outcome(Vector.read, source, read_type))

    def test_empty_negative_and_truncated_counts_preserve_cursor(self):
        for count in (0, -1, -(2 ** 31)):
            for prefix, trailer in [(b"", b""), (b"prefix", b"trailing bytes")]:
                with self.subTest(count=count, prefix=prefix, trailer=trailer):
                    source = prefix + bytes(Int(count)) + trailer
                    self.assertEqual(outcome(baseline_read, source, position=len(prefix)),
                                     outcome(Vector.read, source, position=len(prefix)))
                    data = io.BytesIO(source)
                    data.seek(len(prefix))
                    self.assertEqual([], Vector.read(data))
                    self.assertEqual(len(prefix) + 4, data.tell())
        for source in (b"", b"\x01", b"\x02\x00", b"\xff\xff\xff"):
            with self.subTest(truncated_count=source):
                self.assertEqual(outcome(baseline_read, source), outcome(Vector.read, source))

    def test_cursor_beyond_eof_is_not_clamped_to_end(self):
        for source, position in [(b"", 5), (b"abc", 8), (bytes(Int(7)), 32)]:
            with self.subTest(source=source, position=position):
                data = io.BytesIO(source)
                data.seek(position)
                self.assertEqual([], Vector.read(data))
                self.assertEqual(position, data.tell())
                self.assertEqual(outcome(baseline_read, source, position=position),
                                 outcome(Vector.read, source, position=position))

    def test_typed_read_failure_preserves_consumed_cursor(self):
        class FailingReader:
            @staticmethod
            def read(data):
                data.read(2)
                raise ValueError("fixture read failed")

        source = bytes(Int(1)) + b"payload"
        self.assertEqual(("error", ValueError, "fixture read failed", 6),
                         outcome(Vector.read, source, FailingReader))
        self.assertEqual(outcome(baseline_read, source, FailingReader),
                         outcome(Vector.read, source, FailingReader))

    def test_large_trailer_is_not_read(self):
        values = [1, -2, 3]
        wire = bytes(Vector(values, Int))[4:]
        data = NoSuffixRead(wire + b"x" * (1024 * 1024))
        self.assertEqual(values, Vector.read(data, Int))
        self.assertEqual(len(wire), data.tell())

    def test_nested_raw_vectors_round_trip_without_suffix_reads(self):
        page = raw.types.updates.ChannelDifference(
            pts=11, final=True, users=[raw.types.UserEmpty(id=7)], chats=[],
            new_messages=[raw.types.MessageEmpty(id=1), raw.types.MessageEmpty(id=2)],
            other_updates=[])
        wire = page.write()
        data = NoSuffixRead(wire)
        decoded = TLObject.read(data)
        self.assertEqual(wire, decoded.write())
        self.assertEqual(len(wire), data.tell())
