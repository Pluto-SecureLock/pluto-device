import json
import os
import adafruit_hashlib as hashlib

IDENTITY_FILE = "sd/identity.db"
X25519_TEMP_FILE = "sd/x25519.tmp"

def _mock_public_from_private_seed(seed: bytes) -> bytes:
    """Lightweight stand-in for Ed25519 public-key derivation on constrained MCUs."""
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    # Deterministic 32-byte value so file integrity can be checked on load.
    return hashlib.sha256(b"ed25519-mock" + seed).digest()


def _mock_generate_x25519_keypair():
    """Return a mock X25519 (private, public) keypair as 32-byte values."""
    private_key = bytearray(os.urandom(32))

    # Keep private key shape close to real X25519 by clamping bits.
    private_key[0] &= 248
    private_key[31] &= 127
    private_key[31] |= 64

    private_key = bytes(private_key)
    public_key = hashlib.sha256(b"x25519-mock" + private_key).digest()
    return private_key, public_key


class IdentityManager:
    def __init__(self, path: str = IDENTITY_FILE, x25519_path: str = X25519_TEMP_FILE, atecc=None, public_key_source: str = "auto", atecc_slot: int = 0):
        self.path = path
        self.x25519_path = x25519_path
        self.atecc = atecc
        self.public_key_source = public_key_source
        self.atecc_slot = atecc_slot
        self._private_seed = None
        self._public_key = None
        self._public_key_source = None

    def _resolve_public_key_source(self, source: str = None, allow_fallback: bool = True) -> str:
        resolved = self.public_key_source if source is None else source
        if resolved == "auto":
            resolved = "atecc" if self.atecc is not None else "mock"
        if resolved == "atecc" and self.atecc is None:
            if allow_fallback:
                return "mock"
            raise RuntimeError("ATECC public key generation requested but no ATECC instance is available")
        return resolved

    def _atecc_public_from_private_seed(self, seed: bytes) -> bytes:
        if len(seed) != 32:
            raise ValueError("Ed25519 seed must be 32 bytes")
        if self.atecc is None:
            raise RuntimeError("ATECC instance is not configured")

        key_buffer = bytearray(64)
        key_output = self.atecc.gen_key(key_buffer, slot_num=self.atecc_slot, private_key=False)
        return hashlib.sha256(b"atecc-mock" + seed + bytes(key_output)).digest()

    def _derive_public_key(self, seed: bytes, source: str = None, allow_fallback: bool = True):
        resolved = self._resolve_public_key_source(source, allow_fallback=allow_fallback)
        if resolved == "atecc":
            return self._atecc_public_from_private_seed(seed), resolved
        return _mock_public_from_private_seed(seed), resolved

    def ensure_identity(self):
        seed, pub, source = self._load_identity()
        if seed and pub:
            self._private_seed = seed
            self._public_key = pub
            self._public_key_source = source
            return

        seed = os.urandom(32)
        pub, source = self._derive_public_key(seed)
        self._save_identity(seed, pub, source)
        self._private_seed = seed
        self._public_key = pub
        self._public_key_source = source

    def get_public_key_hex(self) -> str:
        if not self._public_key:
            self.ensure_identity()
        return self._public_key.hex()

    def generate_x25519_public_key_hex(self) -> str:
        priv, pub = _mock_generate_x25519_keypair()
        self._save_x25519_private_temporary(priv, pub)
        return pub.hex()

    def clear_x25519_temporary(self) -> bool:
        try:
            os.remove(self.x25519_path)
            return True
        except OSError:
            return False

    def _load_identity(self):
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
            seed = bytes.fromhex(data.get("id_priv", ""))
            pub = bytes.fromhex(data.get("id_pub", ""))
            source = data.get("pub_source", "mock")

            if len(seed) != 32 or len(pub) != 32:
                return None, None, None

            # Guard against file corruption by recomputing pub from seed.
            computed, resolved_source = self._derive_public_key(seed, source, allow_fallback=False)
            if computed != pub:
                return None, None, None

            return seed, pub, resolved_source
        except Exception:
            return None, None, None

    def _save_identity(self, seed: bytes, pub: bytes, source: str):
        data = {
            "id_priv": seed.hex(),
            "id_pub": pub.hex(),
            "pub_source": source,
            "mock": True,
        }
        with open(self.path, "w") as f:
            json.dump(data, f)

    def _save_x25519_private_temporary(self, private_key: bytes, public_key: bytes):
        data = {
            "x25519_priv": private_key.hex(),
            "x25519_pub": public_key.hex(),
            "mock": True,
            "temporary": True,
        }
        with open(self.x25519_path, "w") as f:
            json.dump(data, f)