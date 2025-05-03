import os
import json
import binascii
import adafruit_hashlib as hashlib
from key_store import KeyStore

AUTH_FILE = "sd/auth.db"
SYS_PARAM_FILE = "sd/systemparam_finger.json"
SALT_SIZE = 16  # 128-bit salt


class AuthManager:
    def __init__(self):
        self.fingerprint = None
        self._authenticated = False
        self._f_authenticated = False
        self._vault = None
        pass
    
    def attach_fingerprint(self, fingerprint):
        self.fingerprint = fingerprint

    def generate_salt(self) -> bytes:
        return os.urandom(SALT_SIZE)

    def hash_password(self, password: bytes, salt: bytes) -> str:
        combined = salt + password
        hashed = hashlib.sha256(combined).digest()
        return binascii.hexlify(hashed).decode("utf-8")

    def _save_credentials(self, salt: bytes, hashed_password: str, path: str):
        data = {
            "salt": binascii.hexlify(salt).decode("utf-8"),
            "hash": hashed_password
        }
        with open(path, "w") as f:
            json.dump(data, f)
        print(f"💾 Credentials saved securely: {data}")

    def _load_credentials(self, path: str = AUTH_FILE):
        with open(path, "r") as f:
            data = json.load(f)
        salt = binascii.unhexlify(data["salt"])
        return salt, data["hash"]

# TODO: Only if auth.db is empty or not present
# Otherwise ask for PIN and verifies before setting it
    def set_pin(self, pin: int, path: str = AUTH_FILE) -> str:
        if not isinstance(pin, int) or not (0 <= pin <= 9999):
            raise ValueError("PIN must be a 4-digit number.")
        
        if self._load_credentials() and not self.authenticate: #TODO 
            raise ValueError("Please verify before setting a new one.")
        
        else:
            pin_bytes = pin.to_bytes(4, 'big')
            salt = self.generate_salt()
            pin_hash = self.hash_password(pin_bytes, salt)
            self._save_credentials(salt, pin_hash, path)
            self.fingerprint.set_pin(pin)
            print("🔑 PIN set successfully.")
            return pin_hash
    
    @property
    def authenticated(self):
        return self._authenticated
    
    @property
    def f_authenticated(self):
        return self._f_authenticated
    
    def verify_pin(self, pin: int) -> bool:
        self._reset_authentication()
        path = AUTH_FILE
        try:
            pin_bytes = pin.to_bytes(4, 'big')
            salt, stored_hash = self._load_credentials(path)

            if self.hash_password(pin_bytes, salt) == stored_hash:
                self._authenticated = True
            return self._authenticated
        
        except Exception as e:
            print("❌ Error verifying PIN:", e)
            return False

    def _reset_authentication(self):
        self._authenticated = False

    def is_registered(self, path: str = AUTH_FILE) -> bool:
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return "hash" in data and "salt" in data
        except FileNotFoundError:
            return False

    def read_sysparams_and_compare(self, path: str = SYS_PARAM_FILE) -> bool:
        print("📟 Reading system parameters...")
        params_string = self.fingerprint.check_system_parameters()  # Returns serialized string
        try:
            salt, stored_hash = self._load_credentials(path)
        except Exception as e:
            print(f"⚠️ Could not load saved hash: {e}")
            print("💾 Saving current system parameters as baseline.")
            salt = self.generate_salt()
            hashed = self.hash_password(params_string.encode("utf-8"), salt)
            self._save_credentials(salt, hashed, path)
            return True

        current_hash = self.hash_password(params_string.encode("utf-8"), salt)
        if current_hash == stored_hash:
            print("✅ System parameters match saved fingerprint")
            return True
        else:
            print("❌ System parameter hash mismatch — possible tampering or change")
            return False

    def authenticate(self) -> bool:
        # self.fingerprint.authenticate()
        # return self.fingerprint.authenticated
        # # if self.fingerprint.authenticated:
        # #     print("✅ Fingerprint authenticated")
        # #     self.vault = KeyStore("ALOJHOMORE24")
        # #     return self.vault

        if not self.fingerprint:
            raise RuntimeError("No fingerprint sensor attached.")
        
        master_key = "ALOJHOMORE24"

        self.fingerprint.authenticate()
        if self.fingerprint.authenticated:
            self._f_authenticated = True
            if master_key:
                self._master_key = master_key
                self._vault = KeyStore(self._master_key)
            return True
        return False
    
    def get_vault(self):
        if not self._f_authenticated or not self._vault:
            raise PermissionError("🔒 Not authenticated or vault not loaded.")
        return self._vault