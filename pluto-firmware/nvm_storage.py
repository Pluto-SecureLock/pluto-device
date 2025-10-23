import microcontroller, binascii, struct

NVM = microcontroller.nvm
MAGIC   = b"PSL1"
VERSION = 1

HEADER_LEN = 4 + 1 + 1 + 1   # MAGIC + VER + slen + hlen
CRC_LEN    = 4

def _slot_offset(slot: int, slot_size: int) -> int:
    return slot * slot_size

def save_slot(slot: int, slot_size: int, salt: bytes, hsh: bytes):
    """Save one (salt, hash) pair into a slot."""
    slen, hlen = len(salt), len(hsh)
    total_len = HEADER_LEN + slen + hlen + CRC_LEN

    if total_len > slot_size:
        raise ValueError("Slot too small for given salt/hash")

    buf = bytearray(total_len)
    struct.pack_into(">4sBBB", buf, 0, MAGIC, VERSION, slen, hlen)
    offset = HEADER_LEN
    buf[offset:offset+slen] = salt; offset += slen
    buf[offset:offset+hlen] = hsh;  offset += hlen

    crc = binascii.crc32(buf[:-CRC_LEN]) & 0xFFFFFFFF
    struct.pack_into(">I", buf, offset, crc)

    base = _slot_offset(slot, slot_size)
    NVM[base:base+total_len] = buf
    return total_len

def load_slot(slot: int, slot_size: int):
    """Load one (salt, hash) pair from a slot, verifying CRC."""
    base = _slot_offset(slot, slot_size)
    header = bytes(NVM[base:base+HEADER_LEN])
    magic, ver, slen, hlen = struct.unpack(">4sBBB", header)

    if magic != MAGIC:
        raise ValueError(f"Slot {slot}: invalid magic")
    if ver != VERSION:
        raise ValueError(f"Slot {slot}: unsupported version")

    total_len = HEADER_LEN + slen + hlen + CRC_LEN
    data = bytes(NVM[base:base+total_len])

    crc_stored = struct.unpack(">I", data[-4:])[0]
    crc_calc = binascii.crc32(data[:-4]) & 0xFFFFFFFF
    if crc_calc != crc_stored:
        raise ValueError(f"Slot {slot}: CRC mismatch")

    offset = HEADER_LEN
    salt = data[offset:offset+slen]; offset += slen
    hsh  = data[offset:offset+hlen]
    return salt, hsh

def nvm_wipe():
    try:
        NVM[:] = b"\xFF" * len(NVM)
        return True
    except Exception as e:
        print(f"❌ Error wiping NVM: {e}")
        return False
