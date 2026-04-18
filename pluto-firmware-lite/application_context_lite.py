from auth_manager_lite import AuthManagerLite
from command_processor import CommandProcessor
from hid_output import HIDOutput
from identity_manager import IdentityManager
from usb_serial import USBSerial


class ApplicationContextLite:
    def __init__(self):
        self.usb = USBSerial()
        self.hid_output = HIDOutput()
        self.authenticator = AuthManagerLite()
        self.authenticator.set_master_key()

        self.identity = IdentityManager()
        self.identity.ensure_identity()

        self.processor = CommandProcessor(self.hid_output, self.usb, self.authenticator)
        self.processor.attach_identity(self.identity)

    def update(self):
        command = self.usb.read(echo=False)
        if command:
            print("Received command: {}".format(command))
            self.processor.execute(command)
