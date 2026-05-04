import time
from  utils import pin_to_tuple

MAX_SLOTS = 127                # sensor’s addressable slots (1-127)
MAX_FINGERS = 2              # max number of fingerprints to store
DEBUG = True

class FingerprintAuthenticator:
    def __init__(self, max_fingers=MAX_FINGERS, passwd: str = "0000", screen=None):
        import board
        import busio
        import adafruit_fingerprint

        self._adafruit = adafruit_fingerprint
        self.screen = screen # Attach the screen if provided
        self.uart = busio.UART(board.TX, board.RX, baudrate=57600, timeout=1)
        self.passwd_tuple = pin_to_tuple(passwd) # "0304"->(0,3,0,4)
        self.finger = self._adafruit.Adafruit_Fingerprint(self.uart, passwd=self.passwd_tuple)
        if self.finger is None:
            self.uart.deinit()
            raise ValueError("Failed to initialize fingerprint sensor.")
        self.max_fingers = max_fingers
        self._authenticated = False  # private variable
        self._verify_sensor()
        self.finger.set_led(color=3, mode=1, speed=20, cycles=2)

    def _start_waiting_led(self):
        try:
            # Blink while waiting for finger placement.
            self.finger.set_led(color=2, mode=1, speed=40, cycles=0) 
        except Exception:
            pass

    def _stop_waiting_led(self):
        try:
            self.finger.set_led(color=3, mode=1, speed=20, cycles=1)
        except Exception:
            pass

    def _verify_sensor(self, DEBUG=True):
        if DEBUG: print("🔋 Verifying sensor...")
        if self.finger.verify_password() != self._adafruit.OK:
            raise RuntimeError("❌ Failed to find sensor; Incorrect password")
        if DEBUG: print("✅ Sensor verified")
        if not self._ensure_two_fingerprints():
            raise RuntimeError("❌ Failed to ensure exactly two fingerprints.")
        time.sleep(1)

    def _ensure_two_fingerprints(self) -> bool:
        """
        Make sure *exactly* two fingerprints are stored.
        Returns True on success, False on any failure.
        """
        try:
            # 1) Count how many templates exist right now
            current_templates = self.count_templates()

            if DEBUG: print(f"🧾 Templates present: {current_templates}")

            # 2) Bail (or wipe) if there are already too many
            if current_templates > MAX_FINGERS:
                if DEBUG: print("❌ More than 2 prints stored - aborting")
                return False

            # 3) If no fingerprints needed, we're done
            fingers_needed = MAX_FINGERS - current_templates  # p.ej. 2 - 1 = 1

            if fingers_needed <= 0:
                return True  # nothing to do

            # 4) If we need to add 1 or 2 prints, find unused slots
            if current_templates < MAX_FINGERS:

                # read_templates() gives us a list of occupied slot numbers
                occupied = set(self.read_templates())

                enrolled_so_far = 0

                for slot in range(1, MAX_SLOTS + 1):
                    if slot in occupied:
                        continue                  # slot already used
                    if DEBUG: print(f"👉 Enrolling into free slot {slot} …")
                    if not self.enroll(slot):
                        if DEBUG: print(f"❌ Enrollment failed in slot {slot}")
                        return False

                    enrolled_so_far += 1
                    if enrolled_so_far >= fingers_needed:
                        if DEBUG: print("✅ Reached required number of fingers")
                        return True
                    time.sleep(1)                 # time between enrollments

            # if we reach here, Library is full
            if DEBUG: print("❌ Library is full, can't enroll more")
            return False

        except Exception as e:
            if DEBUG: print(f"❌ Exception during fingerprint setup: {e}")
            return False

    @property
    def authenticated(self):
        return self._authenticated
    
    def check_system_parameters(self) -> bool:
        import json

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
    
    def set_pin(self, passwd: str) -> str:
        self.passwd_tuple = pin_to_tuple(passwd)
        pin_set = self.finger.set_password(self.passwd_tuple) # PIN [min 0, max 9999]
        if pin_set == self._adafruit.OK:
            print(f"New PIN {passwd} set successfully.")
            return True
        else:
            print("ERROR setting new PIN.")
            return False
        
    def count_templates(self) -> bool:
        status = self.finger.count_templates()
        if status != self._adafruit.OK:
            if DEBUG: print("❌ count_templates() failed")
            raise RuntimeError("Failed to get template count")
        return self.finger.template_count

    def read_templates(self) -> bool:
        status = self.finger.read_templates()
        if status != self._adafruit.OK:
            if DEBUG: print("❌ read_templates() failed")
            raise RuntimeError("Failed to read templates")
        return self.finger.templates

    def initialize(self):
        self._ensure_two_fingerprints()

    def enroll(self, location: int) -> bool:
        self.screen.clear()
        self.screen.write(f"Creating #{location}", line=1, identifier="line1")
        self.screen.write(" ", line=2, identifier="line2")
        for pass_num in (1, 2):
            prompt = "Place finger..." if pass_num == 1 else "Place same finger..."
            print(prompt, end="")
            self.screen.update(identifier="line2", new_text=prompt)
            self._start_waiting_led()
            
            while True:
                r = self.finger.get_image()
                if r == self._adafruit.OK:
                    self._stop_waiting_led()
                    print(" 📸")
                    break
                elif r == self._adafruit.NOFINGER:
                    time.sleep(0.5)
                else:
                    self._stop_waiting_led()
                    error= f" ⚠️ Error code {r}"
                    print(error)
                    self.screen.update(identifier="line2", new_text=error)
                    return False

            print("⏳ Templating...", end="")
            self.screen.update(identifier="line2", new_text="Templating...")

            if self.finger.image_2_tz(pass_num) != self._adafruit.OK:
                print(" ❌")
                self.screen.update(identifier="line2", new_text="Conversion failed")
                return False
            print(" ✅")

            if pass_num == 1:
                print("✋ Remove finger…")
                self.screen.update(identifier="line2", new_text="Remove finger...")
                while self.finger.get_image() != self._adafruit.NOFINGER:
                    time.sleep(1)

        print("🔧 Creating model...", end="")
        self.screen.update(identifier="line2", new_text="Creating model...")
        # Create the fingerprint model from the two templates
        if self.finger.create_model() != self._adafruit.OK:
            print(" ❌")
            self.screen.update(identifier="line2", new_text="Model creation failed")
            return False

        print(f"💾 Storing at slot {location}...", end="")

        if self.finger.store_model(location) != self._adafruit.OK:
            print(" ❌")
            self.screen.update(identifier="line2", new_text="Store failed")
            return False
        print(" ✅")

        self.screen.update(identifier="line1", new_text=f"Successfully created!")
        self.screen.update(identifier="line2", new_text=f"")
        return True

    def _reset_authentication(self):
        self._authenticated = False

    def authenticate(self):
        
        self._reset_authentication()  # Reset authentication status

        self._verify_sensor(True)
        print("🤚 Place finger...", end="")
        self.screen.clear()
        self.screen.write("Place finger...", line=1, identifier="line1")
        self._start_waiting_led()
        while self.finger.get_image() != self._adafruit.OK:
            time.sleep(0.05)
        self._stop_waiting_led()
        print(" 📸")

        if self.finger.image_2_tz(1) != self._adafruit.OK:
            print(" ⚠️ Conversion failed")
            self.screen.update(identifier="line1", new_text="Conversion failed...")
            return None

        print(" 🔍 Searching...", end="")
        if self.finger.finger_search() != self._adafruit.OK:
            print(" ❌ No match")
            self.screen.update(identifier="line1", new_text="NOT a match")
            self.finger.set_led(color=1, mode=2, speed=60, cycles=2)  # Flash red if fingerprint IS NOT a match
            return None

        if DEBUG: print(f"✅ Fingerprint Matched. Access Granted. ID #{self.finger.finger_id} with confidence {self.finger.confidence}")

        self.screen.update(identifier="line1", new_text=f"Fingerprint Matched.")
        self.screen.write("Access Granted.", line=2, identifier="line2")

        self._authenticated = True  # ✅ only change from here
        time.sleep(1)
        self.finger.set_led(color=2, mode=6, speed=30, cycles=2)  # Flash purple if fingerprint IS a match
        self.screen.clear()
        return self.finger.finger_id

    def delete(self, location: int):
        if self.finger.delete_model(location) == self._adafruit.OK:
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
        return self.finger.get_template(slot=1)[:128]
    
    def delete_all(self):
        self.finger.empty_library()

    def hard_reset(self):
        self.delete_all()
        self.set_pin(0)  # Reset to default PIN