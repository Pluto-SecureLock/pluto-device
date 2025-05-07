import time
from utils import generate_password

# --- Base State Class --- #
class BaseState:
    def __init__(self, context):
        self.context = context

    def enter(self):
        """Called when this state becomes active."""
        pass

    def handle(self):
        """Process inputs or events."""
        raise NotImplementedError

    def exit(self):
        """Called when exiting this state."""
        pass

# --- State Implementations --- #
class SetupState(BaseState):
    def enter(self):
        self.context.tft.clear()
        self.context.tft.write("Initial Setup...", x=10, y=10)

        # PIN setup
        self.context.tft.write("🔑 Set 4-digit PIN", x=10, y=40)
        self.pin_helper = PinEntryHelper(self.context.encoder, self.context.tft, prompt="Enter your Admin PIN")

    def handle(self):
        self.pin_helper.update()

        if self.pin_helper.is_done():
            new_pin = self.pin_helper.get_pin()

            self.context.authenticator.set_pin(new_pin)
            self.context.tft.write("✅ PIN updated!", x=10, y=80, identifier="done")
            time.sleep(1)
            self.context.transition_to(AutoState(self.context))

    def exit(self):
        self.context.tft.clear()

class UnblockState(BaseState):
    def enter(self):
        if not self.context.authenticator.is_registered():
            print("SET UP A NEW PIN")
            self.context.transition_to(SetupState(self.context))
        self.pin_helper = PinEntryHelper(self.context.encoder, self.context.tft, prompt="Enter Admin PIN")
        
    def handle(self):
        self.pin_helper.update()

        if self.pin_helper.is_done():
            pin = self.pin_helper.get_pin()

            if self.context.authenticator.verify_pin(pin):
                self.context.initialize_fingerprint(pin)
                self.context.transition_to(AutoState(self.context))
            else:
                self.context.tft.update("pin_view", "❌ Wrong PIN")
                time.sleep(1)
                self.context.transition_to(UnblockState(self.context))

    def exit(self):
        self.context.tft.clear()

class PinEntryHelper:
    def __init__(self, encoder, tft, prompt="Enter PIN"):
        self.encoder = encoder
        self.tft = tft
        self.prompt = prompt
        self.digits = [0, 0, 0, 0]
        self.index = 0
        self._done = False
        self.last_rendered = ""

        self.tft.clear()
        self.tft.write(self.prompt, x=10, y=30, identifier="pin_prompt")
        self.tft.write("PIN: 0000", x=10, y=50, identifier="pin_view")

    def update(self):
        if self._done:
            return

        direction = self.encoder.get_direction()
        if direction == "CW":
            self.digits[self.index] = (self.digits[self.index] + 1) % 10
        elif direction == "CCW":
            self.digits[self.index] = (self.digits[self.index] - 1) % 10

        pin_str = ''.join(str(d) for d in self.digits)
        if direction in ("CW", "CCW") and pin_str != self.last_rendered:
            self.tft.update("pin_view", f"PIN: {pin_str}")
            self.last_rendered = pin_str

        if self.encoder.was_pressed():
            self.index += 1
            time.sleep(0.2)  # debounce
            if self.index >= 4:
                self._done = True

    def is_done(self):
        return self._done

    def get_pin(self) -> int:
        return int(''.join(str(d) for d in self.digits))


class AutoState(BaseState):
    def enter(self):
        self.context.tft.clear()
        self.context.tft.write("Send Command O.o ...", x=10, y=10, identifier="auto_view")
        if not self.context.processor.authenticated:
            self.context.tft.write("Not Authenticated", x=10, y=50, identifier="waiting_view")
        else:
            self.context.tft.write("Authenticated! >:)", x=10, y=50, identifier="waiting_view")
        self.context.usb.write("\U0001F4E5 Ready to receive commands over USB Serial...\n")

    def handle(self):
        command = self.context.usb.read(echo=False)
        if command:
            if not self.context.processor.authenticated and command.startswith("auth "):
                if self.context.processor.execute(command):
                    self.context.tft.update("waiting_view", "Authenticated! :)")
                return
            #if self.context.processor.authenticated:
            if self.context.authenticator.f_authenticated:
                self.context.processor.execute(command)

        if self.context.encoder.was_pressed():
            self.context.transition_to(MenuState(self.context))
        
        if self.context.fingerprint.finger_irq():
            print("👆 Finger is on the sensor")
            self.context.authenticator.authenticate()
            if self.context.fingerprint.authenticated:
                self.context.tft.update("waiting_view", "Authenticated! :)")


    def exit(self):
        pass

