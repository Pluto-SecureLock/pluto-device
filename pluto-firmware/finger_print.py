import time
import board
import busio
import adafruit_fingerprint
import json
import digitalio
from usb_serial import USBSerial

MAX_SLOTS = 127                # sensor’s addressable slots (1-127)
MAX_FINGERS = 2              # max number of fingerprints to store
class FingerprintAuthenticator:
    def __init__(self, max_fingers=MAX_FINGERS, pin=0000):
        self.screen = None
        self.usb = USBSerial()
        self.uart = busio.UART(board.TX, board.RX, baudrate=57600, timeout=1)
        password_tuple = tuple(pin.to_bytes(4, 'big'))
        self.finger = adafruit_fingerprint.Adafruit_Fingerprint(self.uart, passwd=password_tuple)
        self.max_fingers = max_fingers
        self.irq_pin = self._enable_irq()
        self._authenticated = False  # private variable
        self._last_irq_state = self.irq_pin.value  # track for edge detection
        self._verify_sensor()
        self.finger.set_led(color=3, mode=1, speed=20, cycles=2)

    def attach_screen(self, screen):
        self.screen = screen

    def _verify_sensor(self,DEBUG=True):
        if DEBUG: print("🔋 Verifying sensor...")
        if self.finger.verify_password() != adafruit_fingerprint.OK:
            raise RuntimeError("❌ Failed to find sensor; check wiring/power!")
        if DEBUG: print("✅ Sensor verified")
        if not self._ensure_two_fingerprints(DEBUG=DEBUG):
            raise RuntimeError("❌ Failed to ensure exactly two fingerprints.")
        time.sleep(1)

    def _ensure_two_fingerprints(self, DEBUG=True) -> bool:
        """
        Make sure *exactly* two fingerprints are stored.
        ─ If 0 or 1 are present → enroll into the first free slots.
        ─ If 3-127 are present  → abort (or wipe, if you really want empty_library()).
        Returns True on success, False on any failure.
        """
        # 1) Count how many templates exist right now
        status = self.finger.count_templates()
        if status != adafruit_fingerprint.OK:
            if DEBUG: print("❌ count_templates() failed")
            return False

        current = self.finger.template_count
        if DEBUG: print(f"🧾 Templates present: {current}")

        # 2) Bail (or wipe) if there are already too many
        if current > MAX_FINGERS:
            if DEBUG: print("❌ More than 2 prints stored – aborting")
            # self.finger.empty_library()   # uncomment if you *want* to wipe
            return False

        # 3) If we need to add 1 or 2 prints, find unused slots
        if current < MAX_FINGERS:
            # read_templates() gives us a list of occupied slot numbers
            if self.finger.read_templates() != adafruit_fingerprint.OK:
                if DEBUG: print("❌ read_templates() failed")
                return False
            occupied = set(self.finger.templates)

            needed = MAX_FINGERS - current
            for slot in range(1, MAX_SLOTS + 1):
                if slot in occupied:
                    continue                      # slot already used
                if DEBUG: print(f"👉 Enrolling into free slot {slot} …")
                if not self.enroll(slot):
                    if DEBUG: print(f"❌ Enrollment failed in slot {slot}")
                    return False
                needed -= 1
                time.sleep(0.5)                  # small debounce
                if needed == 0:
                    break

            if needed:                           # ran out of free slots
                if DEBUG: print("❌ Library is full – can’t reach exactly 2")
                return False

        if DEBUG: print("✅ Exactly 2 fingerprints stored")
        return True

    def _usb_input(self, prompt: str) -> str:
        print(prompt, end="")
        line = ""
        while not line:
            line = self.usb.read(echo=False) or ""
            time.sleep(0.05)
        return line

    def _get_valid_id(self) -> int:
        while True:
            s = self._usb_input("Enter ID (1–2): ")
            try:
                n = int(s)
                if 1 <= n <= self.max_fingers:
                    return n
            except ValueError:
                pass

    def _enable_irq(self):
        self.irq_pin = digitalio.DigitalInOut(board.D2)
        self.irq_pin.direction = digitalio.Direction.INPUT
        self.irq_pin.pull = digitalio.Pull.UP  # most fingerprint sensors pull LOW when active
        return self.irq_pin
    
    @property
    def authenticated(self):
        return self._authenticated
    
    def finger_irq(self):
        # return not self.irq_pin.value  # LOW = finger present
        current_state = self.irq_pin.value
        triggered = self._last_irq_state and not current_state  # HIGH -> LOW transition
        self._last_irq_state = current_state
        if triggered:
        #     # Optionally wait until released
        #     while not self.irq_pin.value:
        #         time.sleep(0.01)
            return triggered
    
    def check_system_parameters(self) -> bool:
        self.finger.read_sysparam()
        print("📟 Current sensor params:")
        current_params = {
            "status_register": self.finger.status_register,
            "system_id": self.finger.system_id,
            "library_size": self.finger.library_size,
            "security_level": self.finger.security_level,
            "device_address": list(self.finger.device_address),
            "data_packet_size": self.finger.data_packet_size,
            "baudrate": self.finger.baudrate
            }
        print(json.dumps(current_params))
        return json.dumps(current_params)
    
    def set_pin(self, pin: int) -> str:
        pin_set = self.finger.set_password(pin)
        if pin_set == adafruit_fingerprint.OK:
            print("OK")
            return True
        else:
            print("ERROR")
            return False
        
    def has_fingerprints(self) -> bool:
        if self.finger.count_templates() > 0:
            print("✅ Fingerprints found")
            return True
        else:
            print("❌ No fingerprints found")
            return False
        
    def enroll(self, location: int) -> bool:
        for pass_num in (1, 2):
            prompt = "Place finger..." if pass_num == 1 else "Place same finger again..."
            print(prompt, end="")
            while True:
                r = self.finger.get_image()
                if r == adafruit_fingerprint.OK:
                    print(" 📸")
                    break
                elif r == adafruit_fingerprint.NOFINGER:
                    time.sleep(0.5)
                else:
                    print(f" ⚠️ Error code {r}")
                    return False

            print("⏳ Templating...", end="")
            if self.finger.image_2_tz(pass_num) != adafruit_fingerprint.OK:
                print(" ❌")
                return False
            print(" ✅")

            if pass_num == 1:
                print("✋ Remove finger…")
                while self.finger.get_image() != adafruit_fingerprint.NOFINGER:
                    time.sleep(0.5)

        print("🔧 Creating model...", end="")
        if self.finger.create_model() != adafruit_fingerprint.OK:
            print(" ❌")
            return False
        print(" ✅")

        print(f"💾 Storing at slot {location}...", end="")
        if self.finger.store_model(location) != adafruit_fingerprint.OK:
            print(" ❌")
            return False
        print(" ✅")
        return True

    def _reset_authentication(self):
        self._authenticated = False

    def authenticate(self):
        
        self._reset_authentication()  # Reset authentication status

        self._verify_sensor(True)

        print("🤚 Place finger...", end="")
        self.screen.clear()
        self.screen.write("Place finger...", line=1, identifier="line1")
        while self.finger.get_image() != adafruit_fingerprint.OK:
            time.sleep(0.05)
        print(" 📸")

        if self.finger.image_2_tz(1) != adafruit_fingerprint.OK:
            print(" ⚠️ Conversion failed")
            self.screen.update(identifier="line1", new_text="Conversion failed...")
            return None

        print(" 🔍 Searching...", end="")
        if self.finger.finger_search() != adafruit_fingerprint.OK:
            print(" ❌ No match")
            self.screen.update(identifier="line1", new_text="NOT a match")
            self.finger.set_led(color=1, mode=2, speed=60, cycles=2)  # Flash red if fingerprint IS NOT a match
            return None

        print(f"✅ Match: ID {self.finger.finger_id} (score {self.finger.confidence})")
        
        self.screen.update(identifier="line1", new_text=f"Match: ID {self.finger.finger_id} (score {self.finger.confidence})")
        
        self._authenticated = True  # ✅ only change from here
        time.sleep(1)
        self.finger.set_led(color=2, mode=6, speed=30, cycles=2)  # Flash purple if fingerprint IS a match
        self.screen.update(identifier="line1", new_text="")  # Clear screen before returning
        return self.finger.finger_id

    def delete(self, location: int):
        if self.finger.delete_model(location) == adafruit_fingerprint.OK:
            print(f"🗑️  Deleted slot {location}")
            return True
        else:
            print("❌ Delete failed")
            return False

    def update(self, location: int):
        print(f"🔄 Updating slot {location}...")
        if self.delete(location):
            return self.enroll(location)
        return False

    def get_template(self):
        return self.finger.get_template(slot=1)

    # def menu_loop(self):
    #     def print_menu():
    #         print("\n=== MENU ===")
    #         print("(e) Enroll    (f) Authenticate    (u) Update    (d) Delete    (q) Quit")

    #     print_menu()
    #     while True:
    #         choice = self._usb_input("> ").lower()

    #         if choice == "e":
    #             slot = self._get_valid_id()
    #             if self.enroll(slot):
    #                 print(f"✅ Enrolled slot {slot}")
    #             else:
    #                 print("❌ Enrollment failed")

    #         elif choice == "f":
    #             result = self.authenticate()
    #             if result is None:
    #                 print("❌ No match found")

    #         elif choice == "u":
    #             slot = self._get_valid_id()
    #             if self.update(slot):
    #                 print(f"🔁 Updated slot {slot}")
    #             else:
    #                 print("❌ Update failed")

    #         elif choice == "d":
    #             slot = self._get_valid_id()
    #             self.delete(slot)

    #         elif choice == "q":
    #             print("👋 Goodbye!")
    #             break

    #         else:
    #             print("❓ Invalid choice")

    #         print_menu()
    #         time.sleep(0.2)