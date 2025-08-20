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
        self.context.screen.clear()
        self.context.screen.write("Initial Setup...", line=1, identifier="setup")

        # PIN setup
        self.context.screen.write("🔑 Set 4-digit PIN",line=2)
        self.pin_helper = PinEntryHelper(self.context.encoder, self.context.screen, prompt="Enter NEW Admin PIN")

    def handle(self):
        # Update any input from the encoder
        self.pin_helper.update()

        if self.pin_helper.is_done():
            new_pin = self.pin_helper.get_pin()
            # Set the PIN in the authenticator
            self.context.initialize_fingerprint(0000)
            self.context.authenticator.set_pin(new_pin)
            self.context.screen.write("✅ PIN updated!", line=2, identifier="done")
            self.context.authenticator.set_master_key()
            time.sleep(0.5)
            self.context.transition_to(AutoState(self.context))

    def exit(self):
        self.context.screen.clear()

class UnblockState(BaseState):
    def enter(self):
        if not self.context.authenticator.is_registered():
            print("SET UP A NEW PIN")
            self.context.transition_to(SetupState(self.context))
        else:
            self.pin_helper = PinEntryHelper(self.context.encoder, self.context.screen, prompt="Enter Admin PIN")
        
    def handle(self):
        self.pin_helper.update()

        if self.pin_helper.is_done():
            pin = self.pin_helper.get_pin()

            if self.context.authenticator.verify_pin(pin):
                # Initialize the fingerprint authenticator
                self.context.initialize_fingerprint(pin)
                # Verify master key
                self.context.authenticator.set_master_key()
                # Transition to the main Auto state
                self.context.transition_to(AutoState(self.context))
            else:
                self.context.screen.update("pin_view", "❌ Wrong PIN")
                time.sleep(1)
                self.context.transition_to(UnblockState(self.context))

    def exit(self):
        self.context.screen.clear()

class PinEntryHelper:
    def __init__(self, encoder, screen, prompt="Enter PIN"):
        self.encoder = encoder
        self.screen = screen
        self.prompt = prompt
        self.digits = [0, 0, 0, 0]
        self.index = 0
        self._done = False
        self.last_rendered = ""

        self.screen.clear()
        self.screen.write(self.prompt, line=1, identifier="pin_prompt")
        self.screen.write("PIN: 0000", line=2, identifier="pin_view")

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
            self.screen.update("pin_view", f"PIN: {pin_str}")
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
        self.context.screen.clear()
        self.context.screen.write("Send Command...", line=1, identifier="auto_view")
        #self.context.usb.write("Ready to receive commands over USB Serial...\n")

    def handle(self):
        command = self.context.usb.read(echo=False)

        if command:
            self.context.screen.update("auto_view", f"Recieved {command}")
            self.context.authenticator.set_master_key()  # Ensure master key is set before executing commands
            self.execute_with_retry(command)
            self.context.transition_to(AutoState(self.context))
            
        if self.context.encoder.was_pressed():
            self.context.transition_to(MenuState(self.context))

    def exit(self):
        pass

    def execute_with_retry(self, command):
        """
        Securely attempts fingerprint authentication up to 3 times.
        If successful at any attempt, the command is executed.
        If it fails 3 times, the command is dropped securely.
        """
        MAX_ATTEMPTS = 3
        attempts = 0
        self.context.screen.clear()
        # Write the initial state
        self.context.screen.write("Waiting for Authentication...", line=1, identifier="waiting_view")
        self.context.screen.write(f"Attempt {attempts + 1} of {MAX_ATTEMPTS}", line=2, identifier="attempts")

        # Save the state of the screen before trying authentication
        state = self.context.screen.save_state()
        #print("State saved:", state)
        while attempts < MAX_ATTEMPTS:
            # Display the current attempt
            self.context.screen.update("attempts", f"Attempt {attempts + 1} of {MAX_ATTEMPTS}")

            if self.context.authenticator.authenticate():
                # Restore the screen to the initial state
                self.context.screen.restore_state(state)
                # Update directly without checking
                self.context.screen.update("waiting_view", "Authenticated! :)")
                self.context.processor.execute(command)
                return  # Exit after successful authentication
            else:
                # Restore the original state if it fails
                self.context.screen.restore_state(state)
                attempts += 1
                # Direct update without checking
                self.context.screen.update("attempts", f"Failed attempt {attempts}")

        # If we reach here, all attempts failed
        self.context.screen.update("waiting_view", "Access Denied")
        self.context.screen.update("attempts", "Maximum attempts reached.")
        print("❌ Command dropped due to failed authentication.")


