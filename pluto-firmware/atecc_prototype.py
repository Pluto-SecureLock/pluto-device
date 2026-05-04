import board
from busio import I2C
from adafruit_binascii import hexlify
from adafruit_atecc.adafruit_atecc import ATECC


def _to_hex(data):
    return str(hexlify(data), "utf-8").upper()

def create_atecc(debug=False, i2c=None):
    if i2c is None:
        try:
            i2c = board.I2C()
        except Exception:
            i2c = I2C(board.SCL, board.SDA)
    return ATECC(i2c, debug=debug)

def generate_random_value(atecc, rnd_min=0, rnd_max=1000000):
    return atecc.random(rnd_min, rnd_max)


def generate_nonce(atecc, seed=None):
    nonce_input = bytearray(range(20)) if seed is None else bytearray(seed)
    if len(nonce_input) != 20:
        raise ValueError("Nonce seed must be exactly 20 bytes")
    nonce_output = atecc.nonce(nonce_input, mode=0x00)
    return nonce_input, nonce_output


def generate_key(atecc, slot=0, private_key=True):
    key_buffer = bytearray(64)
    return atecc.gen_key(key_buffer, slot_num=slot, private_key=private_key)


def run_atecc_prototype(out=None, i2c=None):
    emit = out if out is not None else print
    emit("=== ATECC PROTOTYPE START ===")
    atecc = create_atecc(debug=False, i2c=i2c)

    emit("Serial Number: {}".format(atecc.serial_number))
    emit("Locked: {}".format(atecc.locked))

    random_value = generate_random_value(atecc)
    emit("Random Value (0..999999): {}".format(random_value))

    nonce_input, nonce_output = generate_nonce(atecc)
    emit("Nonce Input (20B): {}".format(_to_hex(nonce_input)))
    emit("Nonce Output (32B): {}".format(_to_hex(nonce_output)))

    try:
        generated_key = generate_key(atecc, slot=0, private_key=True)
        emit("Generated Private Key/Public Response (slot 0): {}".format(_to_hex(generated_key)))
    except Exception as ex:
        emit("gen_key(private_key=True) failed: {}".format(ex))
        try:
            generated_key = generate_key(atecc, slot=0, private_key=False)
            emit("Generated Public Key (slot 0): {}".format(_to_hex(generated_key)))
        except Exception as ex2:
            emit("gen_key(private_key=False) also failed: {}".format(ex2))

    emit("=== ATECC PROTOTYPE END ===")