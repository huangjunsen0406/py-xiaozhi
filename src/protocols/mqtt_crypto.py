"""MQTT/UDP 音频通道使用的 AES-CTR 加解密."""

from __future__ import annotations

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


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
