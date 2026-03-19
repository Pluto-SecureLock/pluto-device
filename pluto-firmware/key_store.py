import gc
import json
from crypto_utils import decrypt_aes_bytes, encrypt_aes_bytes
from utils import csv_reader

KEYS_FILE = "sd/keys.db"

class KeyStore:
    def __init__(self, master_key):
        self.master_key = master_key  # raw string (authenticated)
        self.db = self._load_db()
        self._normalize_loaded_db()

    def _load_db(self):
        try:
            with open(KEYS_FILE, "r") as f:
                encrypted = f.read().strip()
                decrypted = decrypt_aes_bytes(base64_input=encrypted, key=self.master_key)
                return json.loads(decrypted)
        except Exception as e:
            print("⚠️ Failed to load key store:", e)
            return {}

    def _save(self):
        try:
            plaintext = json.dumps(self.db)
            encrypted = encrypt_aes_bytes(plaintext, self.master_key)
            with open(KEYS_FILE, "w") as f:
                f.write(encrypted)
            print("💾 Vault saved successfully.")
            return True
        except Exception as e:
            print("❌ Failed to save vault:", e)
            return e

    def _find_key(self, identifier: str):
        """Resolve an entry by URL key first, then by alias for compatibility."""
        if identifier in self.db:
            return identifier

        for key, entry in self.db.items():
            if isinstance(entry, dict) and entry.get("alias") == identifier:
                return key

        return None

    def _normalize_loaded_db(self):
        """Migrate legacy alias-keyed entries into URL-keyed entries."""
        normalized = {}
        changed = False

        for old_key, entry in self.db.items():
            if not isinstance(entry, dict):
                normalized[old_key] = entry
                continue

            url = entry.get("url", "").strip()
            alias = entry.get("alias")

            if not alias:
                alias = old_key
                entry["alias"] = alias
                changed = True

            if url:
                if url != old_key:
                    changed = True
                normalized[url] = entry
            else:
                # Keep malformed/legacy records reachable even without URL.
                normalized[old_key] = entry

        if changed:
            self.db = normalized
            self._save()

    def get_aliases(self):
        aliases = []
        for key, entry in self.db.items():
            if isinstance(entry, dict):
                aliases.append(entry.get("alias", key))
            else:
                aliases.append(key)
        return aliases

    def get(self, site):
        entry_key = self._find_key(site)
        if not entry_key:
            return None
        return self.db.get(entry_key)

    def add(self, site: str, url: str, username: str,
            password: str, note: str = "") -> None:
        """Add / overwrite one credential and persist."""
        url = url.strip()
        if not url:
            raise ValueError("URL is required")

        self.db[url] = {
            "alias": site,
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

            if skip_duplicates and url in self.db:
                skipped.append(url)
                continue

            (updated if url in self.db else added).append(name)
            self.add(name, url, user, pwd, note)

        return added, updated, skipped
    
    # def import_csv(self, csv_blob: str, *, skip_duplicates=False):
    #     added, updated, skipped = [], [], []

    #     for row_no, row in enumerate(csv_reader(csv_blob), 1):
    #         if len(row) < 4:
    #             skipped.append(f"line {row_no} (have {len(row)} cols)")
    #             continue

    #         name, url, user, pwd, *note = row
    #         note = note[0] if note else ""

    #         if skip_duplicates and name in self.db:
    #             skipped.append(name)
    #             continue

    #         (updated if name in self.db else added).append(name)
    #         self.db[name] = {"url": url, "username": user, "password": pwd, "note": note}

    #     # Save once
    #     self._save()
    #     return added, updated, skipped
    
    def delete(self, domain: str) -> bool:
        key = self._find_key(domain)
        if key in self.db:
            del self.db[key]
            self._save()
            return True
        else:
            return False
    
    def update(self, site: str, updates_string: str) -> bool:
        """Update an existing credential."""
        entry_key = self._find_key(site)
        if not entry_key:
            return False

        parsed_updates = list(csv_reader(updates_string))

        if not parsed_updates:
            return False

        for item_str in parsed_updates[0]: # Assuming a single row of updates
            if ':' not in item_str:
                continue
            
            field, value = item_str.split(":", 1) # Split only on the first colon in case value has colons
            self.db[entry_key][field.strip()] = value.strip()

        # Keep URL as the database key if URL was updated.
        new_url = self.db[entry_key].get("url", "").strip()
        if new_url and new_url != entry_key:
            self.db[new_url] = self.db.pop(entry_key)

        self._save()
        return True

    def backup(self, key_bytes: bytes) -> str:
        """
        Returns an encrypted blob (string) of the vault DB using key_bytes.
        """
        if not key_bytes:
            raise ValueError("Backup key is not set.")

        plaintext = json.dumps(self.db)
        return encrypt_aes_bytes(plaintext=plaintext, key=key_bytes)

    def restore(self, key_bytes: bytes, encrypted_blob: str, *, overwrite: bool = False):
        """
        Restore credentials from an encrypted backup blob.

        Behavior:
          - Decrypts encrypted_blob using key_bytes (the backup key).
          - If current DB is empty OR KEYS_FILE missing/unreadable, replaces entire DB.
          - Otherwise merges:
              - existing keys are updated with backup values
              - new keys are added
          - If overwrite=True, always replaces entire DB.

        Persists restored/merged DB encrypted with self.master_key via _save().

        Returns:
          dict with counts: {"added": int, "updated": int, "total_in_backup": int}
        """
        if not key_bytes:
            raise ValueError("Restore key is missing.")
        if not encrypted_blob:
            raise ValueError("Restore blob is missing.")

        # 1) Decrypt backup payload with backup key
        decrypted = decrypt_aes_bytes(base64_input=encrypted_blob, key=key_bytes)

        # 2) Parse JSON
        try:
            backup_db = json.loads(decrypted)
        except Exception as e:
            raise ValueError("Restore blob decrypted but is not valid JSON.") from e

        if not isinstance(backup_db, dict):
            try:
                backup_db = dict(backup_db)
            except Exception as e:
                raise ValueError(f"Restore payload is not a dict: {e}")

        # 3) Decide strategy: replace vs merge
        if overwrite or not self.db:
            self.db = backup_db
            self._save()
            self._normalize_loaded_db()
            return {
                "added": len(backup_db),
                "updated": 0,
                "total_in_backup": len(backup_db),
                "mode": "overwrite" if overwrite else "replace_empty",
            }

        # 4) Merge into existing DB
        added = 0
        updated = 0

        for site, entry in backup_db.items():
            if site in self.db:
                # Update entire entry (simpler + deterministic)
                self.db[site] = entry
                updated += 1
            else:
                self.db[site] = entry
                added += 1

        self._save()
        self._normalize_loaded_db()
        return {
            "added": added,
            "updated": updated,
            "total_in_backup": len(backup_db),
            "mode": "merge",
        }