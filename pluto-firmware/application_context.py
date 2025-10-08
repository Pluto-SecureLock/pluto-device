from screen import Screen
from encoder import RotaryEncoderWithButton
from usb_serial import USBSerial
from hid_output import HIDOutput
from command_processor import CommandProcessor
from finger_print import FingerprintAuthenticator
from auth_manager import AuthManager
from states import UnblockState

class ApplicationContext:
    def __init__(self):
        self.usb = USBSerial()
        self.hid_output = HIDOutput()
        self.fingerprint = None  # Delayed initialization
        self.authenticator = AuthManager()  # Accepts no fingerprint initially
        self.processor = CommandProcessor(self.hid_output,self.usb,self.authenticator)
        self.encoder = RotaryEncoderWithButton()
        self.screen = Screen()

        # Application data / shared state
        self.password_length = 12
        self.complexity_index = 0
        self.settings_index = 0
        self.settings_list = ["Change PIN", "Update Fingerprints", "Factory Reset"]
        self.password_generated = ""
        self.menu_modes = ["Manual Mode", "Suggest Strong Password", "Settings"]
        self.menu_index = 0
        self.save_decision = ["Yes", "No"]
        self.save_index = 0
        self.login_index = 0

        # Set the initial state
        self.current_state = UnblockState(self)
        self.transition_to(UnblockState(self))

    def transition_to(self, new_state):
        self.current_state.exit()
        self.current_state = new_state
        self.current_state.enter()

    def update(self):
        self.encoder.update()
        self.current_state.handle()
    
    def initialize_fingerprint(self, pin: int):
        if self.fingerprint is None:
            self.fingerprint = FingerprintAuthenticator(pin=pin,screen=self.screen)
            self.authenticator.attach_fingerprint(self.fingerprint)

