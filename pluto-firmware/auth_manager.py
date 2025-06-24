import os
import json
import binascii
import adafruit_hashlib as hashlib
from key_store import KeyStore
import circuitpython_hmac as hmac

AUTH_FILE = "sd/auth.db"
SECRET_FILE = "sd/secret.db"
KEYS_FILE = "sd/keys.db"
SYS_PARAM_FILE = "sd/systemparam_finger.db"

THE_FILES = [AUTH_FILE, SECRET_FILE, KEYS_FILE, SYS_PARAM_FILE]

SALT_SIZE = 16  # 128-bit salt
DEBUG = True

class AuthManager:
    def __init__(self):
        self.fingerprint = None
        self._authenticated = False
        self._f_authenticated = False
        self._vault = None
        self._master_key = None
        pass
    
    def attach_fingerprint(self, fingerprint):
        self.fingerprint = fingerprint

    def generate_salt(self) -> bytes:
        return os.urandom(SALT_SIZE)

    def hash_password(self, password: bytes, salt: bytes) -> str:
        combined = salt + password
        hashed = hashlib.sha256(combined).digest()
        return binascii.hexlify(hashed).decode("utf-8")

    def _hkdf_extract(self,salt: bytes, input_key_material: bytes) -> bytes:
        """HKDF-Extract step (RFC 5869)"""
        if not salt:
            salt = bytes([0] * hashlib.sha256().digest_size)
        return hmac.new(salt, input_key_material, hashlib.sha256).digest()
     
    def _hkdf_expand(self, prk: bytes, info: bytes, length: int) -> bytes:
        """HKDF-Expand step (RFC 5869)"""
        hash_len = hashlib.sha256().digest_size
        blocks = []
        block = b""
        for counter in range(1, -(-length // hash_len) + 1):  # ceil(length/hash_len)
            block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
            blocks.append(block)
        return b"".join(blocks)[:length]

    def _derive_key_from_template(self,template: bytes, salt: bytes = b"", info: bytes = b"fingerprint-key", length: int = 32) -> bytes:
        """Derive AES key from fingerprint template using HKDF (CircuitPython version)"""
        prk = self._hkdf_extract(salt, template)
        return self._hkdf_expand(prk, info, length)
           
    def _save_credentials(self, salt: bytes, hashed_password: str, path: str):
        data = {
            "salt": binascii.hexlify(salt).decode("utf-8"),
            "hash": hashed_password
        }
        with open(path, "w") as f:
            json.dump(data, f)
        print(f"💾 Credentials saved securely: {data}")

    def _load_credentials(self, path: str = AUTH_FILE):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            salt = binascii.unhexlify(data["salt"])
            return salt, data["hash"]
        except:
            return None, None

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
            #TODO: if fingerprint is non initialized, it will not work
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
    
    def _reset_f_authentication(self):
        self._f_authenticated = False

    def is_registered(self, path = AUTH_FILE) -> bool:
        try:
            with open(path, "r") as f:
                data = json.load(f)
            return "hash" in data and "salt" in data
        except:
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
        
    def set_master_key(self):
        if not self.is_registered(SECRET_FILE):
            template = self.fingerprint.get_template()
            salt = self.generate_salt()
            aes_key = self._derive_key_from_template(template, salt)
            try :
                self._save_credentials(salt, binascii.hexlify(aes_key).decode("utf-8"), SECRET_FILE)
                return True
            except Exception as e:
                print(f"❌ Error saving master key: {e}")
        return False
    
    def get_master_key(self):
        if not self.is_registered(SECRET_FILE):
            self.set_master_key()
        salt , key = self._load_credentials(SECRET_FILE)
        template = self.fingerprint.get_template()
        self._master_key = self._derive_key_from_template(template, salt)
        if DEBUG: 
            print(f"🔑 Master key derived: {binascii.hexlify(self._master_key).decode('utf-8')}")
            print(f"🔑 Master key original: {key}")
        return True if self._master_key else False

    def authenticate(self) -> bool:
        """Attempts to authenticate via fingerprint sensor and load master key into vault."""
        if not self.fingerprint:
            raise RuntimeError("No fingerprint sensor attached.")

        self._reset_f_authentication()
        self.fingerprint.authenticate()

        if not self.fingerprint.authenticated:
            return False

        self._f_authenticated = True

        master_key = self._retrieve_master_key()
        if master_key:
            self._master_key = master_key
            self._vault = KeyStore(self._master_key)
            return True

        return False

    def _retrieve_master_key(self, path: str = SECRET_FILE):
        _ , key = self._load_credentials(path)
        key = bytes.fromhex(key)
        print(f"🔑 Master key retrieved: {key}")
        return key

    def get_vault(self):
        if not self._f_authenticated or not self._vault:
            raise PermissionError("🔒 Not authenticated or vault not loaded.")
        return self._vault
    
    def update_fingerprint(self, fingerprint_id):
        if isinstance(fingerprint_id, int):
            if self.authenticate():
               return self.fingerprint.update(fingerprint_id)
        else:
            print("❌ Invalid fingerprint ID")
        return False
    
    def factory_reset(self):
        if not self.authenticate():
            print("❌ Authentication failed. Factory reset aborted.")
            return False

        failed_files = [f for f in THE_FILES if not self._try_delete(f)]

        if failed_files:
            print(f"❌ Could not delete: {', '.join(failed_files)}.")

        self.fingerprint.delete_all()
        print("🧼 All files and fingerprint data erased.")
        return True

    def _try_delete(self,filename):
        try:
            os.remove(filename)
            print(f"✅ {filename} deleted.")
            return True
        except OSError:
            print(f"⚠️ {filename} not found or could not be deleted.")
            return False