class MenuState(BaseState):
    def enter(self):
        self.draw_menu()

    def draw_menu(self):
        self.context.screen.clear()
        self.context.screen.write("Menu:", line=1, identifier="menu_title")
        self.context.screen.write(self.context.menu_modes[self.context.menu_index], line=2, identifier="menu_item")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction == "CW":
            self.context.menu_index = (self.context.menu_index + 1) % len(self.context.menu_modes)
            self.context.screen.update("menu_item", self.context.menu_modes[self.context.menu_index])
        elif direction == "CCW":
            self.context.menu_index = (self.context.menu_index - 1) % len(self.context.menu_modes)
            self.context.screen.update("menu_item", self.context.menu_modes[self.context.menu_index])
        
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
        self.context.screen.clear()
        self.context.screen.write("Authenticate with key", line=1, identifier="auth")
        self.context.usb.write("Waiting for authentication...")

    def handle(self):
        if self.context.authenticator.authenticate():
            self.context.screen.write("\u2705 Auth OK", line=2, identifier="status")
            self.context.usb.write("✅ Authentication successful!")
            self.context.transition_to(LoginState(self.context))

    def exit(self):
        pass

class LoginState(BaseState):
    def enter(self):
        self.draw_login_screen()

    def draw_login_screen(self):
        self.context.screen.clear()
        self.context.screen.write("Login Page",line=1, identifier="login")
        if self.context.authenticator.authenticated:
            try:
                vault = self.context.authenticator.get_vault()
                domain = list(vault.db.keys())[self.context.login_index]
                self.context.screen.write(domain, line=2, identifier="domain")
            except Exception as e:
                self.context.screen.write("🔒 No credentials", line=2, identifier="domain")

    def handle(self):
        direction = self.context.encoder.get_direction()
        try:
            if not self.context.authenticator.authenticated:
                return

            vault = self.context.authenticator.get_vault()
            vault_keys = list(vault.db.keys())
        except Exception as e:
            return

        if not vault_keys:
            return

        if direction == "CW":
            self.context.login_index = (self.context.login_index + 1) % len(vault_keys)
            self.context.screen.update("domain", vault_keys[self.context.login_index])
        elif direction == "CCW":
            self.context.login_index = (self.context.login_index - 1) % len(vault_keys)
            self.context.screen.update("domain", vault_keys[self.context.login_index])

        if self.context.encoder.was_pressed():
            domain = vault_keys[self.context.login_index]
            creds = vault.get(domain)
            self.context.usb.write(f"\U0001F511 Credentials for {domain}: {creds}")
            if creds:
                if (len(creds["username"]) > 0):
                    time.sleep(0.2)
                    self.context.processor.hid.type_text(creds["username"], delay=0.0)
                    self.context.processor.hid.key_strokes("TAB")
                time.sleep(0.1)
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
        self.context.screen.clear()
        self.context.screen.write("Length:", line=1, identifier="pass_title")
        self.context.screen.write(str(self.context.password_length), line=2, identifier="pass_len")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction == "CW" and self.context.password_length < 30:
            self.context.password_length += 1
            self.context.screen.update("pass_len", str(self.context.password_length))
        elif direction == "CCW" and self.context.password_length > 8:
            self.context.password_length -= 1
            self.context.screen.update("pass_len", str(self.context.password_length))
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
        self.context.screen.clear()
        self.context.screen.write("Complexity:", line=1, identifier="complex_title")
        self.context.screen.write(self.COMPLEXITY_LEVELS[self.context.complexity_index],
                                 line=2, identifier="complex_level")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction == "CW":
            self.context.complexity_index = (self.context.complexity_index + 1) % len(self.COMPLEXITY_LEVELS)
            self.context.screen.update("complex_level", self.COMPLEXITY_LEVELS[self.context.complexity_index])
        elif direction == "CCW":
            self.context.complexity_index = (self.context.complexity_index - 1) % len(self.COMPLEXITY_LEVELS)
            self.context.screen.update("complex_level", self.COMPLEXITY_LEVELS[self.context.complexity_index])
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
        self.context.screen.clear()
        self.context.screen.write("Save password?",line=1, identifier="save_title")
        self.context.screen.write(self.context.save_decision[self.context.save_index], line=2, identifier="save_option")

    def handle(self):
        direction = self.context.encoder.get_direction()
        if direction in ("CW", "CCW"):
            self.context.save_index = 1 - self.context.save_index
            self.context.screen.update("save_option", self.context.save_decision[self.context.save_index])
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
        self.context.screen.clear()
        self.context.screen.write("Authenticate to Save", line=1, identifier="auth")
        self.context.usb.write("Waiting for authentication...")
        self.authenticated = False

    def handle(self):
        if not self.context.processor.authenticated:
            command = self.context.usb.read()
            if command:
                self.context.processor.execute(command)
            return

        if self.context.processor.authenticated and not self.authenticated:
            self.context.screen.write("\u2705 Auth OK", line=2, identifier="status")
            self.context.usb.write("Authenticated. Please send domain and username in the format: <domain> <username>")
            self.authenticated = True
            return

        credentials = self.context.usb.read()
        if credentials:
            try:
                new_domain, user = credentials.split(" ", 1)
                self.context.processor.vault.add(new_domain.strip(), user.strip(), self.context.password_generated)
                self.context.usb.write(f"✅ Password saved for {new_domain.strip()}\n")
                self.context.screen.write(f"Password saved for {new_domain.strip()}", line=2, identifier="save_status")
                self.context.transition_to(AutoState(self.context))
            except Exception as e:
                self.context.usb.write(f"❌ Failed to save credentials: {e}\n")

    def exit(self):
        pass

