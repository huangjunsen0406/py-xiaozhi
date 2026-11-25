"""MQTT/UDP 音频通道使用的 AES-CTR 加解密与 UDP 探测 HMAC 认证."""

from __future__ import annotations

import hashlib
import hmac
import struct

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PROBE_TYPE_PING = 0x02
PROBE_TYPE_PONG = 0x03
PROBE_DATAGRAM_SIZE = 32
_PROBE_PAYLOAD_LEN = 16


def encode_probe(kind: int, key: bytes, ssrc: bytes, probe_seq: int) -> bytes:
    """编码 32 字节 MQTT/UDP 认证探测包（见 xiaozhi-esp32/docs/mqtt-udp-probe_zh.md）."""
    if kind not in (PROBE_TYPE_PING, PROBE_TYPE_PONG):
        raise ValueError("invalid probe type")
    if len(key) != 16 or len(ssrc) != 4:
        raise ValueError("invalid key or SSRC length")
    if not 1 <= probe_seq <= 0xFFFFFFFF:
        raise ValueError("invalid probe sequence")
    header = struct.pack("!BBH4sII", kind, 0, _PROBE_PAYLOAD_LEN, ssrc, 0, probe_seq)
    return header + hmac.new(key, header, hashlib.sha256).digest()[:16]


def matches_pending_pong(data: bytes, pending_ping: bytes, key: bytes) -> bool:
    """校验收到的 32 字节数据报是否为当前 pending PING 的合法认证 PONG."""
    if len(data) != PROBE_DATAGRAM_SIZE or len(pending_ping) != PROBE_DATAGRAM_SIZE:
        return False
    if len(key) != 16:
        return False
    if data[0] != PROBE_TYPE_PONG or data[1:16] != pending_ping[1:16]:
        return False
    expected = hmac.new(key, data[:16], hashlib.sha256).digest()[:16]
    return hmac.compare_digest(data[16:], expected)


def decode_probe_credentials(aes_key_hex: str, aes_nonce_hex: str) -> tuple[bytes, bytes]:
    """从 hello.udp.key/nonce 解码 16 字节原始密钥与 4 字节 SSRC（nonce[4:8]）."""
    if not isinstance(aes_key_hex, str) or not isinstance(aes_nonce_hex, str):
        raise ValueError("UDP key/nonce must be hex strings")
    key = bytes.fromhex(aes_key_hex)
    nonce = bytes.fromhex(aes_nonce_hex)
    if len(key) != 16 or len(nonce) != 16:
        raise ValueError("UDP key/nonce must be 16 bytes")
    return key, nonce[4:8]


def aes_ctr_encrypt(key: bytes, nonce: bytes, plaintext: bytes) -> bytes:
    """AES-CTR 加密.

    Args:
        key: 密钥
        nonce: 初始向量（与解密时一致）
        plaintext: 明文
    """
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    encryptor = cipher.encryptor()
    return encryptor.update(plaintext) + encryptor.finalize()


def aes_ctr_decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """AES-CTR 解密.

    Args:
        key: 密钥
        nonce: 与加密相同的 nonce
        ciphertext: 密文
    """
    cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def build_audio_nonce(aes_nonce_hex: str, audio_len: int, sequence: int) -> str:
    """构造 UDP 音频包 nonce（hex 字符串）.

    格式: 固定前缀 4 hex + 长度 4 hex + 原始 nonce 16 hex + 序列号 8 hex
    """
    return (
        aes_nonce_hex[:4]
        + format(audio_len, "04x")
        + aes_nonce_hex[8:24]
        + format(sequence, "08x")
    )