class MenuState(BaseState):
    def enter(self):
        self.draw_menu()

    def draw_menu(self):
        self.context.tft.clear()
        self.context.tft.write("Menu:", x=10, y=10, identifier="menu_title")
        self.context.tft.write(self.context.menu_modes[self.context.menu_index], x=10, y=30, identifier="menu_item")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction == "CW":
            self.context.menu_index = (self.context.menu_index + 1) % len(self.context.menu_modes)
            self.context.tft.update("menu_item", self.context.menu_modes[self.context.menu_index])
        elif direction == "CCW":
            self.context.menu_index = (self.context.menu_index - 1) % len(self.context.menu_modes)
            self.context.tft.update("menu_item", self.context.menu_modes[self.context.menu_index])
        
        if self.context.encoder.was_pressed():
            if self.context.menu_modes[self.context.menu_index] == "Manual Mode":
                self.context.transition_to(AuthState(self.context))
            elif self.context.menu_modes[self.context.menu_index] == "Suggest Strong Password":
                self.context.transition_to(PassLengthState(self.context))
            elif self.context.menu_modes[self.context.menu_index] == "Settings":
                self.context.transition_to(SettingsState(self.context))
        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(AutoState(self.context))

    def exit(self):
        pass

class AuthState(BaseState):
    def enter(self):
        self.context.tft.clear()
        self.context.tft.write("Authenticate with key", x=10, y=20, identifier="auth")
        self.context.usb.write("Waiting for authentication...")

    def handle(self):
        if self.context.authenticator.f_authenticated:
                self.context.tft.write("\u2705 Auth OK", x=10, y=50, identifier="status")
                self.context.usb.write("✅ Authentication successful!")
                self.context.transition_to(LoginState(self.context))

        else:
            if self.context.fingerprint.finger_irq():
                print("👆 Finger is on the sensor")
                self.context.authenticator.authenticate()

    def exit(self):
        pass

class LoginState(BaseState):
    def enter(self):
        self.draw_login_screen()

    def draw_login_screen(self):
        self.context.tft.clear()
        self.context.tft.write("Login Page", x=10, y=20, identifier="login")
        if self.context.authenticator.authenticated:
            try:
                vault = self.context.authenticator.get_vault()
                domain = list(vault.db.keys())[self.context.login_index]
                self.context.tft.write(domain, x=10, y=50, identifier="domain")
            except (PermissionError, IndexError):
                self.context.tft.write("🔒 No credentials", x=10, y=50, identifier="domain")

    def handle(self):
        direction = self.context.encoder.get_direction()
        try:
            if not self.context.authenticator.authenticated:
                return

            vault = self.context.authenticator.get_vault()
            vault_keys = list(vault.db.keys())
        except PermissionError:
            return

        if not vault_keys:
            return

        if direction == "CW":
            self.context.login_index = (self.context.login_index + 1) % len(vault_keys)
            self.context.tft.update("domain", vault_keys[self.context.login_index])
        elif direction == "CCW":
            self.context.login_index = (self.context.login_index - 1) % len(vault_keys)
            self.context.tft.update("domain", vault_keys[self.context.login_index])

        if self.context.encoder.was_pressed():
            domain = vault_keys[self.context.login_index]
            creds = vault.get(domain)
            self.context.usb.write(f"\U0001F511 Credentials for {domain}: {creds}")
            if creds:
                time.sleep(1)
                self.context.processor.hid.type_text(creds["username"], delay=0.0)
                self.context.processor.hid.key_strokes("TAB")
                self.context.processor.hid.type_text(creds["password"], delay=0.0)
                self.context.processor.hid.key_strokes("ENTER")

        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(MenuState(self.context))


    def exit(self):
        pass

