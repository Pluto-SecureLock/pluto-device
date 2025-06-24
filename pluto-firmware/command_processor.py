from aes_encryptor import encrypt_aes_cbc_bytes, decrypt_aes_cbc_bytes
import time

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

    def _log_usb_error(self, where: str, exc: Exception) -> None:
        """Write a succinct error message to the USB port."""
        self.usb.write(f"Error ({where}): {exc}\n".encode())

    def secure_write(self, plaintext):
        try: 
            if DEBUG_MODE:
                data = str(plaintext).strip()
            else:
                data = encrypt_aes_cbc_bytes(str(plaintext) , key=SESSION_KEY) 

            self.usb.write(data + "\n")
            return True
        except Exception as exc:
            self._log_usb_error("secure_write", exc)
            return False
        
    def secure_read(self, command):
        try: 
            if not DEBUG_MODE:
                command = decrypt_aes_cbc_bytes(str(command) , key=SESSION_KEY) 
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
                encrypted = encrypt_aes_cbc_bytes(plaintext=raw, key=key_bytes)

                self.secure_write(f"🔐 Encrypted (base64): {encrypted}")

            except ValueError:
                self.secure_write("❌ Error: Expected format 'encrypt key:<hexkey> <payload>'")
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
                decrypted = decrypt_aes_cbc_bytes(base64_input=raw, key=key_bytes)

                self.secure_write(f"🔓 Decrypted: {decrypted}")

            except ValueError:
                self.secure_write("❌ Error: Expected format 'encrypt key:<hexkey> <payload>'")
            except Exception as e:
                self.secure_write(f"❌ Encryption failed: {e}")

        elif command.startswith("encrypt_save "):
            _, msg = command.split(" ", 1)
            encrypted = encrypt_aes_cbc_bytes(msg, key_string=self.master_key)
            
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
                self.hid.type_text(creds["username"], delay=DELAY)
                self.hid.key_strokes("TAB")
                self.hid.type_text(creds["password"], delay=DELAY)
                self.hid.key_strokes("ENTER")
            except Exception as e:
                self.secure_write(f"❌ Error retrieving credentials: {e}\n")
                print(f"Error: {e}")

        elif command.startswith("add "):
            """add amazon:https://amazon.com,alice,pa55,"shopping account"""
            try:
                # Extraer los datos desde el comando: site:url,username,password,note
                raw_data = command[4:].strip()

                # Separar por ":" para obtener el nombre del sitio y los valores
                site, values = raw_data.split(":", 1)

                # Separar los valores por coma: url, username, password, note (nota es opcional)
                parts = [part.strip() for part in values.split(",")]

                if len(parts) < 3:
                    self.secure_write("❌ Missing required fields. Usage: add site:url,username,password[,note]\n")
                    return

                url = parts[0]
                username = parts[1]
                password = parts[2]
                note = parts[3] if len(parts) > 3 else ""

                # Añadir al vault
                vault = self.authenticator.get_vault()
                vault.add(site, url, username, password, note)
                self.secure_write(f"✅ Added credentials for {site}\n")

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
                self.secure_write(f"{list(vault.db.keys())}\n")
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

        elif command.startswith("modify "):
            """modify example.com[username:alice_wonder,password:newP@ss,note:2FA enabled]"""
            try:
                domain, rest = command[7:].split("[", 1)
                domain = domain.strip()
                updates = rest.strip("[] ")

                vault = self.authenticator.get_vault()
                
                if not vault.update(domain, updates):
                    self.secure_write("⚠️ Failed to update credentials\n")
                    return
                self.secure_write(f"✏️ Modified credentials for {domain}\n")
            except Exception as e:
                self.secure_write(f"❌ Failed to modify credentials: {e}\n")
        
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
                self.secure_write(f"{csv_blob}\n")
                added, updated, skipped = vault.import_csv(csv_blob)

                summary = "\n".join((
                    "Added:   "   + (", ".join(added)   or "-"),
                    "Updated: "   + (", ".join(updated) or "-"),
                    "Skipped: "   + (", ".join(skipped) or "-"),
                )) + "\n"
                self.secure_write(summary)
            except Exception as exc:
                self.secure_write(f"❌ Bulk-add failed: {exc}\n")

        elif command.lower() == "help":
            self.hid.type_text("Available: hello, greet, bye, encrypt <msg>, decrypt <base64>")
        else:
            print(f"Unknown command: '{command}'")
