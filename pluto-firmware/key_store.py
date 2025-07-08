import json
from aes_encryptor import decrypt_aes_cbc_bytes, encrypt_aes_cbc_bytes
from utils import csv_reader

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

    def add(self, site: str, url: str, username: str,
            password: str, note: str = "") -> None:
        """Add / overwrite one credential and persist."""
        self.db[site] = {
            "url": url,
            "username": username,
            "password": password,
            "note": note,
        }
        self._save()


    def import_csv(self, csv_blob: str, *, skip_duplicates=False):
        added, updated, skipped = [], [], []

        for row_no, row in enumerate(csv_reader(csv_blob), 1):
            if len(row) < 4:              # note is optional
                skipped.append(f"line {row_no} (have {len(row)} cols)")
                continue

            name, url, user, pwd, *note = row
            note = note[0] if note else ""

            if skip_duplicates and name in self.db:
                skipped.append(name)
                continue

            (updated if name in self.db else added).append(name)
            self.add(name, url, user, pwd, note)

        return added, updated, skipped
    
    def delete(self, domain: str) -> bool:
        if domain in self.db:
            del self.db[domain]
            self._save()
            return True
        else:
            return False
    
    def update(self, site: str, updates_string: str) -> bool:
        """Update an existing credential."""
        if site not in self.db:
            return False

        parsed_updates = list(csv_reader(updates_string))

        if not parsed_updates:
            return False

        for item_str in parsed_updates[0]: # Assuming a single row of updates
            if ':' not in item_str:
                continue
            
            key, value = item_str.split(":", 1) # Split only on the first colon in case value has colons
            self.db[site][key.strip()] = value.strip()

        self._save()
        return True
    
    def _save(self):
        try:
            plaintext = json.dumps(self.db)
            encrypted = encrypt_aes_cbc_bytes(plaintext, self.master_key)
            with open(KEYS_FILE, "w") as f:
                f.write(encrypted)
            print("💾 Vault saved successfully.")
        except Exception as e:
            print("❌ Failed to save vault:", e)