class PassLengthState(BaseState):
    def enter(self):
        self.draw_pass_length()

    def draw_pass_length(self):
        self.context.tft.clear()
        self.context.tft.write("Length:", x=10, y=10, identifier="pass_title")
        self.context.tft.write(str(self.context.password_length), x=10, y=30, identifier="pass_len")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction == "CW" and self.context.password_length < 30:
            self.context.password_length += 1
            self.context.tft.update("pass_len", str(self.context.password_length))
        elif direction == "CCW" and self.context.password_length > 8:
            self.context.password_length -= 1
            self.context.tft.update("pass_len", str(self.context.password_length))
        if self.context.encoder.was_pressed():
            self.context.transition_to(PassComplexState(self.context))
        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(MenuState(self.context))

    def exit(self):
        pass

class PassComplexState(BaseState):
    COMPLEXITY_LEVELS = ["Numbers + Letters", "Numbers + Small + Special", "All Characters"]

    def enter(self):
        self.draw_complexity()

    def draw_complexity(self):
        self.context.tft.clear()
        self.context.tft.write("Complexity:", x=10, y=10, identifier="complex_title")
        self.context.tft.write(self.COMPLEXITY_LEVELS[self.context.complexity_index],
                                 x=10, y=30, identifier="complex_level")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction == "CW":
            self.context.complexity_index = (self.context.complexity_index + 1) % len(self.COMPLEXITY_LEVELS)
            self.context.tft.update("complex_level", self.COMPLEXITY_LEVELS[self.context.complexity_index])
        elif direction == "CCW":
            self.context.complexity_index = (self.context.complexity_index - 1) % len(self.COMPLEXITY_LEVELS)
            self.context.tft.update("complex_level", self.COMPLEXITY_LEVELS[self.context.complexity_index])
        if self.context.encoder.was_pressed():
            self.context.password_generated = generate_password(self.context.password_length,
                                                                  self.context.complexity_index)
            self.context.hid_output.type_text(self.context.password_generated, delay=0.1)
            self.context.transition_to(PassSaveState(self.context))
        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(PassLengthState(self.context))

    def exit(self):
        pass

class PassSaveState(BaseState):
    def enter(self):
        self.draw_save_prompt()

    def draw_save_prompt(self):
        self.context.tft.clear()
        self.context.tft.write("Save password?", x=10, y=10, identifier="save_title")
        self.context.tft.write(self.context.save_decision[self.context.save_index], x=10, y=30, identifier="save_option")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction in ("CW", "CCW"):
            self.context.save_index = 1 - self.context.save_index
            self.context.tft.update("save_option", self.context.save_decision[self.context.save_index])
        if self.context.encoder.was_pressed():
            if self.context.save_decision[self.context.save_index] == "Yes":
                self.context.transition_to(DomainEntryState(self.context))
            else:
                self.context.transition_to(AutoState(self.context))
        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(PassComplexState(self.context))

    def exit(self):
        pass

class DomainEntryState(BaseState):
    def enter(self):
        self.context.tft.clear()
        self.context.tft.write("Authenticate to Save", x=10, y=20, identifier="auth")
        self.context.usb.write("Waiting for authentication...")
        self.authenticated = False

    def handle(self):
        if not self.context.processor.authenticated:
            command = self.context.usb.read()
            if command:
                self.context.processor.execute(command)
            return

        if self.context.processor.authenticated and not self.authenticated:
            self.context.tft.write("\u2705 Auth OK", x=10, y=50, identifier="status")
            self.context.usb.write("Authenticated. Please send domain and username in the format: <domain> <username>")
            self.authenticated = True
            return

        credentials = self.context.usb.read()
        if credentials:
            try:
                new_domain, user = credentials.split(" ", 1)
                self.context.processor.vault.add(new_domain.strip(), user.strip(), self.context.password_generated)
                self.context.usb.write(f"✅ Password saved for {new_domain.strip()}\n")
                self.context.tft.write(f"Password saved for {new_domain.strip()}", x=10, y=70, identifier="save_status")
                self.context.transition_to(AutoState(self.context))
            except Exception as e:
                self.context.usb.write(f"❌ Failed to save credentials: {e}\n")

    def exit(self):
        pass

