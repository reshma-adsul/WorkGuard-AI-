"""
WorkGuard AI - AES-256 Encryption Module
All logs are encrypted at rest. Only password holder can read them.
"""

import os
import base64
import hashlib
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class AESEncryptor:
    """AES-256-GCM encryption for log files"""

    def __init__(self, password: str):
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("Run: pip install cryptography")
        # Derive 256-bit key from password using SHA-256
        self.key = hashlib.sha256(password.encode()).digest()

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt string → bytes (nonce + tag + ciphertext)"""
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ct = encryptor.update(plaintext.encode()) + encryptor.finalize()
        tag = encryptor.tag  # 16-byte authentication tag
        # Format: [4-byte len][nonce][tag][ciphertext]
        payload = nonce + tag + ct
        size = len(payload).to_bytes(4, 'big')
        return size + payload

    def decrypt(self, data: bytes) -> str:
        """Decrypt bytes → string"""
        size = int.from_bytes(data[:4], 'big')
        payload = data[4:4 + size]
        nonce = payload[:12]
        tag   = payload[12:28]
        ct    = payload[28:]
        cipher = Cipher(
            algorithms.AES(self.key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return (decryptor.update(ct) + decryptor.finalize()).decode()

    def append_encrypted(self, filepath: Path, text: str):
        """Append encrypted chunk to file"""
        chunk = self.encrypt(text)
        with open(filepath.with_suffix('.enc'), 'ab') as f:
            f.write(chunk)

    def decrypt_file(self, enc_path: Path) -> str:
        """Read and decrypt entire .enc file"""
        result = []
        with open(enc_path, 'rb') as f:
            while True:
                size_bytes = f.read(4)
                if not size_bytes or len(size_bytes) < 4:
                    break
                size = int.from_bytes(size_bytes, 'big')
                payload = f.read(size)
                if len(payload) < size:
                    break
                try:
                    nonce = payload[:12]
                    tag   = payload[12:28]
                    ct    = payload[28:]
                    cipher = Cipher(
                        algorithms.AES(self.key),
                        modes.GCM(nonce, tag),
                        backend=default_backend()
                    )
                    dec = cipher.decryptor()
                    result.append((dec.update(ct) + dec.finalize()).decode())
                except Exception:
                    result.append("[DECRYPTION ERROR - Wrong password or corrupted chunk]")
        return "".join(result)


def derive_key_info(password: str) -> dict:
    """Return key fingerprint (for verification without exposing key)"""
    key = hashlib.sha256(password.encode()).digest()
    fingerprint = hashlib.md5(key).hexdigest()[:8].upper()
    return {"fingerprint": fingerprint, "algorithm": "AES-256-GCM"}
