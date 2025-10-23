import os
import json
import binascii
from key_store import KeyStore
from nvm_storage import save_slot, load_slot, nvm_wipe
from crypto_utils import generate_salt, hash_pin, derive_key


KEYS_FILE = "sd/keys.db"
SYS_PARAM_FILE = "sd/systemparam_finger.db"

THE_FILES = [KEYS_FILE, SYS_PARAM_FILE]

SLOT_SIZE = 128

PIN_SLOT = 0
KEY_SLOT = 1

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
     
    def _save_credentials(self, salt: bytes, hashed_password: str, path: str):
        data = {
            "salt": binascii.hexlify(salt).decode("utf-8"),
            "hash": hashed_password
        }
        with open(path, "w") as f:
            json.dump(data, f)
        print(f"💾 Credentials saved securely: {data}")

    def _load_credentials(self, path: str = SYS_PARAM_FILE):
        try:
            with open(path, "r") as f:
                data = json.load(f)
            salt = binascii.unhexlify(data["salt"])
            return salt, data["hash"]
        except:
            return None, None

    def _set_slot(self, slot_index: int, salt: bytes, hsh: bytes):
        save_slot(slot_index, SLOT_SIZE, salt, hsh)
        print(f"Slot {slot_index} updated.")

    def _get_slot(self, slot_index: int):
        salt, hsh = load_slot(slot_index, SLOT_SIZE)
        return salt, hsh

    def set_pin(self, pin: int) -> str:
        if not isinstance(pin, int) or not (0 <= pin <= 9999):
            raise ValueError("PIN must be a 4-digit number.")

        # if self._get_slot(PIN_SLOT) and not self.authenticate: #TODO
        #     raise ValueError("Please verify before setting a new one.")
        
        else:
            pin_bytes = pin.to_bytes(4, 'big')
            salt = generate_salt()
            pin_hash = hash_pin(pin_bytes, salt)
            self._set_slot(PIN_SLOT, salt, pin_hash)
            self.fingerprint.set_pin(pin)
            print("🔑 PIN set successfully.")
            self.fingerprint.initialize()
            return pin_hash
    
    @property
    def authenticated(self):
        return self._authenticated
    
    @property
    def f_authenticated(self):
        return self._f_authenticated
    
    def verify_pin(self, pin: int) -> bool:
        self._reset_authentication()
        try:
            pin_bytes = pin.to_bytes(4, 'big')
            salt, stored_hash = self._get_slot(PIN_SLOT)

            if hash_pin(pin_bytes, salt) == stored_hash:
                self._authenticated = True
            return self._authenticated
        
        except Exception as e:
            print("❌ Error verifying PIN:", e)
            return False

    def _reset_authentication(self):
        self._authenticated = False
    
    def _reset_f_authentication(self):
        self._f_authenticated = False

    def is_registered(self, slot: int = PIN_SLOT) -> bool:
        try:
            salt, stored_hash = self._get_slot(slot)
            return salt is not None and stored_hash is not None
        except:
            return False

#TODO: This function is not used anywhere
    def read_sysparams_and_compare(self, path: str = SYS_PARAM_FILE) -> bool:
        print("📟 Reading system parameters...")
        params_string = self.fingerprint.check_system_parameters()  # Returns serialized string
        try:
            salt, stored_hash = self._load_credentials(path)
        except Exception as e:
            print(f"⚠️ Could not load saved hash: {e}")
            print("💾 Saving current system parameters as baseline.")
            salt = generate_salt()
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
        if not self.is_registered(KEY_SLOT):
            template = self.fingerprint.get_template()
            salt = generate_salt()
            print(f"🔑 MASTER Template: {binascii.hexlify(template).decode('utf-8')}")
            aes_key = derive_key(template=template, salt=salt)
            try:
                self._set_slot(KEY_SLOT, salt, aes_key)
                return True
            except Exception as e:
                print(f"❌ Error saving master key: {e}")
        return False
    
    def compare_master_key(self):
        if not self.is_registered(KEY_SLOT):
            self.set_master_key()
        salt, key = self._get_slot(KEY_SLOT)
        template = self.fingerprint.get_template()
        print(f"🔑 Template retrieved: {binascii.hexlify(template).decode('utf-8')}")
        self.master_key = derive_key(template=template, salt=salt)
        if DEBUG:
            print(f"🔑 Master key derived: {binascii.hexlify(self.master_key).decode('utf-8')}")
            print(f"🔑 Master key original: {binascii.hexlify(key).decode('utf-8')}")
            print(f"🔑 Master key match: {self.master_key == key}")
        return True if self.master_key else False

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

    def _retrieve_master_key(self):
        _ , key = self._get_slot(KEY_SLOT)
        print(f"🔑 Master key retrieved: {binascii.hexlify(key).decode('utf-8')}")
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

        if failed_files and not nvm_wipe():
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