class SettingsState(BaseState):
    def enter(self):
        self.context.screen.clear()
        self.context.screen.write("Settings", line=1, identifier="settings_title")
        self.context.screen.write(self.context.settings_list[self.context.settings_index], line=2, identifier="settings_item")

        self.mode = "menu"
        self.pin_helper = None

        self.mode_handlers = {
            "menu": self.handle_menu,
            "verify_old": self.handle_verify_old_pin,
            "enter_new": self.handle_enter_new_pin,
            "update_finger": self.handle_update_finger
        }

    def handle(self):
        if self.mode in self.mode_handlers:
            self.mode_handlers[self.mode]()

    def handle_menu(self):
        """
        Handle navigation in the main settings menu.
        """
        direction = self.context.encoder.get_direction()

        if direction == "CW":
            self.context.settings_index = (self.context.settings_index + 1) % len(self.context.settings_list)
            self.context.screen.update("settings_item", self.context.settings_list[self.context.settings_index])
        elif direction == "CCW":
            self.context.settings_index = (self.context.settings_index - 1) % len(self.context.settings_list)
            self.context.screen.update("settings_item", self.context.settings_list[self.context.settings_index])

        if self.context.encoder.was_pressed():
            selected = self.context.settings_list[self.context.settings_index]
            if selected == "Change PIN":
                self.pin_helper = PinEntryHelper(self.context.encoder, self.context.screen, prompt="Enter Admin PIN")
                self.mode = "verify_old"
            elif selected == "Update Fingerprints":
                self.context.screen.clear()
                self.context.screen.write("Select Fingerprint:", line=1, identifier="finger_id")
                self.finger_options = ["Fingerprint 1", "Fingerprint 2"]
                self.current_finger = 0
                self.context.screen.update("finger_id", self.finger_options[self.current_finger])
                self.mode = "update_finger"
            elif selected == "Factory Reset":
                self.context.screen.clear()
                self.context.screen.write("Factory Resetting...", line=2, identifier="reset")
                time.sleep(1)
                if self.context.authenticator.factory_reset():
                    self.context.screen.write("✅ Factory reset complete!", line=2, identifier="reset_done")
                    time.sleep(1)
                    self.context.transition_to(SetupState(self.context))
                else:
                    self.context.transition_to(SettingsState(self.context))

        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(MenuState(self.context))

    def handle_verify_old_pin(self):
        """
        Handle PIN verification for PIN change.
        """
        self.pin_helper.update()
        if self.pin_helper.is_done():
            pin = self.pin_helper.get_pin()
            if self.context.authenticator.verify_pin(pin):
                self.pin_helper = PinEntryHelper(self.context.encoder, self.context.screen, prompt="New PIN")
                self.mode = "enter_new"
            else:
                self.context.screen.update("pin_view", "❌ Wrong PIN")
                time.sleep(1)
                self.context.transition_to(SettingsState(self.context))
    
    def handle_enter_new_pin(self):
        """
        Handle entering the new PIN after verification.
        """
        self.pin_helper.update()
        if self.pin_helper.is_done():
            new_pin = self.pin_helper.get_pin()
            self.context.authenticator.set_pin(new_pin)
            self.context.screen.clear()
            self.context.screen.write("✅ PIN updated!", line=2, identifier="done")
            time.sleep(1)
            self.context.transition_to(SettingsState(self.context))

    def handle_update_finger(self):
        """
        Handle the selection and updating of fingerprints.
        """
        direction = self.context.encoder.get_direction()

        # Move between Fingerprint 1 and Fingerprint 2
        if direction == "CW":
            self.current_finger = (self.current_finger + 1) % len(self.finger_options)
        elif direction == "CCW":
            self.current_finger = (self.current_finger - 1) % len(self.finger_options)

        # Update screen
        self.context.screen.update("finger_id", self.finger_options[self.current_finger])

        if self.context.encoder.was_pressed():
            finger_id = self.current_finger + 1  # Convert to 1-based index
            self.context.screen.clear()
            self.context.screen.write(f"Updating FP {finger_id}...", line=2, identifier="enroll_finger")
            
            if self.context.authenticator.update_fingerprint(finger_id):
                self.context.screen.write(f"FP {finger_id} updated!", line=2, identifier="enroll_finger")
            else:
                self.context.screen.write(f"FP {finger_id} NOT updated!", line=2, identifier="enroll_finger")
            time.sleep(1)
            self.context.transition_to(SettingsState(self.context))

        elif self.context.encoder.rtr_was_pressed():
            self.context.transition_to(SettingsState(self.context))

    def exit(self):
        pass