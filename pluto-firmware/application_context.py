import time
import gc

class ApplicationContext:
    def __init__(self):
        import board
        import busio

        from usb_serial import USBSerial
        from hid_output import HIDOutput
        from auth_manager import AuthManager
        from encoder import RotaryEncoderWithButton
        from screen import Screen
        self.i2c = None

        if self.i2c is None:
            try:
                self.i2c = board.I2C()
            except AttributeError:
                self.i2c = busio.I2C(board.SCL, board.SDA)
        self.usb = USBSerial()
        self.hid_output = HIDOutput()
        self.fingerprint = None  # Delayed initialization
        self.authenticator = AuthManager()  # Accepts no fingerprint initially
        self.atecc = None
        self.identity = None
        self.processor = None
        self.encoder = RotaryEncoderWithButton()
        self.screen = Screen(i2c=self.i2c)

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

        # Set the initial state lazily to avoid importing states at module load time.
        from states import UnblockState

        self.current_state = None
        gc.collect()
        self.transition_to(UnblockState(self))

    def ensure_runtime_services(self):
        if self.identity is None:
            try:
                from identity_manager import IdentityManager
                # from atecc_prototype import create_atecc

                # if self.atecc is None:
                #     try:
                #         self.atecc = create_atecc(debug=False, i2c=self.i2c)
                #     except Exception:
                #         self.atecc = None

                self.identity = IdentityManager(atecc=self.atecc)
                self.identity.ensure_identity()
            except Exception as e:
                self.identity = None
                print("Identity initialization failed:", e)

        if self.processor is None:
            from command_processor import CommandProcessor

            self.processor = CommandProcessor(self.hid_output, self.usb, self.authenticator, i2c_bus=self.i2c)
            if self.identity is not None:
                self.processor.attach_identity(self.identity)

        gc.collect()

    def transition_to(self, new_state):
        if self.current_state is not None:
            self.current_state.exit()
        self.current_state = new_state
        self.current_state.enter()
        gc.collect()

    def update(self):
        self.encoder.update()
        self.current_state.handle()
    
    def initialize_fingerprint(self, pin: str):
        if self.fingerprint is None:
            gc.collect()
            from finger_print import FingerprintAuthenticator

            self.fingerprint = FingerprintAuthenticator(passwd=pin,screen=self.screen)
            self.authenticator.attach_fingerprint(self.fingerprint)
            gc.collect()