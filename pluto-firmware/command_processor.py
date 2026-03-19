import json
from crypto_utils import encrypt_aes_bytes, decrypt_aes_bytes
import time
from utils import csv_reader, generate_password
from backup_handler import handle_backup_command, BackupCommandError


DELAY = 0.0
DEBUG_MODE = True
SESSION_KEY  = bytes.fromhex("f3d1c97a8b4e234c2d10ab51f9c76aee")  # 128-bit key

class CommandProcessor:
    def __init__(self, hid_output, usb_output, authenticator):
        self.hid = hid_output
        self.usb = usb_output
        self.authenticator = authenticator
        self.master_key = None
        self.vault = None
        self.password = None
        self.same_used = False

    def _log_usb_error(self, where: str, exc: Exception) -> None:
        """Write a succinct error message to the USB port."""
        self.usb.write(f"Error ({where}): {exc}\n".encode())

    def secure_write(self, plaintext):
        try: 
            if DEBUG_MODE:
                data = str(plaintext).strip()
            else:
                data = encrypt_aes_bytes(str(plaintext), key=SESSION_KEY)

            self.usb.write(data + "\n")
            return True
        except Exception as exc:
            self._log_usb_error("secure_write", exc)
            return False
        
    def secure_read(self, command):
        try: 
            if not DEBUG_MODE:
                command = decrypt_aes_bytes(str(command), key=SESSION_KEY)
            return command.strip()
        except Exception as exc:
            self._log_usb_error("secure_read", exc)
            return None

    def execute(self, command):
        command = self.secure_read(command)
        print(f"Executing command: '{command}'")

        if command.startswith("encrypt "):
            try:
                # Remove the prefix
                _, raw = command.split(" ", 1)
                # Split into key and payload
                key_str, payload = raw.strip().split(":", 1)
                # Convert key string to bytes (assuming it's hex)
                key_bytes = bytes.fromhex(key_str)  # or base64.b64decode(key_str) if using base64
                # Encrypt using the provided key
                encrypted = encrypt_aes_bytes(plaintext=payload, key=key_bytes)
                self.secure_write(f"🔐 Encrypted (base64): {encrypted}")
            except ValueError:
                self.secure_write("❌ Error: Expected format 'encrypt <hexkey>:<payload>'")
            except Exception as e:
                self.secure_write(f"❌ Encryption failed: {e}")

        elif command.startswith("decrypt "):
            try:
                # Remove the prefix
                _, raw = command.split(" ", 1)
                # Split into key and payload
                key_str, payload = raw.strip().split(":", 1)
                # Convert key string to bytes (assuming it's hex)
                key_bytes = bytes.fromhex(key_str)  # or base64.b64decode(key_str) if using base64
                # Encrypt using the provided key
                decrypted = decrypt_aes_bytes(base64_input=payload, key=key_bytes)
                self.secure_write(f"🔓 Decrypted: {decrypted}")
            except ValueError:
                self.secure_write("❌ Error: Expected format 'decrypt <hexkey>:<payload>'")
            except Exception as e:
                self.secure_write(f"❌ Decryption failed: {e}")

        elif command.startswith("encrypt_save "):
            try:
                _, msg = command.split(" ", 1)
                msg = msg.strip()
                msg = msg.replace("'", "\"")  # Replace single quotes with double quotes for valid JSON

                # 1) Parse user input into dict (must be JSON object)
                try:
                    plaintext_dict = json.loads(msg)
                except Exception as e:
                    raise ValueError("Expected JSON object after encrypt_save, e.g. encrypt_save {\"a\":1}") from e

                if not isinstance(plaintext_dict, dict):
                    raise ValueError("encrypt_save expects a JSON object (dict).")

                # 2) Serialize dict to JSON string (this is what you'll encrypt)
                plaintext_json = json.dumps(plaintext_dict)

                encrypted = encrypt_aes_bytes(plaintext=plaintext_json, key=self.authenticator.get_backup_key())

                self.secure_write(f"🔐 Encrypted: {encrypted}\n")

            except Exception as e:
                self.secure_write(f"❌ encrypt_save failed: {e}\n")

        elif command.startswith("type "):
            _, domain = command.split(" ", 1)
            domain = domain.strip()
            try:
                vault = self.authenticator.get_vault()
                creds = vault.get(domain)
                if not creds:
                    self.secure_write("⚠️ Domain not found\n")
                    return
                self.secure_write(f"Typing...\n")
                time.sleep(1)
                if (len(creds["username"]) > 0):
                    self.hid.type_text(creds["username"], delay=DELAY)
                    self.hid.key_strokes("TAB")
                self.hid.type_text(creds["password"], delay=DELAY)
                self.hid.key_strokes("ENTER")
            except Exception as e:
                self.secure_write(f"❌ Error retrieving credentials: {e}\n")
                print(f"Error: {e}")

        elif command.startswith("add "):
            """add amazon:https://amazon.com,alice,"pa55,word",shopping account"""
            try:
                # Extract the data from the command: site:url,username,password,note
                raw_data = command[4:].strip()

                site, values = raw_data.split(":", 1)
                site = site.strip()

                # Use your custom csv_reader to handle quoted fields
                parts = next(csv_reader(values))
                if len(parts) < 2:
                    raise ValueError("Usage: add site:url,username,\"password\",note")

                url, username = parts[0], parts[1]
                username = parts[1]
                password = parts[2].strip() if len(parts) > 2 else ""
                if not password:
                    if self.password:
                        password = self.password
                    else:
                        raise ValueError("Password missing")
                note = parts[3] if len(parts) > 3 else ""
                
                # Add to vault
                vault = self.authenticator.get_vault()
                vault.add(site, url, username, password, note)
                self.secure_write(f"Added credentials\n")
                self.password = None
                self.same_used = False

            except Exception as e:
                self.secure_write(f"❌ Failed to add credentials: {e}\n")
        
        elif command.startswith("get "):
            _, domain = command.split(" ", 1)
            domain = domain.strip()
            try:
                vault = self.authenticator.get_vault()
                creds = vault.get(domain)
                if not creds:
                    self.secure_write(f"⚠️ Domain not found: {domain}\n")
                    return
                self.secure_write(f"{domain}: {creds}\n")
            except Exception as e:
                self.secure_write(f"❌ Error: retrieving credentials: {e}\n")
        
        elif command.startswith("showkeys"):
            try:
                vault = self.authenticator.get_vault()
                self.secure_write(f"{vault.get_aliases()}\n")
            except Exception as e:
                self.secure_write(f"❌ Error: retrieving credentials: {e}\n")

        elif command.startswith("delete "):
            _, domain = command.split(" ", 1)
            domain = domain.strip()

            try:
                vault = self.authenticator.get_vault()
                if vault.delete(domain):
                    self.secure_write(f"✅ Deleted credentials for {domain}\n")
                else:
                    self.secure_write("⚠️ Domain not found\n")
            except Exception as e:
                self.secure_write(f"❌ Failed to delete credentials: {e}\n")

        elif command.startswith("update "):
            """update example.com[username:alice_wonder,password:newP@ss,note:2FA enabled]"""
            try:
                domain, rest = command[7:].split("[", 1)
                domain = domain.strip()
                updates = rest.strip("[] ")

                vault = self.authenticator.get_vault()
                
                if not vault.update(domain, updates):
                    self.secure_write("⚠️ Failed to update credentials\n")
                    return
                self.secure_write(f"Modified credentials for {domain}\n")
            except Exception as e:
                self.secure_write(f"Failed to modify credentials: {e}\n")
        
        elif command.startswith("bulkadd "):
            """bulkadd <csv_blob>
            bulkadd amazon,amazon.com,alice,pa55,"personal inbox"\nbank,bank.com,bob,secret,"main repo"\nmybank,bank.example,carol,123456
            """
            # Everything after the first space
            csv_blob_raw = command[8:].lstrip()

            # Convert the visible back-slash-n into an actual newline character
            csv_blob = csv_blob_raw.replace("\\n", "\n")
            try:
                vault = self.authenticator.get_vault()

                added, updated, skipped = vault.import_csv(csv_blob)

                summary = "\n".join((
                    "Added:   "   + (", ".join(added)   or "-"),
                    "Updated: "   + (", ".join(updated) or "-"),
                    "Skipped: "   + (", ".join(skipped) or "-"),
                )) + "\n"
                self.secure_write(summary)
            except Exception as exc:
                self.secure_write(f"❌ Bulk-add failed: {exc}\n")

        elif command == "passwd" or command.startswith("passwd"):
            """passwd len=12,lvl=2 or passwd --same"""
            try:
                _, options = command.split(" ", 1)

                if options.strip() == "--same":
                    if not self.password:
                        raise ValueError("No passwd available")
                    if self.same_used:
                        self.password = None
                        raise ValueError("--same already used for this password")
                    self.hid.type_text(self.password, delay=DELAY)
                    self.secure_write(f"Typed\n")
                    self.same_used = True
                else:
                    params = {}
                    for opt in options.strip().split(","):
                        k, v = opt.split("=")
                        k = k.strip().lower()
                        if k not in ("len", "lvl"):
                            raise ValueError(f"Unknown parameter: '{k}'")
                        params[k] = int(v.strip())

                    self.password = generate_password(
                        length=params.get("len", 12),
                        level=params.get("lvl", 2)
                    )
                    self.same_used = False
                    self.hid.type_text(self.password, delay=DELAY)
                    self.secure_write(f"Typed\n")

            except Exception as e:
                self.secure_write(f"❌ Password generation failed: {e}\n")

        elif command.startswith("backup"):
            try:
                result = handle_backup_command(command, authenticator=self.authenticator)
                self.secure_write(f"{result}\n")
            except BackupCommandError as e:
                self.secure_write(f"❌ {e}\n")
            except Exception as e:
                self.secure_write(f"❌ Failed to backup credentials: {e}\n")
        elif command.lower() == "help":
            self.hid.type_text("Available: hello, greet, bye, encrypt <msg>, decrypt <base64>")
        else:
            print(f"Unknown command: '{command}'")