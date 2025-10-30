import time
import board
import rotaryio
import digitalio

class RotaryEncoderWithButton:
    def __init__(self, pin_clk=board.D5, pin_dt=board.D6, pin_sw=board.D9,pin_rtr=board.D7):
        # Rotary encoder setup
        self.encoder = rotaryio.IncrementalEncoder(pin_clk, pin_dt)
        self.last_position = self.encoder.position

        # Button setup
        self.button = digitalio.DigitalInOut(pin_sw)
        self.button.direction = digitalio.Direction.INPUT
        self.button.pull = digitalio.Pull.UP
        self.last_button = self.button.value

        # Extra button (RTR)
        self.rtr_button = digitalio.DigitalInOut(pin_rtr)
        self.rtr_button.direction = digitalio.Direction.INPUT
        self.rtr_button.pull = digitalio.Pull.UP
        self.last_rtr = self.rtr_button.value
        self.rtr_pressed = False

        # State flags
        self.direction = None
        self.button_pressed = False

    def update(self):
        # Handle rotation
        current_position = self.encoder.position
        self.direction = None
        if current_position != self.last_position:
            self.direction = "CW" if current_position > self.last_position else "CCW"
            self.last_position = current_position

        # Encoder button check
        current_button = self.button.value
        self.button_pressed = (self.last_button and not current_button)
        self.last_button = current_button

        # Extra button check
        current_rtr = self.rtr_button.value
        self.rtr_pressed = (self.last_rtr and not current_rtr)
        self.last_rtr = current_rtr

    def get_direction(self):
        return self.direction

    def was_pressed(self):
        return self.button_pressed
    
    def rtr_was_pressed(self):
        return self.rtr_pressed

    def get_position(self):
        return self.encoder.position
    
    def get_delta(self):
        direction = self.get_direction()
        if direction == "CW":
            return 1
        elif direction == "CCW":
            return -1
        else:
            return 0

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

        elif self.encoder.rtr_was_pressed():
            if self.index > 0:
                self.index -= 1
                time.sleep(0.2)  # debounce

    def is_done(self):
        return self._done

    def get_pin(self) -> str:
        return ''.join(str(d) for d in self.digits)