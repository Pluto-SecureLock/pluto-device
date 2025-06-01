import json
import os
from aes_encryptor import decrypt_aes_cbc_bytes, encrypt_aes_cbc_bytes

KEYS_FILE = "sd/keys.db"

class KeyStore:
    def __init__(self, master_key):
        self.master_key = master_key  # raw string (authenticated)
        self.db = self._load_db()

    def _load_db(self):
        try:
            with open(KEYS_FILE, "r") as f:
                encrypted = f.read().strip()
                decrypted = decrypt_aes_cbc_bytes(base64_input=encrypted, key=self.master_key)
                return json.loads(decrypted)
        except Exception as e:
            print("⚠️ Failed to load key store:", e)
            return {}

    def get(self, site):
        return self.db.get(site)

    def add(self, site, username, password):
        self.db[site] = {"username": username, "password": password}
        self._save()
    
    def delete(self,domain):
        if domain in self.db:
            del self.db[domain]
            self._save()
            return True
        else:
            return False

    def _save(self):
        try:
            plaintext = json.dumps(self.db)
            encrypted = encrypt_aes_cbc_bytes(plaintext, self.master_key)
            with open(KEYS_FILE, "w") as f:
                f.write(encrypted)
            print("💾 Vault saved successfully.")
        except Exception as e:
            print("❌ Failed to save vault:", e)
