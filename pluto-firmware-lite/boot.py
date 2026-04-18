import board
import digitalio
import storage
import usb_cdc

# Pico RP2040 jumper switch:
# - Put a jumper between JUMPER_PIN and GND before boot to enter maintenance mode
#   (mass storage + console enabled).
# - Without jumper, mass storage is disabled and only USB CDC data is exposed.
JUMPER_PIN = board.GP14

jumper = digitalio.DigitalInOut(JUMPER_PIN)
jumper.direction = digitalio.Direction.INPUT
jumper.pull = digitalio.Pull.UP

maintenance_mode = not jumper.value
jumper.deinit()

if maintenance_mode:
	storage.enable_usb_drive()
	usb_cdc.enable(console=True, data=True)
else:
	storage.disable_usb_drive()
	usb_cdc.enable(console=False, data=True)