class SettingsState(BaseState):
    def enter(self):
        self.context.tft.clear()
        self.context.tft.write("Settings", x=10, y=10, identifier="settings_title")
        self.context.tft.write(self.context.settings_list[self.context.settings_index], x=10, y=30, identifier="settings_item")

        self.mode = "menu"
        self.pin_helper = None

        self.mode_handlers = {
            "menu": self.handle_menu,
            "verify_old": self.handle_verify_old_pin,
            "enter_new": self.handle_enter_new_pin
        }

    def handle(self):
        if self.mode in self.mode_handlers:
            self.mode_handlers[self.mode]()

    def handle_menu(self):
        direction = self.context.encoder.get_direction()

        if direction == "CW":
            self.context.settings_index = (self.context.settings_index + 1) % len(self.context.settings_list)
            self.context.tft.update("settings_item", self.context.settings_list[self.context.settings_index])
        elif direction == "CCW":
            self.context.settings_index = (self.context.settings_index - 1) % len(self.context.settings_list)
            self.context.tft.update("settings_item", self.context.settings_list[self.context.settings_index])

        if self.context.encoder.was_pressed():
            selected = self.context.settings_list[self.context.settings_index]
            if selected == "Change PIN":
                self.pin_helper = PinEntryHelper(self.context.encoder, self.context.tft, prompt="Enter Admin PIN")
                self.mode = "verify_old"
            elif selected == "Update Fingerprints":
                self.update_finger()

    def handle_verify_old_pin(self):
        self.pin_helper.update()
        if self.pin_helper.is_done():
            pin = self.pin_helper.get_pin()
            if self.context.authenticator.verify_pin(pin):
                self.pin_helper = PinEntryHelper(self.context.encoder, self.context.tft, prompt="New PIN")
                self.mode = "enter_new"
            else:
                self.context.tft.update("pin_view", "❌ Wrong PIN")
                time.sleep(1)
                self.context.transition_to(SettingsState(self.context))
    
    def handle_enter_new_pin(self):
        self.pin_helper.update()
        if self.pin_helper.is_done():
            new_pin = self.pin_helper.get_pin()
            self.context.authenticator.set_pin(new_pin)
            self.context.tft.write("✅ PIN updated!", x=10, y=80, identifier="done")
            time.sleep(1)
            self.context.transition_to(SettingsState(self.context))




    # def handle(self):
    #     direction = self.context.encoder.get_direction()
    #     if direction == "CW":
    #         self.context.settings_index = (self.context.settings_index + 1) % 2
    #         self.context.tft.update("settings_item", self.context.settings_list[self.context.settings_index])
    #     elif direction == "CCW":
    #         self.context.settings_index = (self.context.settings_index - 1) % 2
    #         self.context.tft.update("settings_item", self.context.settings_list[self.context.settings_index])

    #     if self.context.encoder.was_pressed():
    #         if self.context.settings_list[self.context.settings_index] == "Change PIN":
    #             self.change_pin()
    #         elif self.context.settings_list[self.context.settings_index] == "Update Fingerprints":
    #             self.update_finger()

    def update_finger(self):
        # Placeholder for enrolling a finger
        pass

    # def change_pin(self):
    #     # Placeholder for changing the PIN
    #       # Example PIN check
    #     self.pin_helper = PinEntryHelper(self.context.encoder, self.context.tft, prompt="Enter Admin PIN")
    #     self.pin_helper.update()

    #     if self.pin_helper.is_done():
    #         pin = self.pin_helper.get_pin()
    #         if self.context.authenticator.verify_pin(pin):
    #             self.context.tft.write("Enter new PIN:", x=10, y=50, identifier="new_pin")
    #             new_pin = self._prompt_pin()
    #             self.context.authenticator.set_pin(new_pin)
    #             self.context.tft.write("PIN updated!", x=10, y=70, identifier="pin_update")

    def exit(self):
        pass