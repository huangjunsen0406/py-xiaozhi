"""Exercise encrypted UDP datagrams without opening sockets or using devices."""

from collections import deque

import pytest

from src.protocols.mqtt_crypto import aes_ctr_encrypt
from src.protocols.mqtt_udp import MqttUdpChannel

_KEY = bytes.fromhex("00112233445566778899aabbccddeeff")
_NONCE = "01a70000010203040506070800000000"


class QueuedLoop:
    def __init__(self):
        self.pending = deque()

    def call_soon_threadsafe(self, callback, *args):
        self.pending.append((callback, args))

    def drain(self):
        while self.pending:
            callback, args = self.pending.popleft()
            callback(*args)


class DatagramSocket:
    def __init__(self, channel, packets):
        self.channel = channel
        self.packets = deque(packets)
        self.closed = False

    def recvfrom(self, size):
        if not self.packets:
            self.channel.running = False
            raise TimeoutError
        packet = self.packets.popleft()
        assert len(packet) <= size
        return packet, ("192.0.2.1", 8888)

    def close(self):
        self.closed = True


def _packet(sequence, payload=b"opus", *, kind=1, declared_len=None):
    # Deliberately use nonzero flags/ssrc/timestamp: only the documented type,
    # length and sequence fields constrain ingress, and all 16 bytes are the IV.
    header = (
        bytes((kind, 0xA7))
        + (len(payload) if declared_len is None else declared_len).to_bytes(2, "big")
        + bytes.fromhex("0102030405060708")
        + sequence.to_bytes(4, "big")
    )
    return header + aes_ctr_encrypt(_KEY, header, payload)


def _channel():
    loop = QueuedLoop()
    channel = MqttUdpChannel(loop)
    channel.configure("192.0.2.1", 8888, _KEY.hex(), _NONCE)
    received = []
    channel.set_audio_handler(received.append)
    return channel, loop, received


def _receive(channel, loop, packets):
    channel.socket = DatagramSocket(channel, packets)
    channel.running = True
    channel._receive_loop()
    loop.drain()


@pytest.fixture(autouse=True)
def forbid_real_socket(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Packet tests must not create real sockets")

    monkeypatch.setattr("src.protocols.mqtt_udp.socket.socket", fail)


def test_duplicate_and_out_of_order_packets_are_dropped_but_gaps_are_allowed():
    channel, loop, received = _channel()
    _receive(
        channel,
        loop,
        [
            _packet(1, b"first"),
            _packet(1, b"duplicate"),
            _packet(4, b"gap"),
            _packet(3, b"late"),
            _packet(0, b"old-zero"),
            _packet(5, b"next"),
        ],
    )
    assert received == [b"first", b"gap", b"next"]
    assert channel.remote_sequence == 5


def test_first_sequence_zero_is_accepted_once():
    channel, loop, received = _channel()
    _receive(channel, loop, [_packet(0, b"zero"), _packet(0), _packet(1, b"one")])
    assert received == [b"zero", b"one"]
    assert channel.remote_sequence == 1


def test_uint32_wraparound_accepts_new_packets_and_rejects_late_pre_wrap_packets():
    channel, loop, received = _channel()
    _receive(
        channel,
        loop,
        [
            _packet(0xFFFFFFFE, b"before"),
            _packet(0xFFFFFFFF, b"last"),
            _packet(0, b"wrapped"),
            _packet(0, b"duplicate"),
            _packet(0xFFFFFFFF, b"late"),
            _packet(2, b"gap"),
            _packet(1, b"late-one"),
        ],
    )
    assert received == [b"before", b"last", b"wrapped", b"gap"]
    assert channel.remote_sequence == 2


@pytest.mark.parametrize("distance", [0x80000000, 0x80000001, 0xFFFFFFFF])
def test_ambiguous_or_backward_serial_distances_do_not_advance_sequence(distance):
    channel, loop, received = _channel()
    _receive(channel, loop, [_packet(7), _packet((7 + distance) & 0xFFFFFFFF)])
    assert received == [b"opus"]
    assert channel.remote_sequence == 7
    _receive(channel, loop, [_packet(8, b"next")])
    assert received == [b"opus", b"next"]


def test_largest_unambiguous_forward_gap_is_accepted():
    channel, loop, received = _channel()
    _receive(channel, loop, [_packet(0), _packet(0x7FFFFFFF, b"forward")])
    assert received == [b"opus", b"forward"]
    assert channel.remote_sequence == 0x7FFFFFFF


@pytest.mark.parametrize(
    "malformed",
    [
        b"",
        b"\x01" * 15,
        _packet(100, kind=0),
        _packet(100, kind=2),
        _packet(100, declared_len=3),
        _packet(100, declared_len=5),
        _packet(100, declared_len=0xFFFF),
        _packet(100)[:-1],
        _packet(100) + b"trailing",
    ],
)
def test_malformed_packets_never_advance_sequence_or_deliver_audio(malformed):
    channel, loop, received = _channel()
    _receive(channel, loop, [malformed])
    assert received == []
    assert channel.remote_sequence == 0
    assert not channel._remote_sequence_received
    _receive(channel, loop, [_packet(0, b"valid")])
    assert received == [b"valid"]


def test_malformed_high_sequence_does_not_block_later_valid_packet():
    channel, loop, received = _channel()
    _receive(
        channel,
        loop,
        [_packet(1), _packet(100, declared_len=5), _packet(2, b"valid")],
    )
    assert received == [b"opus", b"valid"]
    assert channel.remote_sequence == 2


def test_zero_declared_payload_preserves_existing_protocol_compatibility():
    channel, loop, received = _channel()
    _receive(channel, loop, [_packet(0, b"")])
    assert received == [b""]
    assert channel._remote_sequence_received


@pytest.mark.parametrize("aes_key", [None, "not-hex", "aa"])
def test_unavailable_or_invalid_key_does_not_consume_sequence(aes_key):
    channel, loop, received = _channel()
    channel.aes_key = aes_key
    _receive(channel, loop, [_packet(0)])
    assert received == []
    assert not channel._remote_sequence_received
    channel.aes_key = _KEY.hex()
    _receive(channel, loop, [_packet(0, b"retry")])
    assert received == [b"retry"]


def test_configure_resets_sequence_history_for_new_session():
    channel, loop, received = _channel()
    _receive(channel, loop, [_packet(100)])
    channel.configure("192.0.2.1", 8888, _KEY.hex(), _NONCE)
    assert channel.remote_sequence == 0
    assert not channel._remote_sequence_received
    _receive(channel, loop, [_packet(0, b"new-session")])
    assert received == [b"opus", b"new-session"]


def test_reset_session_clears_sequence_history_and_closes_fake_socket():
    channel, loop, received = _channel()
    _receive(channel, loop, [_packet(100)])
    sock = channel.socket
    channel.reset_session()
    assert sock.closed
    assert channel.remote_sequence == 0
    assert not channel._remote_sequence_received
    assert channel.aes_key is None
    channel.configure("192.0.2.1", 8888, _KEY.hex(), _NONCE)
    _receive(channel, loop, [_packet(0, b"new-session")])
    assert received == [b"opus", b"new-session"]


def test_sequence_history_advances_even_without_an_audio_handler():
    channel, loop, received = _channel()
    channel.set_audio_handler(None)
    _receive(channel, loop, [_packet(10)])
    assert channel.remote_sequence == 10
    channel.set_audio_handler(received.append)
    _receive(channel, loop, [_packet(10), _packet(11, b"next")])
    assert received == [b"next"]
