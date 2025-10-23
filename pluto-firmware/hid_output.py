import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS

class HIDOutput:
    def __init__(self):
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)

    def type_text(self, text, delay=0.1):
        """Types the given text via USB HID with an optional delay between characters."""
        self.layout.write(text, delay)
    
    def press_enter(self):
        self.keyboard.send(Keycode.ENTER)

    def press_tab(self):
        self.keyboard.send(Keycode.TAB)

    def key_strokes(self,key_name):
        """Send a keystroke for the given key name string via USB HID."""
        key = key_name.upper()  # normalize to uppercase
        if not hasattr(Keycode, key):
            # Key name not found in Keycode class
            print(f"Invalid key name: {key_name}")
            return False  # indicate failure (could also raise an exception)
        keycode_val = getattr(Keycode, key)      # get the Keycode attribute
        self.keyboard.send(keycode_val)              # send the key press
        return True
