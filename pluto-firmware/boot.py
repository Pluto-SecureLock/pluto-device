import storage
import board, digitalio
import usb_cdc

# On the Macropad, pressing a key grounds it. You need to set a pull-up.
# If not pressed, the key will be at +V (due to the pull-up).
button = digitalio.DigitalInOut(board.D9)
button.pull = digitalio.Pull.UP

# Disable devices only if button is not pressed.
if button.value:
    storage.enable_usb_drive()
    usb_cdc.enable(console=True,data=True)
#    storage.disable_usb_drive()
#    usb_cdc.enable(console=False,data=True)

else:
#    storage.enable_usb_drive()
#    usb_cdc.enable(console=True,data=True)
   storage.disable_usb_drive()
   usb_cdc.enable(console=False,data=True)
