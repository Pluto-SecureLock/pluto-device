import board
import rotaryio
import digitalio
import time

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
