import usb_hid
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS


class HIDOutput:
    def __init__(self):
        self.keyboard = Keyboard(usb_hid.devices)
        self.layout = KeyboardLayoutUS(self.keyboard)

    def type_text(self, text, delay=0.1):
        self.layout.write(text, delay)

    def press_enter(self):
        self.keyboard.send(Keycode.ENTER)

    def press_tab(self):
        self.keyboard.send(Keycode.TAB)

    def key_strokes(self, key_name):
        key = key_name.upper()
        if not hasattr(Keycode, key):
            print("Invalid key name: {}".format(key_name))
            return False
        self.keyboard.send(getattr(Keycode, key))
        return True
