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
    def __init__(self, path: str = IDENTITY_FILE, x25519_path: str = X25519_TEMP_FILE):
        self.path = path
        self.x25519_path = x25519_path
        self._private_seed = None
        self._public_key = None

    def ensure_identity(self):
        seed, pub = self._load_identity()
        if seed and pub:
            self._private_seed = seed
            self._public_key = pub
            return

        seed = os.urandom(32)
        pub = _mock_public_from_private_seed(seed)
        self._save_identity(seed, pub)
        self._private_seed = seed
        self._public_key = pub

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

            if len(seed) != 32 or len(pub) != 32:
                return None, None

            # Guard against file corruption by recomputing pub from seed.
            computed = _mock_public_from_private_seed(seed)
            if computed != pub:
                return None, None

            return seed, pub
        except Exception:
            return None, None

    def _save_identity(self, seed: bytes, pub: bytes):
        data = {
            "id_priv": seed.hex(),
            "id_pub": pub.hex(),
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