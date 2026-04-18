import binascii
import os

from crypto_utils import generate_salt
from key_store import KeyStore
from nvm_storage import load_slot, save_slot


SLOT_SIZE = 128
KEY_SLOT = 1
BACKUP_KEY_SLOT = 2
DEBUG = True


class AuthManagerLite:
    """API-oriented authenticator that avoids fingerprint, screen and encoder dependencies."""

    def __init__(self):
        self._vault = None
        self._master_key = None

    @property
    def authenticated(self):
        return True

    @property
    def f_authenticated(self):
        return True

    def _set_slot(self, slot_index: int, salt: bytes, payload: bytes):
        save_slot(slot_index, SLOT_SIZE, salt, payload)
        if DEBUG:
            print("Slot {} updated.".format(slot_index))

    def _get_slot(self, slot_index: int):
        salt, payload = load_slot(slot_index, SLOT_SIZE)
        return salt, payload

    def _generate_master_key(self) -> bytes:
        # Keep key material device-tied and deterministic once stored in NVM.
        return os.urandom(32)

    def set_master_key(self):
        if not self.is_registered(KEY_SLOT):
            salt = generate_salt()
            self._set_slot(KEY_SLOT, salt, self._generate_master_key())

        _, key = self._get_slot(KEY_SLOT)
        self._master_key = key
        self._vault = KeyStore(self._master_key)
        if DEBUG:
            print("Master key ready: {}".format(binascii.hexlify(key).decode("utf-8")))
        return True

    def is_registered(self, slot: int = KEY_SLOT) -> bool:
        try:
            salt, payload = self._get_slot(slot)
            return salt is not None and payload is not None
        except Exception:
            return False

    def is_session_valid(self) -> bool:
        return self._vault is not None

    def ensure_authenticated(self) -> bool:
        if self._vault is None:
            self.set_master_key()
        return True

    def authenticate(self) -> bool:
        return self.ensure_authenticated()

    def get_vault(self):
        if self._vault is None:
            self.set_master_key()
        return self._vault

    def get_backup_key(self):
        try:
            _, key = self._get_slot(BACKUP_KEY_SLOT)
            if DEBUG:
                print("Backup key retrieved: {}".format(binascii.hexlify(key).decode("utf-8")))
            return key
        except Exception:
            return None

    def store_backup_key(self, key_bytes: bytes):
        salt = generate_salt()
        self._set_slot(BACKUP_KEY_SLOT, salt, key_bytes)
        if DEBUG:
            print("Backup key stored.")

    def has_backup_key(self) -> bool:
        try:
            return bool(self.get_backup_key())
        except Exception:
            return False
