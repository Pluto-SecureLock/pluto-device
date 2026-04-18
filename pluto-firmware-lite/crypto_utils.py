import aesio
import os
import binascii
import adafruit_hashlib as hashlib
import circuitpython_hmac as hmac
import microcontroller

BLOCK_SIZE = 16
SALT_SIZE = 16

def pad(data):
    """Apply PKCS#7 padding."""
    pad_len = BLOCK_SIZE - (len(data) % BLOCK_SIZE)
    return data + bytes([pad_len]) * pad_len

def unpad(padded_data):
    """Remove PKCS#7 padding."""
    pad_len = padded_data[-1]
    if pad_len > BLOCK_SIZE or pad_len == 0:
        raise ValueError("Invalid padding")
    return padded_data[:-pad_len]

def encrypt_aes(plaintext, key_string):
    key = key_string.encode("utf-8")
    key = (key + b"\x00" * BLOCK_SIZE)[:BLOCK_SIZE]

    iv = os.urandom(BLOCK_SIZE)
    padded = pad(plaintext.encode("utf-8"))
    encrypted = bytearray(len(padded))

    cipher = aesio.AES(key, aesio.MODE_CBC, IV=iv)
    cipher.encrypt_into(padded, encrypted)

    result = iv + encrypted
    return binascii.b2a_base64(result).decode("utf-8").strip()

def decrypt_aes(base64_input, key_string):
    key = key_string.encode("utf-8")
    key = (key + b"\x00" * BLOCK_SIZE)[:BLOCK_SIZE]

    try:
        encrypted_data = binascii.a2b_base64(base64_input)
    except Exception:
        return "[ERROR] Invalid base64"

    if len(encrypted_data) < BLOCK_SIZE:
        return "[ERROR] Data too short"

    iv = encrypted_data[:BLOCK_SIZE]
    ciphertext = encrypted_data[BLOCK_SIZE:]
    decrypted = bytearray(len(ciphertext))

    cipher = aesio.AES(key, aesio.MODE_CBC, IV=iv)
    cipher.decrypt_into(ciphertext, decrypted)

    try:
        unpadded = unpad(decrypted)
        return unpadded.decode("utf-8")
    except Exception:
        return "[ERROR] Invalid padding or decoding"

def encrypt_aes_bytes(plaintext: str, key: bytes) -> str:
    """
    Encrypts the given plaintext using AES-CBC with the given binary key.
    Returns a base64-encoded string of IV + ciphertext.
    """
    key = (key + b"\x00" * BLOCK_SIZE)[:BLOCK_SIZE]  # Pad/truncate to 16 bytes

    iv = os.urandom(BLOCK_SIZE)
    padded = pad(plaintext.encode("utf-8"))
    encrypted = bytearray(len(padded))

    cipher = aesio.AES(key, aesio.MODE_CBC, IV=iv)
    cipher.encrypt_into(padded, encrypted)

    result = iv + encrypted
    return binascii.b2a_base64(result).decode("utf-8").strip()

def decrypt_aes_bytes(base64_input: str, key: bytes) -> str:
    """
    Decrypts the base64 input string using AES-CBC and the given binary key.
    Returns the plaintext as a UTF-8 string.
    """
    key = (key + b"\x00" * BLOCK_SIZE)[:BLOCK_SIZE]

    try:
        encrypted_data = binascii.a2b_base64(base64_input)
    except Exception:
        return "[ERROR] Invalid base64"

    if len(encrypted_data) < BLOCK_SIZE:
        return "[ERROR] Data too short"

    iv = encrypted_data[:BLOCK_SIZE]
    ciphertext = encrypted_data[BLOCK_SIZE:]
    decrypted = bytearray(len(ciphertext))

    cipher = aesio.AES(key, aesio.MODE_CBC, IV=iv)
    cipher.decrypt_into(ciphertext, decrypted)

    try:
        unpadded = unpad(decrypted)
        return unpadded.decode("utf-8")
    except Exception:
        return "[ERROR] Invalid padding or decoding"

def generate_salt() -> bytes:
    return os.urandom(SALT_SIZE)

def hash_pin(pin: bytes, salt: bytes) -> bytes:
    uid = microcontroller.cpu.uid
    h = hashlib.sha256()
    h.update(salt + pin + uid)
    return h.digest()

def hkdf_extract(salt: bytes, input_key_material: bytes) -> bytes:
    """HKDF-Extract step (RFC 5869)"""
    if not salt:
        salt = bytes([0] * hashlib.sha256().digest_size)
    return hmac.new(salt, input_key_material, hashlib.sha256).digest()

def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    """HKDF-Expand step (RFC 5869)"""
    hash_len = hashlib.sha256().digest_size
    blocks = []
    block = b""
    for counter in range(1, -(-length // hash_len) + 1):  # ceil(length/hash_len)
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        blocks.append(block)
    return b"".join(blocks)[:length]

def derive_key(template: bytes, salt: bytes = b"", info: bytes = b"fingerprint-key", length: int = 32) -> bytes:
    """Derive AES key from fingerprint template using HKDF (CircuitPython version)"""
    prk = hkdf_extract(salt, template)
    return hkdf_expand(prk, info, length)