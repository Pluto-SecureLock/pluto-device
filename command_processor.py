from aes_encryptor import encrypt_aes_cbc, decrypt_aes_cbc
#from key_store import KeyStore
import time

DELAY = 0.0

class CommandProcessor:
    def __init__(self, hid_output, usb_output, authenticator):
        self.hid = hid_output
        self.usb = usb_output
        self.authenticator = authenticator
        self.authenticated = False
        self.master_key = None
        self.vault = None
        

    def execute(self, command):
        command = command.strip()
        print(f"Executing command: '{command}'")

        if command.startswith("encrypt "):
            if not self.authenticated:
                print("🔒 Auth required before sending credentials.")
                return
            _, msg = command.split(" ", 1)
            encrypted = encrypt_aes_cbc(msg, key_string=self.master_key)
            print("🔐 Encrypted (base64):", encrypted)

        elif command.startswith("decrypt "):
            if not self.authenticated:
                print("🔒 Auth required before sending credentials.")
                return
            _, b64 = command.split(" ", 1)
            decrypted = decrypt_aes_cbc(b64, key_string=self.master_key)
            print("🔓 Decrypted:", decrypted)
            self.hid.type_text(decrypted, delay=0.2)

        elif command.startswith("auth "):
            _, auth = command.split(" ", 1)
            if auth is None:
                print("🔐 Usage: auth <masterkey>")
            elif auth == "?":
                self.usb.write(f"{self.authenticated}\n")
            elif self.authenticator.authenticate():
                print("✅ Authentication successful!")
                self.authenticated = True
                self.master_key = auth
                #self.vault = KeyStore(self.master_key)
            return self.authenticated
                
        elif command.startswith("encrypt_save "):
            _, msg = command.split(" ", 1)
            encrypted = encrypt_aes_cbc(msg, key_string=self.master_key)
# ��������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������������"⚠️ Domain not found\n")
        elif command.startswith("get "):
            if not self.authenticated:
                self.usb.write("🔒 Auth required before accessing vault.\n")
                return

            _, domain = command.split(" ", 1)
            domain = domain.strip()
            try:
                vault = self.authenticator.get_vault()
                creds = vault.get(domain)
                if not creds:
                    self.usb.write("⚠️ Domain not found\n")
                    return
                self.usb.write(f"🔑 Credentials for {domain}: {creds}\n")
                time.sleep(1)
                self.hid.type_text(creds["username"], delay=DELAY)
                self.hid.key_strokes("TAB")
                self.hid.type_text(creds["password"], delay=DELAY)
                self.hid.key_strokes("ENTER")
            except Exception as e:
                self.usb.write(f"❌ Error retrieving credentials: {e}\n")

        elif command.startswith("add "):
            try:
                domain, raw_data = command[4:].split("[", 1)
                domain = domain.strip()
                creds_data = raw_data.strip("] \n")

                data = {}
                for item in creds_data.split(","):
                    key, value = item.split(":")
                    data[key.strip()] = value.strip()

                vault = self.authenticator.get_vault()
                vault.db[domain] = data
                vault.update()
                self.usb.write(f"✅ Added credentials for {domain}\n")

            except Exception as e:
                self.usb.write(f"❌ Failed to add credentials: {e}\n")
        
        elif command.startswith("delete "):
            _, domain = command.split(" ", 1)
            domain = domain.strip()

            try:
                vault = self.authenticator.get_vault()
                if domain in vault.db:
                    del vault.db[domain]
                    vault.update()
                    self.usb.write(f"🗑️ Deleted credentials for {domain}\n")
                else:
                    self.usb.write("⚠️ Domain not found\n")
            except Exception as e:
                self.usb.write(f"❌ Failed to delete credentials: {e}\n")
                
        elif command.startswith("modify "):
            try:
                domain, rest = command[7:].split("[", 1)
                domain = domain.strip()
                updates = rest.strip("[] ")

                vault = self.authenticator.get_vault()
                if domain not in vault.db:
                    self.usb.write("⚠️ Domain not found\n")
                    return

                for item in updates.split(","):
                    key, value = item.split(":")
                    vault.db[domain][key.strip()] = value.strip()

                vault.update()
                self.usb.write(f"✏️ Modified credentials for {domain}\n")
            except Exception as e:
                self.usb.write(f"❌ Failed to modify credentials: {e}\n")

        elif command.lower() == "hello":
            self.hid.type_text("Hello people!!!", delay=0.2)
        elif command.lower() == "help":
            self.hid.type_text("Available: hello, greet, bye, encrypt <msg>, decrypt <base64>")
        else:
            print(f"Unknown command: '{command}'")
