class HIDOutputLite:
    """No-op HID backend for API-only firmware builds."""

    def type_text(self, text, delay=0.0):
        return False

    def press_enter(self):
        return False

    def press_tab(self):
        return False

    def key_strokes(self, key_name):
        return False
